"""
Local Document Agent
====================
A terminal REPL that drives a ReAct loop (Reason → Act → Observe → repeat)
using Claude as the reasoning engine and a set of RAG tools as its hands.

Usage:
    python agent.py
"""

import os
from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule

from tools.registry import TOOL_DEFINITIONS, execute_tool

load_dotenv()

client = Anthropic()
console = Console()

SYSTEM_PROMPT = """You are a local document agent. You help the user manage, search, and update documents stored on their machine.

You have four tools:
- ingest_doc   → index a file into the knowledge base
- search_docs  → find relevant passages (RAG retrieval)
- update_doc   → write or append to a local file
- list_docs    → show what is currently indexed

When given a goal, think step by step. Call tools in sequence as needed — you can call multiple tools before giving a final answer. Always ground your answers in retrieved content when answering questions about documents."""


def run_agent(goal: str) -> None:
    """
    ReAct loop for a single user goal.

    Each iteration:
      1. Ask Claude what to do next (it may call a tool or give a final answer)
      2. If it called a tool → execute it, feed the result back, loop
      3. If it gave a final answer (stop_reason == "end_turn") → done
    """
    messages = [{"role": "user", "content": goal}]

    while True:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Print any text Claude produced in this turn
        for block in response.content:
            if hasattr(block, "text") and block.text:
                console.print(Markdown(block.text))

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
                    console.print(f"\n[bold yellow]→ {block.name}[/bold yellow]({args_preview})")

                    result = execute_tool(block.name, block.input)

                    # Show a short preview of the result
                    preview = result[:300] + ("…" if len(result) > 300 else "")
                    console.print(f"[dim]{preview}[/dim]")

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})


def main() -> None:
    console.print(Rule("[bold green]Local Document Agent[/bold green]"))
    console.print("[dim]Type your goal or question. Type 'exit' to quit.[/dim]\n")

    while True:
        try:
            goal = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not goal:
            continue
        if goal.lower() in ("exit", "quit"):
            break

        console.print()
        run_agent(goal)
        console.print()

    console.print("\n[dim]Bye![/dim]")


if __name__ == "__main__":
    main()
