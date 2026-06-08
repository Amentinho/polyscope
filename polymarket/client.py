"""Polymarket CLOB + Gamma API client (read-only for paper trading)."""

import httpx
from dataclasses import dataclass
from typing import Optional


CLOB_BASE = "https://clob.polymarket.com"
GAMMA_BASE = "https://gamma-api.polymarket.com"


@dataclass
class Market:
    condition_id: str
    question: str
    description: str
    category: str
    end_date: Optional[str]
    yes_price: float   # probability 0–1
    no_price: float
    volume_24h: float
    liquidity: float
    active: bool
    url: str


def _get(url: str, params: dict = None) -> dict | list:
    resp = httpx.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_markets(limit: int = 200, active_only: bool = True) -> list[Market]:
    """Fetch open prediction markets from Gamma API."""
    params = {"limit": limit, "active": "true" if active_only else "false", "closed": "false"}
    try:
        data = _get(f"{GAMMA_BASE}/markets", params=params)
        markets = []
        for m in data:
            tokens = m.get("tokens", [])
            yes_price = no_price = 0.5
            for t in tokens:
                outcome = t.get("outcome", "").lower()
                price = float(t.get("price", 0.5))
                if outcome == "yes":
                    yes_price = price
                elif outcome == "no":
                    no_price = price
            markets.append(Market(
                condition_id=m.get("conditionId", ""),
                question=m.get("question", ""),
                description=m.get("description", ""),
                category=m.get("category", ""),
                end_date=m.get("endDate"),
                yes_price=yes_price,
                no_price=no_price,
                volume_24h=float(m.get("volume24hr", 0)),
                liquidity=float(m.get("liquidity", 0)),
                active=m.get("active", True),
                url=f"https://polymarket.com/event/{m.get('slug', '')}",
            ))
        return markets
    except Exception as e:
        print(f"[polymarket] fetch error: {e}")
        return []


def fetch_market(condition_id: str) -> Optional[Market]:
    markets = fetch_markets(limit=1)  # fallback
    try:
        data = _get(f"{GAMMA_BASE}/markets/{condition_id}")
        m = data
        tokens = m.get("tokens", [])
        yes_price = no_price = 0.5
        for t in tokens:
            if t.get("outcome", "").lower() == "yes":
                yes_price = float(t.get("price", 0.5))
            elif t.get("outcome", "").lower() == "no":
                no_price = float(t.get("price", 0.5))
        return Market(
            condition_id=m.get("conditionId", ""),
            question=m.get("question", ""),
            description=m.get("description", ""),
            category=m.get("category", ""),
            end_date=m.get("endDate"),
            yes_price=yes_price,
            no_price=no_price,
            volume_24h=float(m.get("volume24hr", 0)),
            liquidity=float(m.get("liquidity", 0)),
            active=m.get("active", True),
            url=f"https://polymarket.com/event/{m.get('slug', '')}",
        )
    except Exception as e:
        print(f"[polymarket] fetch_market error: {e}")
        return None
