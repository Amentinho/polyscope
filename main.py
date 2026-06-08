"""Polyscope — Polymarket AI trading agent (paper mode)."""

import os
import click
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console()


@click.group()
def cli():
    """Polyscope: AI-powered Polymarket analyst and paper trader."""
    pass


@cli.command()
@click.option("--min-edge", default=0.05, help="Minimum edge to show (0.05 = 5%)")
@click.option("--min-liquidity", default=5000, help="Minimum market liquidity in USD")
@click.option("--trade/--no-trade", default=False, help="Auto-open paper positions on opportunities")
def scan(min_edge: float, min_liquidity: float, trade: bool):
    """Scan news + markets, find opportunities, optionally paper-trade."""
    from ingester.sources import fetch_all
    from polymarket.client import fetch_markets
    from analyst.analyst import find_opportunities
    from trader.paper_trader import PaperTrader
    from dashboard.display import show_opportunities, show_portfolio

    console.print("[bold cyan]Polyscope[/bold cyan] — scanning news and markets...")

    with console.status("Fetching news..."):
        news = fetch_all(max_age_hours=6)
    console.print(f"  [green]✓[/green] {len(news)} news items fetched")

    with console.status("Fetching Polymarket markets..."):
        markets = fetch_markets(limit=200)
    console.print(f"  [green]✓[/green] {len(markets)} active markets loaded")

    with console.status("Analyzing opportunities (this takes ~30s)..."):
        opportunities = find_opportunities(news, markets, min_edge=min_edge, min_liquidity=min_liquidity)
    console.print(f"  [green]✓[/green] {len(opportunities)} opportunities found above {min_edge:.0%} edge\n")

    show_opportunities(opportunities)

    if trade and opportunities:
        trader = PaperTrader()
        max_usd = float(os.getenv("MAX_POSITION_USD", "50.0"))
        opened = 0
        for opp in opportunities[:5]:  # max 5 positions per scan
            pos = trader.open_position(opp, max_usd=max_usd)
            if pos:
                console.print(
                    f"  [green]PAPER BUY[/green] {pos.position_id}: "
                    f"{opp.side} {pos.shares:.1f} shares @ ${opp.market_price:.3f} "
                    f"(${pos.cost_basis:.2f}) — {opp.market.question[:50]}"
                )
                opened += 1
        console.print(f"\n[bold]{opened} paper position(s) opened.[/bold]")
        console.print()
        show_portfolio(trader)
    elif opportunities:
        console.print("\n[dim]Run with --trade to auto-open paper positions.[/dim]")


@cli.command()
def portfolio():
    """Show current paper trading portfolio."""
    from trader.paper_trader import PaperTrader
    from dashboard.display import show_portfolio

    trader = PaperTrader()
    show_portfolio(trader)


@cli.command()
@click.argument("position_id")
@click.argument("exit_price", type=float)
@click.option("--won/--lost", required=True)
def close(position_id: str, exit_price: float, won: bool):
    """Manually close a paper position (e.g. after market resolves)."""
    from trader.paper_trader import PaperTrader

    trader = PaperTrader()
    pos = trader.close_position(position_id, exit_price, won)
    if pos:
        pnl_str = f"${pos.pnl:+.2f}"
        console.print(f"[bold]Closed {position_id}[/bold]: {pos.status.upper()} | P&L {pnl_str}")
    else:
        console.print(f"[red]Position {position_id} not found or already closed.[/red]")


if __name__ == "__main__":
    cli()
