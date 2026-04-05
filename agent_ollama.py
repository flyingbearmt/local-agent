"""
Ollama/OpenAI Agent Implementation
==================================
A terminal REPL that drives a ReAct loop using Ollama/OpenAI-compatible models.
"""

import json
from ollama import Client
from rich.console import Console
from rich.markdown import Markdown

from tools.registry_openai import TOOL_DEFINITIONS, execute_tool

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


class OllamaAgent:
    def __init__(self, model_name: str = "llama3.1:8b", host: str = "http://localhost:11434"):
        self.client = Client(host=host)
        self.model_name = model_name
        self.console = Console()
    
    def run_agent(self, goal: str) -> None:
        """
        ReAct loop for a single user goal using Ollama.

        Each iteration:
          1. Ask the model what to do next (it may call a tool or give a final answer)
          2. If it called a tool → execute it, feed the result back, loop
          3. If it gave a final answer → done
        """
        messages = [{"role": "user", "content": goal}]

        while True:
            # Prepare tools for the model
            tools_msg = {
                "role": "system",
                "content": f"{SYSTEM_PROMPT}\n\nAvailable tools:\n{json.dumps(TOOL_DEFINITIONS, indent=2)}"
            }
            
            response = self.client.chat(
                model=self.model_name,
                messages=[tools_msg] + messages,
                tools=TOOL_DEFINITIONS
            )

            # Get the main response
            message = response['message']
            
            # Print any text the model produced
            if message.get('content'):
                self.console.print(Markdown(message['content']))

            # No tool calls → model is done
            if not message.get('tool_calls'):
                messages.append({"role": "assistant", "content": message.get('content', '')})
                break

            # Tool calls → execute each one and feed results back
            messages.append({"role": "assistant", "content": message.get('content', '')})

            tool_results = []
            for tool_call in message.get('tool_calls', []):
                function_name = tool_call['function']['name']
                function_args = tool_call['function']['arguments']
                
                # Show the user what the agent is doing
                args_preview = ", ".join(f"{k}={v!r}" for k, v in function_args.items())
                self.console.print(f"\n[bold yellow]→ {function_name}[/bold yellow]({args_preview})")

                try:
                    result = execute_tool(function_name, function_args)
                    # Show a short preview of the result
                    preview = str(result)[:300] + ("…" if len(str(result)) > 300 else "")
                    self.console.print(f"[dim]{preview}[/dim]")
                    
                    tool_results.append({
                        "role": "tool",
                        "name": function_name,
                        "content": str(result)
                    })
                except Exception as e:
                    error_msg = f"Error executing {function_name}: {str(e)}"
                    self.console.print(f"[red]{error_msg}[/red]")
                    tool_results.append({
                        "role": "tool",
                        "name": function_name,
                        "content": error_msg
                    })

            messages.extend(tool_results)
