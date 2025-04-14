from rich.console import Console as RichConsole
from rich.table import Table
from rich import print
import typer
from cola.core.engine import Engine
import asyncio
from rich.traceback import install
import subprocess
import os
import code
import sys
import tempfile
import shutil
import aiohttp
from cola.http.response import Response
from cola.http.request import Request
from cola.core.downloader.aiohttp_downloader import AiohttpDownloader


try:
    from IPython import start_ipython
except ImportError:
    start_ipython = None

app = typer.Typer()
rich_console = RichConsole()

console = rich_console

@app.command()
def bench():
    """Run quick benchmark test."""
    print("[bold green]Running benchmark test...[/bold green]")
    # Implement benchmark logic here
    console.print("Benchmark completed.")

@app.command()
def check():
    """Check spider contracts."""
    print("[bold blue]Checking spider contracts...[/bold blue]")
    # Implement spider contract checking logic here
    console.print("Spider contracts checked.")

@app.command()
def crawl(spider_name: str):
    """Run a spider."""
    print(f"[bold magenta]Running spider: {spider_name}[/bold magenta]")
    # Implement spider running logic here
    console.print(f"Spider {spider_name} finished.")

@app.command()
def edit(spider_name: str):
    """Edit spider."""
    file_path = os.path.join("tests", spider_name, "spiders", spider_name + ".py")

    if not os.path.exists(file_path):
        console.print(f"[red]Spider '{spider_name}' not found.[/red]")
        return

    try:
        if sys.platform == "darwin":
            subprocess.run(["open", file_path])
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", file_path])
        elif sys.platform == "win32":
            subprocess.run(["start", file_path], shell=True)
        else:
            console.print(f"[red]Unsupported operating system: {sys.platform}[/red]")
            return

        console.print(f"[green]Opened spider '{spider_name}' for editing.[/green]")

    except Exception as e:
        console.print(f"[red]Could not open spider: {e}[/red]")

@app.command()
def fetch(url: str):
    """Fetch a URL using the Scrapy downloader."""
    print(f"[bold yellow]Fetching URL: {url}[/bold yellow]")
    # Implement URL fetching logic here
    console.print(f"URL {url} fetched.")

@app.command()
def genspider(spider_name: str, domain: str):
    """Generate new spider using pre-defined templates."""
    print(f"[bold green]Generating spider: {spider_name} for domain {domain}[/bold green]")
    # Implement spider generation logic here
    console.print(f"Spider {spider_name} generated.")

@app.command()
def list():
    """List available spiders."""
    print("[bold blue]Listing available spiders...[/bold blue]")
    # This command is not used in the shell, see list_spiders function below
    table = Table(title="Available Spiders")
    table.add_column("Spider Name", style="cyan", no_wrap=True)
    # Example
    for i in list_spiders():
        table.add_row(i)

    console.print(table)

@app.command()
def parse(url: str, spider_name: str = None):
    """Parse URL (using its spider) and print the results."""
    print(f"[bold magenta]Parsing URL: {url}[/bold magenta]")
    # Implement URL parsing logic here
    console.print(f"URL {url} parsed.")

@app.command()
def runspider(file_path: str):
    """Run a self-contained spider (without creating a project)."""
    print(f"[bold cyan]Running spider from file: {file_path}[/bold cyan]")
    # Implement spider running logic from a file here
    console.print(f"Spider from {file_path} finished.")

@app.command()
def settings(setting_name: str = None):
    """Get settings values."""
    print("[bold yellow]Getting settings...[/bold yellow]")
    # Implement settings retrieval logic here
    if setting_name:
        console.print(f"Setting {setting_name} value: ...")
    else:
        console.print("All settings listed here.")

@app.command()
def shell():
    """Interactive scraping console."""
    print("[bold green]Starting interactive scraping console...[/bold green]")
    install(console=rich_console)

    def _list_spiders(path='.'):
        """List available spider projects in the given path."""
        projects = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
        return projects

    engine = Engine()
    asyncio.get_event_loop().run_until_complete(engine.start())

    shell_locals = {
        "engine": engine,
        "list_spiders": _list_spiders
        # Add other relevant components here, e.g.:
        # "settings": engine.settings, if you implement settings
        # "spiders": engine.spider_manager.list_spiders(), if you implement spider_manager
    }
    rich_console.print("[green]Welcome to the Cola shell![/green]\n"
                      "Available locals: engine, list_spiders.\n"
                      "Type help(list_spiders) or help(engine) for more info.\n")

    if start_ipython:
        start_ipython(argv=[], user_ns=shell_locals)
    else:
        rich_console.print(
            "[yellow]IPython not available. Falling back to standard Python shell...[/yellow]"
        )
        code.InteractiveConsole(locals=shell_locals).interact()

@app.command()
def startproject(project_name: str):
    """Create new project."""
    print(f"[bold blue]Creating new project: {project_name}[/bold blue]")
    # Implement project creation logic here
    console.print(f"Project {project_name} created.")

@app.command()
def version():
    """Print Scrapy version."""
    print("[bold magenta]Cola framework version: 0.1.0[/bold magenta]")

@app.command()
async def view(url: str):
    """Open URL in browser, as seen by Scrapy."""
    print(f"[bold cyan]Opening URL in browser: {url}[/bold cyan]")
    try:
        engine = Engine()
        asyncio.get_event_loop().run_until_complete(engine.start())

        async with aiohttp.ClientSession() as session:
            downloader = AiohttpDownloader(session=session)
            request = Request(url=url)
            response: Response = await downloader.fetch(request)

        if response.status != 200:
            console.print(f"[red]Failed to download URL: {url} (status: {response.status})[/red]")
            return

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file_path = os.path.join(temp_dir, "view.html")
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(response.body)

            try:
                if sys.platform == "darwin":
                    subprocess.run(["open", temp_file_path])
                elif sys.platform.startswith("linux"):
                    subprocess.run(["xdg-open", temp_file_path])
                elif sys.platform == "win32":
                    subprocess.run(["start", temp_file_path], shell=True)
                else:
                    console.print(f"[red]Unsupported operating system: {sys.platform}[/red]")
                    return

                console.print(f"[green]Opened URL '{url}' in browser.[/green]")

            except Exception as e:
                console.print(f"[red]Could not open URL in browser: {e}[/red]")
    except Exception as e:
        console.print(f"[red]An error occurred: {e}[/red]")






if __name__ == "__main__":
    app()