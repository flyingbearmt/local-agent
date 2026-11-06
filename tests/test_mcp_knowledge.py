import asyncio
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

import mcp_knowledge as knowledge


PROJECT = Path(__file__).resolve().parents[1]


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    ).stdout.decode().strip()


def fast_rerank(query, candidates, limit):
    return [(chunk_id, text, metadata, 0.5) for chunk_id, text, metadata in candidates[:limit]]


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "android-cfx-tools"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.invalid")
        self.home = self.root / "local-state"
        env = patch.dict(os.environ, {
            "LOCAL_AGENT_HOME": str(self.home),
            "TEAM_REPO_PATH": str(self.repo),
            "TEAM_GIT_REF": "refs/heads/main",
        })
        env.start()
        self.addCleanup(env.stop)
        git(self.repo, "branch", "-M", "main")
        embeddings = patch.object(
            knowledge, "embed_texts",
            side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts],
        )
        embeddings.start()
        self.addCleanup(embeddings.stop)
        query = patch.object(knowledge, "embed_query", return_value=[0.1, 0.2, 0.3])
        query.start()
        self.addCleanup(query.stop)
        reranker = patch.object(knowledge, "rerank", side_effect=fast_rerank)
        reranker.start()
        self.addCleanup(reranker.stop)

    def commit(self, filename="guide.md", content="Android reviewed guidance"):
        document = self.repo / "knowledge" / "android" / filename
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text(content, encoding="utf-8")
        git(self.repo, "add", "knowledge/android")
        git(self.repo, "commit", "-qm", "reviewed")
        return document

    def test_scope_and_version(self):
        self.commit()
        personal = self.home / "personal" / "notes.md"
        knowledge.update_personal(str(personal), "Private preference")
        knowledge.ingest_personal(str(personal))
        knowledge.sync_team()
        self.assertIn("Private preference", knowledge.search_documents("Android", scope="personal"))
        self.assertNotIn("Android reviewed guidance", knowledge.search_documents("Android", scope="personal"))
        team = knowledge.search_documents("Android", scope="team")
        self.assertIn("Android reviewed guidance", team)
        self.assertIn("knowledge/android/guide.md", team)
        self.assertIn("Git blob:", team)
        self.assertNotIn("Private preference", team)
        self.assertIn("[team]", knowledge.list_documents("all"))
        self.assertIn("[personal]", knowledge.list_documents("all"))

    def test_changed_deleted_and_repeat_sync(self):
        document = self.commit(content="First revision")
        self.assertIn("1 updated", knowledge.sync_team())
        with patch.object(knowledge, "embed_texts", side_effect=AssertionError("re-embedded")):
            self.assertIn("0 updated, 0 deleted", knowledge.sync_team())
        document.write_text("Uncommitted draft", encoding="utf-8")
        self.assertIn("0 updated", knowledge.sync_team())
        self.assertNotIn("Uncommitted draft", knowledge.list_documents("team"))
        document.write_text("Second revision", encoding="utf-8")
        git(self.repo, "add", "knowledge/android")
        git(self.repo, "commit", "-qm", "revision")
        self.assertIn("1 updated", knowledge.sync_team())
        self.assertIn("Second revision", knowledge.search_documents("revision", scope="team"))
        document.unlink()
        git(self.repo, "add", "-u")
        git(self.repo, "commit", "-qm", "deletion")
        self.assertIn("1 deleted", knowledge.sync_team())
        self.assertNotIn("guide.md", knowledge.list_documents("team"))
        self.assertIn("0 updated, 0 deleted", knowledge.sync_team())

    def test_paths_cannot_escape_personal_area(self):
        self.commit()
        for target in (
            str(self.repo / "knowledge/android/guide.md"),
            "../../escape.md", "https://example.org/note.md",
        ):
            with self.subTest(target=target), self.assertRaises(ValueError):
                knowledge.update_personal(target, "blocked")
            with self.subTest(target=target), self.assertRaises(ValueError):
                knowledge.ingest_personal(target)
        symlink_home = self.root / "symlink-state"
        symlink_home.mkdir()
        (symlink_home / "personal").symlink_to(self.repo, target_is_directory=True)
        with patch.dict(os.environ, {"LOCAL_AGENT_HOME": str(symlink_home)}):
            with self.assertRaises(ValueError):
                knowledge.update_personal("guide.md", "blocked")
        with self.assertRaises(ValueError):
            knowledge.list_documents("wrong")

    def test_git_source_ignores_symlinks_and_non_markdown(self):
        self.commit()
        (self.repo / "knowledge/android/link.md").symlink_to(self.repo / ".git/config")
        (self.repo / "knowledge/android/key.txt").write_text("secret", encoding="utf-8")
        git(self.repo, "add", "knowledge/android")
        git(self.repo, "commit", "-qm", "other files")
        knowledge.sync_team()
        listing = knowledge.list_documents("team")
        self.assertIn("guide.md", listing)
        self.assertNotIn("link.md", listing)
        self.assertNotIn("key.txt", listing)

    def test_failed_sync_does_not_purge_and_recovers(self):
        document = self.commit(content="Original guidance")
        knowledge.sync_team()
        document.write_text("Revised guidance", encoding="utf-8")
        git(self.repo, "add", "knowledge/android")
        git(self.repo, "commit", "-qm", "revised")
        with patch.object(knowledge, "embed_texts", side_effect=RuntimeError("embedding unavailable")):
            with self.assertRaises(RuntimeError):
                knowledge.sync_team()
        self.assertIn("Original guidance", knowledge.search_documents("guidance", scope="team"))
        with patch.dict(os.environ, {"TEAM_GIT_REF": "missing-ref"}):
            with self.assertRaises(subprocess.CalledProcessError):
                knowledge.sync_team()
        self.assertIn("Original guidance", knowledge.search_documents("guidance", scope="team"))
        self.assertIn("1 updated", knowledge.sync_team())
        self.assertIn("Revised guidance", knowledge.search_documents("guidance", scope="team"))

    def test_two_processes_write_and_read_same_chroma(self):
        self.commit()
        worker = """
import mcp_knowledge as knowledge
import sys
knowledge.embed_texts = lambda texts: [[0.1, 0.2, 0.3] for _ in texts]
knowledge.update_personal(sys.argv[1] + '.md', 'Process ' + sys.argv[1])
knowledge.ingest_personal(sys.argv[1] + '.md')
print(knowledge.list_documents('personal'))
"""
        env = {**os.environ, "PYTHONPATH": str(PROJECT)}
        processes = [subprocess.Popen(
            [sys.executable, "-c", worker, name], cwd=PROJECT, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ) for name in ("alpha", "beta")]
        for process in processes:
            stdout, stderr = process.communicate(timeout=60)
            self.assertEqual(process.returncode, 0, (stdout, stderr))
        self.assertIn("alpha.md", knowledge.list_documents("personal"))
        self.assertIn("beta.md", knowledge.list_documents("personal"))
        knowledge.sync_team()
        reader = subprocess.run(
            [sys.executable, "-c", "import mcp_knowledge; print(mcp_knowledge.list_documents('team'))"],
            cwd=PROJECT, env=env, check=True, capture_output=True, text=True,
        )
        self.assertIn("guide.md", reader.stdout)

    def test_stdio_mcp_discovers_and_calls_tools(self):
        async def exercise():
            parameters = StdioServerParameters(
                command=sys.executable,
                args=[str(PROJECT / "mcp_server.py")],
                env={**os.environ, "PYTHONPATH": str(PROJECT)},
            )
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    tools = {tool.name for tool in (await client.list_tools()).tools}
                    expected = {
                        "ingest_doc", "search_docs", "update_doc", "list_docs",
                        "sync_team_docs", "add_memo_tool",
                    }
                    self.assertTrue(expected <= tools)
                    result = await client.call_tool("list_docs", {"scope": "team"})
                    self.assertIn("No documents indexed yet", result.content[0].text)
                    saved = await client.call_tool(
                        "add_memo_tool", {"topic": "Local", "content": "Private"}
                    )
                    self.assertFalse(saved.isError)

        asyncio.run(exercise())
        self.assertIn("Private", (self.home / "memory.md").read_text())

    def test_two_stdio_mcp_processes_share_index(self):
        (self.repo / "README.md").write_text("Fixture", encoding="utf-8")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-qm", "empty team tree")

        async def exercise(tool, arguments):
            parameters = StdioServerParameters(
                command=sys.executable,
                args=[str(PROJECT / "mcp_server.py")],
                env={**os.environ, "PYTHONPATH": str(PROJECT), "HF_HUB_OFFLINE": "1"},
            )
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    return await client.call_tool(tool, arguments)

        async def run_both():
            return await asyncio.gather(
                exercise("sync_team_docs", {}),
                exercise("list_docs", {"scope": "team"}),
            )

        sync, listing = asyncio.run(run_both())
        self.assertIn("Team sync at", sync.content[0].text)
        self.assertFalse(listing.isError)
        self.assertIn("No documents indexed yet", knowledge.list_documents("team"))


if __name__ == "__main__":
    unittest.main()
