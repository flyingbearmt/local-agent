import fcntl
import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

import chromadb
from rank_bm25 import BM25Okapi

from connectors.local import SUPPORTED_EXTENSIONS, read_local_file
from rag.embeddings import embed_query, embed_texts
from rag.ingest import chunk_text
from rag.rerank import reciprocal_rank_fusion, rerank


SCOPES = {"personal": "personal_docs", "team": "team_docs"}
GIT_PREFIX = "agent-knowledge/knowledge/android/"
MAX_TEAM_FILE_BYTES = 2_000_000


def data_home() -> Path:
    home = Path(os.environ.get("LOCAL_AGENT_HOME", "~/.local/share/local-agent")).expanduser().resolve()
    source = Path(__file__).resolve().parent
    if home == source or home.is_relative_to(source):
        raise ValueError("LOCAL_AGENT_HOME must be outside the source checkout")
    configured_repo = os.environ.get("TEAM_REPO_PATH")
    if configured_repo:
        repo = Path(configured_repo).expanduser().resolve()
        if home == repo or home.is_relative_to(repo) or repo.is_relative_to(home):
            raise ValueError("LOCAL_AGENT_HOME must not overlap the team checkout")
    return home


def private_path(name: str) -> Path:
    home = data_home()
    target = (home / name).resolve()
    if not target.is_relative_to(home):
        raise ValueError(f"Private data must remain inside {home}")
    return target


def personal_file(path: str) -> Path:
    if urlparse(path).scheme:
        raise ValueError("MCP personal documents must be local files, not URLs")
    root = private_path("personal")
    requested = Path(path).expanduser()
    resolved = (requested if requested.is_absolute() else root / requested).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Personal documents must be inside {root}")
    if resolved.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported personal document type")
    return resolved


def _scope_names(scope: str) -> tuple[str, ...]:
    if scope == "all":
        return ("personal", "team")
    if scope not in SCOPES:
        raise ValueError("scope must be personal, team, or all")
    return (scope,)


@contextmanager
def locked_state():
    home = data_home()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    with private_path("index.lock").open("a+b") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


@contextmanager
def locked_index():
    with locked_state():
        client = chromadb.PersistentClient(path=str(private_path("chroma")))
        yield client


def _collection(client, scope: str):
    return client.get_or_create_collection(
        name=SCOPES[scope], metadata={"hnsw:space": "cosine"}
    )


def _replace(collection, source: str, chunks: list[str], embeddings: list[list[float]], metadata: dict):
    old = collection.get(where={"source": source})["ids"]
    if old:
        collection.delete(ids=old)
    if chunks:
        collection.add(
            ids=[f"{source}::chunk_{index}" for index in range(len(chunks))],
            documents=chunks,
            embeddings=embeddings,
            metadatas=[
                {**metadata, "source": source, "chunk_index": index, "chunk_count": len(chunks)}
                for index in range(len(chunks))
            ],
        )


def ingest_personal(path: str) -> str:
    source = personal_file(path)
    text = read_local_file(str(source))
    if not text.strip():
        return f"File is empty: {source}"
    chunks = chunk_text(text)
    embeddings = embed_texts(chunks)
    with locked_index() as client:
        _replace(_collection(client, "personal"), str(source), chunks, embeddings, {})
    return f"Ingested '{source}' — {len(chunks)} chunks stored."


def update_personal(path: str, content: str, mode: str = "overwrite") -> str:
    if mode not in ("overwrite", "append"):
        raise ValueError("mode must be overwrite or append")
    target = personal_file(path)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with target.open("a" if mode == "append" else "w", encoding="utf-8") as output:
        output.write(content)
    return f"{'Appended to' if mode == 'append' else 'Wrote'} '{target}'."


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    ).stdout


