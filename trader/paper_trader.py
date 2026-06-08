"""Paper trading engine — simulates trades with virtual balance."""

import os
import json
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from pathlib import Path

from analyst.analyst import Opportunity


DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
LEDGER_PATH = DATA_DIR / "paper_ledger.json"


@dataclass
class Position:
    position_id: str
    condition_id: str
    question: str
    side: str
    shares: float
    entry_price: float
    cost_basis: float
    market_url: str
    opened_at: str
    closed_at: str | None = None
    exit_price: float | None = None
    pnl: float | None = None
    status: str = "open"  # open | won | lost | cancelled


class PaperTrader:
    def __init__(self):
        self._load()

    def _load(self):
        if LEDGER_PATH.exists():
            with open(LEDGER_PATH) as f:
                data = json.load(f)
            self.balance = data["balance"]
            self.positions = [Position(**p) for p in data["positions"]]
        else:
            self.balance = float(os.getenv("PAPER_BALANCE", "1000.0"))
            self.positions = []

    def _save(self):
        with open(LEDGER_PATH, "w") as f:
            json.dump(
                {"balance": self.balance, "positions": [asdict(p) for p in self.positions]},
                f,
                indent=2,
            )

    def open_position(self, opp: Opportunity, max_usd: float = None) -> Position | None:
        if max_usd is None:
            max_usd = float(os.getenv("MAX_POSITION_USD", "50.0"))

        # Kelly-ish sizing: fraction = edge / (1 - entry_price)
        kelly_fraction = opp.edge / max(1 - opp.market_price, 0.01)
        # Cap at 10% Kelly and max_usd
        bet_usd = min(self.balance * kelly_fraction * 0.1, max_usd, self.balance * 0.05)
        if bet_usd < 1.0:
            print(f"[paper] Skipping {opp.market.question[:50]} — bet too small (${bet_usd:.2f})")
            return None

        shares = bet_usd / opp.market_price
        position_id = f"p_{len(self.positions)+1:04d}"

        pos = Position(
            position_id=position_id,
            condition_id=opp.market.condition_id,
            question=opp.market.question,
            side=opp.side,
            shares=shares,
            entry_price=opp.market_price,
            cost_basis=bet_usd,
            market_url=opp.market.url,
            opened_at=datetime.now(timezone.utc).isoformat(),
        )
        self.balance -= bet_usd
        self.positions.append(pos)
        self._save()
        return pos

    def close_position(self, position_id: str, exit_price: float, won: bool) -> Position | None:
        for pos in self.positions:
            if pos.position_id == position_id and pos.status == "open":
                pos.exit_price = exit_price
                pos.closed_at = datetime.now(timezone.utc).isoformat()
                if won:
                    proceeds = pos.shares * 1.0  # Polymarket pays $1/share on win
                    pos.pnl = proceeds - pos.cost_basis
                    pos.status = "won"
                else:
                    proceeds = pos.shares * exit_price
                    pos.pnl = proceeds - pos.cost_basis
                    pos.status = "lost"
                self.balance += pos.cost_basis + pos.pnl
                self._save()
                return pos
        return None

    def summary(self) -> dict:
        open_pos = [p for p in self.positions if p.status == "open"]
        closed = [p for p in self.positions if p.status in ("won", "lost")]
        total_pnl = sum(p.pnl for p in closed if p.pnl is not None)
        wins = sum(1 for p in closed if p.status == "won")
        return {
            "balance": self.balance,
            "open_positions": len(open_pos),
            "closed_positions": len(closed),
            "wins": wins,
            "losses": len(closed) - wins,
            "win_rate": wins / len(closed) if closed else 0.0,
            "total_pnl": total_pnl,
            "invested": sum(p.cost_basis for p in open_pos),
        }
