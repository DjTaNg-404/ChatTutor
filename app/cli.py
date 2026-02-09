import sys
import os
import datetime
import uuid
from typing import List
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.layout import Layout
from rich.live import Live
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# Add the project root to sys.path to ensure imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.agent_builder import build_agent
from app.core.models import AgentState

console = Console()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_ai_response(message: str):
    """Prints the AI response rendered as Markdown."""
    md = Markdown(message)
    console.print(Panel(md, title="ChatTutor", border_style="blue", expand=False))

def print_plan(plan):
    """Prints the execution plan from the Analyzer."""
    if not plan:
        return
    
    thought = plan.thought_process
    activations = []
    if plan.needs_tutor_answer: activations.append("[cyan]Tutor[/cyan]")
    if plan.needs_judge: activations.append("[magenta]Judge[/magenta]")
    if plan.needs_inquiry: activations.append("[yellow]Inquiry[/yellow]")
    
    if not activations:
        activations_str = "None"
    else:
        activations_str = ", ".join(activations)
        
    content = f"[bold]🧠 Analyzer Thought:[/bold] {thought}\n[bold]⚡ Activating:[/bold] {activations_str}"
    # console.print(Panel(content, title="Internal State", border_style="yellow", expand=False)) 
    # Use log to make it look technical but less obtrusive than the main chat
    console.log(content) # Or print as a smaller panel

def main():
    clear_screen()
    console.print(Panel.fit("🎓 Welcome to ChatTutor CLI 🎓\nType 'exit', 'quit' or 'q' to leave.", style="bold green"))

    # Initialize the agent
    try:
        graph = build_agent()
        console.print("[dim]Agent initialized successfully.[/dim]")
    except Exception as e:
        console.print(f"[bold red]Error initializing agent:[/bold red] {e}")
        return

    # Initialize state
    chat_history: List[BaseMessage] = []
    
    # Generate Session ID (Timestamp + Short UUID)
    session_id = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:4]}"
    console.print(f"[dim]Session ID: {session_id}[/dim]")
    
    # Initial state matching the new AgentState definition
    current_state = {
        "messages": chat_history,
        "current_topic": "General Knowledge",
        "session_id": session_id,
        "plan": None,
        "tutor_output": None,
        "judge_output": None,
        "inquiry_output": None,
        "last_intent": None
    }

    while True:
        try:
            # Get user input
            user_input = Prompt.ask("\n[bold yellow]You[/bold yellow]")
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                console.print("[bold green]Goodbye! Happy learning![/bold green]")
                break
            
            if not user_input.strip():
                continue

            # Update state with user message
            current_state["messages"].append(HumanMessage(content=user_input))

            # Run the agent
            with console.status("[bold green]Thinking & Planning...[/bold green]", spinner="dots"):
                result = graph.invoke(current_state)
            
            # Update local state reference
            current_state = result
            
            # Show the thought process (The "Magic" part)
            if current_state.get("plan"):
                 # Render a nice panel for the thought process
                plan = current_state["plan"]
                thought = plan.thought_process
                activations = []
                if plan.needs_tutor_answer: activations.append("[bold cyan]Tutor Answer[/bold cyan]")
                if plan.needs_judge: activations.append("[bold magenta]Judge[/bold magenta]")
                if plan.needs_inquiry: activations.append("[bold yellow]Inquiry[/bold yellow]")
                if plan.request_summary: activations.append("[bold green]Summary[/bold green]")
                if plan.is_concluding: activations.append("[bold red]Conclusion[/bold red]")
                
                activations_str = " + ".join(activations) if activations else "None"
                
                console.print(Panel(
                    f"[italic]{thought}[/italic]\n\n[bold]⚡ Active Modules:[/bold] {activations_str}",
                    title="🧠 System 2 Reasoning",
                    border_style="yellow",
                    padding=(0, 2)
                ))

            
            # Identify new AI messages to print
            messages = current_state["messages"]
            
            # Find the last HumanMessage index to know what's new
            last_human_idx = -1
            for i in range(len(messages) - 1, -1, -1):
                if isinstance(messages[i], HumanMessage):
                    last_human_idx = i
                    break
            
            # Print all AI messages that came after the last human message
            if last_human_idx != -1:
                new_messages = messages[last_human_idx + 1:]
                for msg in new_messages:
                    if isinstance(msg, AIMessage):
                        print_ai_response(msg.content)
            
            # Check for exit signal from the agent
            if current_state.get("should_exit"):
                console.print("\n[bold green]Session Concluded. Goodbye![/bold green]")
                break

        except KeyboardInterrupt:
            console.print("\n[bold green]Goodbye![/bold green]")
            break
        except Exception as e:
            console.print(f"\n[bold red]An error occurred:[/bold red] {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