def _team_tree() -> tuple[Path, str, dict[str, str]]:
    configured = os.environ.get("TEAM_REPO_PATH")
    ref = os.environ.get("TEAM_GIT_REF")
    if not configured or not ref:
        raise ValueError("TEAM_REPO_PATH and TEAM_GIT_REF are required for team sync")
    repo = Path(configured).expanduser().resolve(strict=True)
    if Path(_git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve() != repo:
        raise ValueError("TEAM_REPO_PATH must point to the checkout root")
    commit = _git(repo, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise ValueError("Invalid Git commit")
    entries = _git(repo, "ls-tree", "-rz", commit, "--", GIT_PREFIX)
    blobs = {}
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        header, raw_path = entry.split(b"\t", 1)
        mode, kind, blob = header.decode("ascii").split()
        source = raw_path.decode("utf-8")
        if (
            mode in ("100644", "100755")
            and kind == "blob"
            and source.startswith(GIT_PREFIX)
            and Path(source).suffix.lower() in (".md", ".markdown")
        ):
            blobs[source] = blob
    return repo, commit, blobs


def sync_team() -> str:
    repo, commit, blobs = _team_tree()
    updated = deleted = 0
    with locked_index() as client:
        collection = _collection(client, "team")
        indexed = collection.get(include=["metadatas"])
        by_source: dict[str, list[tuple[str, dict]]] = {}
        for chunk_id, metadata in zip(indexed["ids"], indexed["metadatas"]):
            by_source.setdefault(metadata["source"], []).append((chunk_id, metadata))

        for source, blob in sorted(blobs.items()):
            old = by_source.get(source, [])
            if (
                old
                and len(old) == old[0][1].get("chunk_count")
                and all(meta.get("git_blob") == blob for _, meta in old)
            ):
                continue
            size = int(_git(repo, "cat-file", "-s", blob))
            if size > MAX_TEAM_FILE_BYTES:
                raise ValueError(f"Team document exceeds size limit: {source}")
            text = _git(repo, "cat-file", "blob", blob).decode("utf-8")
            chunks = chunk_text(text)
            if not chunks and not old:
                continue
            embeddings = embed_texts(chunks) if chunks else []
            _replace(collection, source, chunks, embeddings, {"git_blob": blob, "git_commit": commit})
            updated += 1

        for source in by_source.keys() - blobs.keys():
            collection.delete(ids=[chunk_id for chunk_id, _ in by_source[source]])
            deleted += 1
    return f"Team sync at {commit}: {updated} updated, {deleted} deleted, {len(blobs)} Markdown files."


def list_documents(scope: str = "personal") -> str:
    names = _scope_names(scope)
    lines = []
    with locked_index() as client:
        for name in names:
            result = _collection(client, name).get(include=["metadatas"])
            sources: dict[str, tuple[int, dict]] = {}
            for metadata in result["metadatas"]:
                source = metadata["source"]
                count, _ = sources.get(source, (0, metadata))
                sources[source] = (count + 1, metadata)
            for source, (count, metadata) in sorted(sources.items()):
                version = f" (Git blob: {metadata['git_blob']})" if name == "team" else ""
                lines.append(f"  - [{name}] {source} ({count} chunks){version}")
    if not lines:
        return "No documents indexed yet. Use ingest_doc or sync_team_docs."
    return "Indexed documents:\n" + "\n".join(lines)


def search_documents(query: str, n_results: int = 5, scope: str = "personal") -> str:
    names = _scope_names(scope)
    if not 1 <= n_results <= 20:
        raise ValueError("n_results must be between 1 and 20")
    query_vector = embed_query(query)
    dense_hits = []
    bm25_hits = []
    with locked_index() as client:
        for name in names:
            collection = _collection(client, name)
            count = collection.count()
            if not count:
                continue
            dense = collection.query(
                query_embeddings=[query_vector], n_results=min(25, count),
                include=["documents", "metadatas"],
            )
            dense_hits.extend(
                (chunk_id, document, {**metadata, "scope": name})
                for chunk_id, document, metadata in zip(
                    dense["ids"][0], dense["documents"][0], dense["metadatas"][0]
                )
            )
            snapshot = collection.get(include=["documents", "metadatas"])
            if snapshot["ids"]:
                tokens = [document.lower().split() for document in snapshot["documents"]]
                scores = BM25Okapi(tokens).get_scores(query.lower().split())
                ranked = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)
                bm25_hits.extend(
                    (
                        snapshot["ids"][index], snapshot["documents"][index],
                        {**snapshot["metadatas"][index], "scope": name},
                    )
                    for index in ranked[:25] if scores[index] > 0
                )
    if not dense_hits:
        return "No documents indexed yet. Use ingest_doc or sync_team_docs."
    candidates = reciprocal_rank_fusion(dense_hits, bm25_hits)
    results = rerank(query, candidates, n_results)
    lines = []
    for index, (_, document, metadata, score) in enumerate(results, 1):
        version = f" (Git blob: {metadata['git_blob']})" if metadata["scope"] == "team" else ""
        lines.append(
            f"[{index}] [{metadata['scope']}] {metadata['source']}{version} "
            f"(relevance: {score:.2f})\n{document}"
        )
    return "\n\n---\n\n".join(lines)
