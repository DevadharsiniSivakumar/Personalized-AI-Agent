import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt

# Ensure parent directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.config import DATABASE_PATH, FAISS_INDEX_PATH, get_llm
from utils.logger import logger
from models.schemas import AgentState
from memory.embeddings import EmbeddingsManager
from memory.sqlite_store import SQLiteStore
from memory.faiss_store import FAISSStore
from workflows.graph import create_workflow

console = Console()


def display_welcome_banner():
    """Prints a premium, stylized welcome banner using Rich."""
    banner_text = Text()
    banner_text.append("■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■\n", style="bold blue")
    banner_text.append("   ____                                  _    _   ___    ____  \n", style="bold cyan")
    banner_text.append("  |  _ \\ ___ _ __ ___  ___  _ __   __ _ | |  / \\ |_ _|  / ___| \n", style="bold cyan")
    banner_text.append("  | |_) / _ \\ '__/ __|/ _ \\| '_ \\ / _` || | / _ \\ | |  | |  _  \n", style="bold cyan")
    banner_text.append("  |  __/  __/ |  \\__ \\ (_) | | | | (_| || |/ ___ \\| |  | |_| | \n", style="bold cyan")
    banner_text.append("  |_|   \\___|_|  |___/\\___/|_| |_|\\__,_||_/_/   \\_\\___|  \\____| \n", style="bold cyan")
    banner_text.append("                                                               \n", style="bold cyan")
    banner_text.append("                 --- LOCAL MULTI-AGENT BRAIN ---               \n", style="bold yellow")
    banner_text.append("■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■", style="bold blue")
    
    console.print(
        Panel(
            banner_text,
            subtitle="Type [bold red]/exit[/bold red] to close | [bold yellow]/help[/bold yellow] for commands",
            border_style="bold blue",
            expand=False
        )
    )


def display_help():
    """Displays a styled table listing all console commands."""
    table = Table(title="System Commands", border_style="dim blue", header_style="bold cyan")
    table.add_column("Command", style="bold green")
    table.add_column("Description")
    table.add_column("Example Usage")
    
    table.add_row("/help", "Show this command directory", "/help")
    table.add_row("/memories", "List all raw memories saved in SQLite", "/memories")
    table.add_row("/clear", "Clear the terminal screen", "/clear")
    table.add_row("/exit", "Shutdown the system safely", "/exit")
    table.add_row("[Text Input]", "Talk to the agents (intent routing handles actions)", "Remember I like Python.")
    
    console.print(table)


def list_memories(sqlite_store: SQLiteStore, user_id: int):
    """Fetches and displays memories for the current user in a Rich Table."""
    try:
        # We perform a generic search with empty string or custom retrieval
        # Let's execute a direct query or fetch all records
        with sqlite_store._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT memory_id, content, created_at FROM memories WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            rows = cursor.fetchall()

        if not rows:
            console.print("[yellow]No memories stored yet. Tell the system to remember something![/yellow]")
            return

        table = Table(title=f"Stored Memories (User ID: {user_id})", border_style="green", header_style="bold green")
        table.add_column("ID", justify="center", style="dim")
        table.add_column("Memory Content", ratio=3)
        table.add_column("Saved Date (UTC)", justify="center")

        for row in rows:
            table.add_row(
                str(row["memory_id"]),
                row["content"],
                row["created_at"][:19].replace("T", " ")
            )

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Failed to fetch memories:[/bold red] {e}")


