"""Rich terminal dashboard for positions and opportunities."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from analyst.analyst import Opportunity
from trader.paper_trader import PaperTrader

console = Console()


def show_opportunities(opportunities: list[Opportunity]):
    if not opportunities:
        console.print("[yellow]No opportunities found above threshold.[/yellow]")
        return

    table = Table(title="Opportunities", box=box.ROUNDED, show_lines=True)
    table.add_column("Edge", style="green bold", width=6)
    table.add_column("Side", width=4)
    table.add_column("Mkt%", width=6)
    table.add_column("Est%", width=6)
    table.add_column("Conf", width=6)
    table.add_column("Question", width=50)
    table.add_column("Rationale", width=60)

    for opp in opportunities:
        edge_color = "green" if opp.edge > 0.1 else "yellow"
        table.add_row(
            f"[{edge_color}]{opp.edge:+.2f}[/{edge_color}]",
            opp.side,
            f"{opp.market_price:.2f}",
            f"{opp.analyst_prob:.2f}",
            opp.confidence,
            opp.market.question[:50],
            opp.rationale[:60],
        )
    console.print(table)


def show_portfolio(trader: PaperTrader):
    s = trader.summary()
    pnl_color = "green" if s["total_pnl"] >= 0 else "red"

    panel_text = (
        f"Balance: [bold]${s['balance']:,.2f}[/bold]  |  "
        f"Open: {s['open_positions']}  |  "
        f"P&L: [{pnl_color}]${s['total_pnl']:+,.2f}[/{pnl_color}]  |  "
        f"Win rate: {s['win_rate']:.0%} ({s['wins']}W/{s['losses']}L)"
    )
    console.print(Panel(panel_text, title="Paper Portfolio", border_style="blue"))

    if trader.positions:
        table = Table(box=box.SIMPLE)
        table.add_column("ID")
        table.add_column("Status")
        table.add_column("Side")
        table.add_column("$In")
        table.add_column("P&L")
        table.add_column("Question")

        for p in sorted(trader.positions, key=lambda x: x.opened_at, reverse=True)[:20]:
            pnl_str = f"${p.pnl:+.2f}" if p.pnl is not None else "—"
            pnl_col = "green" if (p.pnl or 0) >= 0 else "red"
            status_col = {"open": "cyan", "won": "green", "lost": "red"}.get(p.status, "white")
            table.add_row(
                p.position_id,
                f"[{status_col}]{p.status}[/{status_col}]",
                p.side,
                f"${p.cost_basis:.2f}",
                f"[{pnl_col}]{pnl_str}[/{pnl_col}]",
                p.question[:55],
            )
        console.print(table)
