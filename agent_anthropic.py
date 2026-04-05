"""
Anthropic/Claude Agent Implementation
====================================
A terminal REPL that drives a ReAct loop using Claude as the reasoning engine.
"""

import json
from anthropic import Anthropic
from rich.console import Console
from rich.markdown import Markdown

from tools.registry_anthropic import TOOL_DEFINITIONS, execute_tool

SYSTEM_PROMPT = """You are a local document agent. You help the user manage, search, and update documents stored on your machine.

You have eight tools:
- ingest_doc   → index a local file or web page into the knowledge base
- search_docs  → find relevant passages (RAG retrieval)
- update_doc   → write or append to a local file
- list_docs    → show what is currently indexed
- add_memo     → add a memo to your personal memory file
- search_memos → search through your memos
- list_memo_topics → list all memo topics
- delete_memo  → delete a memo by topic

When given a goal, think step by step. Call tools in sequence as needed — you can call multiple tools before giving a final answer. Always ground your answers in retrieved content when answering questions about documents."""


class AnthropicAgent:
    def __init__(self, model_name: str = "claude-opus-4-6"):
        self.client = Anthropic()
        self.model_name = model_name
        self.console = Console()
    
    def run_agent(self, goal: str) -> None:
        """
        ReAct loop for a single user goal using Claude.

        Each iteration:
          1. Ask Claude what to do next (it may call a tool or give a final answer)
          2. If it called a tool → execute it, feed the result back, loop
          3. If it gave a final answer → done
        """
        messages = [{"role": "user", "content": goal}]

        while True:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            # Print any text Claude produced in this turn
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    self.console.print(Markdown(block.text))

            # No tool calls → Claude is done
            if response.stop_reason == "end_turn":
                break

            # Tool calls → execute each one and feed results back
            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        # Show the user what the agent is doing
                        args_preview = ", ".join(f"{k}={v!r}" for k, v in block.input.items())
                        self.console.print(f"\n[bold yellow]→ {block.name}[/bold yellow]({args_preview})")

                        result = execute_tool(block.name, block.input)

                        # Show a short preview of the result
                        preview = result[:300] + ("…" if len(result) > 300 else "")
                        self.console.print(f"[dim]{preview}[/dim]")

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            }
                        )

                messages.append({"role": "user", "content": tool_results})