def main():
    display_welcome_banner()
    
    # 1. Establish User Profile and authentication
    try:
        sqlite_store = SQLiteStore(DATABASE_PATH)
    except Exception as e:
        console.print(
            Panel(
                f"[bold red]Database Connection Failed:[/bold red]\n{str(e)}",
                title="Error Loading System",
                border_style="red"
            )
        )
        sys.exit(1)

    username = Prompt.ask("[bold cyan]Enter Username[/bold cyan] (default: [dim]user[/dim])", default="user").strip()
    
    # Authenticate or Create User
    user = sqlite_store.get_user(username)
    if user:
        if user.password_hash:
            # User exists and has a password
            from utils.security import verify_password
            attempts = 3
            authenticated = False
            while attempts > 0:
                password = Prompt.ask("[bold cyan]Enter Password[/bold cyan]", password=True)
                if verify_password(password, user.password_hash):
                    authenticated = True
                    break
                attempts -= 1
                console.print(f"[bold red]Incorrect password. {attempts} attempts remaining.[/bold red]")
            if not authenticated:
                console.print("[bold red]Authentication failed. Exiting.[/bold red]")
                sys.exit(1)
        else:
            # Legacy or test user with no password hash
            console.print("[yellow]This account does not have a password set. Let's secure it.[/yellow]")
            while True:
                password = Prompt.ask("[bold cyan]Set a new password[/bold cyan]", password=True)
                confirm = Prompt.ask("[bold cyan]Confirm new password[/bold cyan]", password=True)
                if password == confirm:
                    if not password:
                        console.print("[bold red]Password cannot be empty.[/bold red]")
                        continue
                    from utils.security import hash_password
                    pw_hash = hash_password(password)
                    with sqlite_store._connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (pw_hash, user.user_id))
                        conn.commit()
                    user.password_hash = pw_hash
                    console.print("[bold green]Password set successfully![/bold green]")
                    break
                else:
                    console.print("[bold red]Passwords do not match. Please try again.[/bold red]")
    else:
        # Create a new user with password
        console.print(f"[yellow]User '{username}' does not exist. Creating a new profile.[/yellow]")
        while True:
            password = Prompt.ask("[bold cyan]Create password[/bold cyan]", password=True)
            confirm = Prompt.ask("[bold cyan]Confirm password[/bold cyan]", password=True)
            if password == confirm:
                if not password:
                    console.print("[bold red]Password cannot be empty.[/bold red]")
                    continue
                user = sqlite_store.create_user(username, password)
                break
            else:
                console.print("[bold red]Passwords do not match. Please try again.[/bold red]")

    # 2. Setup systems with a progress spinner
    with console.status("[bold yellow]Booting Personal AI OS & loading embedding models...[/bold yellow]") as status:
        try:
            # Init Stores
            embeddings_manager = EmbeddingsManager()
            faiss_store = FAISSStore(FAISS_INDEX_PATH, sqlite_store, embeddings_manager)
            user_id = user.user_id
            
            # Init LLM & Graph
            llm = get_llm()
            workflow = create_workflow(faiss_store, llm)
            
        except Exception as e:
            console.print("\n")
            console.print(
                Panel(
                    f"[bold red]Initialization Failed:[/bold red]\n{str(e)}\n\n"
                    "[yellow]Please check your .env file and ensure API keys are correct, or Ollama is running if configured.[/yellow]",
                    title="Error Loading System",
                    border_style="red"
                )
            )
            sys.exit(1)

    console.print(f"\n[bold green]✓[/bold green] Connected to second brain as [bold cyan]{username}[/bold cyan] (ID: {user_id}). System Ready!\n")

    # 3. Main Loop
    while True:
        try:
            user_input = Prompt.ask(f"[bold magenta]Brain@{username}[/bold magenta] >").strip()
            
            if not user_input:
                continue

            # Command Handling
            if user_input.lower() in ["/exit", "/quit"]:
                console.print("[bold yellow]Shutting down Personal AI OS. Stay productive![/bold yellow]")
                break
            elif user_input.lower() == "/help":
                display_help()
                continue
            elif user_input.lower() == "/clear":
                os.system("cls" if os.name == "nt" else "clear")
                display_welcome_banner()
                continue
            elif user_input.lower() == "/memories":
                list_memories(sqlite_store, user_id)
                continue

            # Execute LangGraph Multi-Agent Workflow
            with console.status("[bold cyan]Processing request...[/bold cyan]") as status:
                initial_state: AgentState = {
                    "user_input": user_input,
                    "current_user_id": user_id,
                    "intent": "unknown",
                    "memory_cmd": None,
                    "memory_content": None,
                    "response": "",
                    "agent_outputs": {},
                    "errors": []
                }
                
                # Execute graph workflow run
                final_state = workflow.invoke(initial_state)

            # Print Response
            intent = final_state.get("intent", "unknown").upper()
            response_text = final_state.get("response", "")
            
            # Choose color depending on routing decision
            panel_color = "cyan"
            if intent == "KNOWLEDGE":
                panel_color = "green"
            elif intent == "PLANNER":
                panel_color = "magenta"
            elif intent == "DECISION":
                panel_color = "blue"

            # Render panel
            console.print(
                Panel(
                    Markdown(response_text),
                    title=f"[bold {panel_color}]Agent Response ({intent})[/bold {panel_color}]",
                    border_style=panel_color,
                    padding=(1, 2)
                )
            )
            console.print()

        except KeyboardInterrupt:
            console.print("\n[bold yellow]Session interrupted. Exiting...[/bold yellow]")
            break
        except Exception as e:
            console.print(f"\n[bold red]System Error Encountered:[/bold red] {e}\n")
            logger.error(f"Console loop crash: {e}", exc_info=True)


if __name__ == "__main__":
    main()
