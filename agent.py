"""
Local Document Agent
====================
A dispatcher that routes to the appropriate agent implementation based on configuration.

Usage:
    python agent.py
"""

import os
from dotenv import load_dotenv
from rich.console import Console
from rich.rule import Rule

load_dotenv()

console = Console()

# Detect which model to use based on environment or configuration
MODEL_TYPE = os.getenv("MODEL_TYPE", "ollama").lower()  # Options: "anthropic" or "ollama"

if MODEL_TYPE == "anthropic":
    from agent_anthropic import AnthropicAgent
    MODEL_NAME = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
    agent = AnthropicAgent(model_name=MODEL_NAME)
else:
    from agent_ollama import OllamaAgent
    MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    agent = OllamaAgent(model_name=MODEL_NAME)


def main() -> None:
    model_info = f" ({MODEL_TYPE} - {MODEL_NAME})" if MODEL_TYPE != "anthropic" else f" ({MODEL_NAME})"
    console.print(Rule(f"[bold green]Local Document Agent{model_info}[/bold green]"))
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
        agent.run_agent(goal)
        console.print()

    console.print("\n[dim]Bye![/dim]")


if __name__ == "__main__":
    main()
