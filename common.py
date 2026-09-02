"""Funcoes compartilhadas: extracao de preco, log e escrita do CSV."""
from __future__ import annotations

import csv
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime

import config

_PRICE_RE = re.compile(r"R\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?")

CSV_FIELDS = [
    "collected_at",
    "site",
    "trip_leg",
    "rio_airport",
    "origin",
    "destination",
    "flight_date",
    "price_brl",
    "url",
    "status",
    "note",
]


@dataclass
class PriceResult:
    site: str
    trip_leg: str  # ida | volta
    rio_airport: str  # GIG | SDU
    origin: str
    destination: str
    flight_date: str
    price_brl: float | None = None
    status: str = "error"  # ok | no_price_found | error
    note: str = ""
    url: str = ""
    collected_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def _to_float(raw: str) -> float | None:
    digits = raw.replace("R$", "").strip()
    digits = digits.replace(".", "").replace(",", ".")
    try:
        return float(digits)
    except ValueError:
        return None


def extract_prices_from_text(text: str, min_value: float = 150, max_value: float = 15_000) -> list[float]:
    """Find every BRL amount in page text and keep values in a plausible one-way fare range."""
    prices = []
    for raw in _PRICE_RE.findall(text):
        value = _to_float(raw)
        if value is not None and min_value <= value <= max_value:
            prices.append(value)
    return prices


def setup_logging() -> None:
    os.makedirs(config.LOG_DIR, exist_ok=True)
    log_path = os.path.join(config.LOG_DIR, "crawler.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def cleanup_old_logs(log_dir: str = config.LOG_DIR, days: int = config.LOG_RETENTION_DAYS) -> None:
    if not os.path.isdir(log_dir):
        return
    cutoff = time.time() - days * 86400
    for name in os.listdir(log_dir):
        if name == "crawler.log":
            continue
        path = os.path.join(log_dir, name)
        try:
            if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            pass


def save_debug_artifacts(page, site: str, rio_airport: str, trip_leg: str) -> None:
    """Save a screenshot for the run, to speed up fixing a broken selector later."""
    os.makedirs(config.LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(config.LOG_DIR, f"{site}_{rio_airport}_{trip_leg}_{ts}")
    try:
        page.screenshot(path=base + ".png", full_page=True)
    except Exception:
        pass


def append_results(csv_path: str, results: list[PriceResult]) -> None:
    """Append only results that actually carry a price. Callers should already
    have filtered out status != "ok" / price_brl is None entries, but this is
    enforced here too so a bad call site can never write an empty row."""
    priced = [r for r in results if r.status == "ok" and r.price_brl is not None]
    if not priced:
        return
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        for r in priced:
            writer.writerow(asdict(r))
