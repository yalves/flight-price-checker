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

# Text hints used to tell whether a fare shown near a price includes a
# checked bag. Best-effort: sites word this differently and can change
# wording, so an amount with no baggage hint nearby is skipped rather than
# assumed to include one - see extract_priced_offers_with_checked_bag().
_CHECKED_BAG_INCLUDED_HINTS = [
    "bagagem despachada incluída",
    "bagagem despachada incluida",
    "bagagem despachada grátis",
    "bagagem despachada gratis",
    "1 bagagem despachada",
    "2 bagagens despachadas",
    "inclui bagagem despachada",
    "com bagagem despachada",
    "bagagem despachada: incluída",
    "checked bag included",
    "1 checked bag",
    "2 checked bags",
]
_CHECKED_BAG_EXCLUDED_HINTS = [
    "sem bagagem despachada",
    "não inclui bagagem despachada",
    "nao inclui bagagem despachada",
    "bagagem despachada não incluída",
    "bagagem despachada nao incluida",
    "somente bagagem de mão",
    "apenas bagagem de mão",
    "só bagagem de mão",
    "no checked bag",
    "carry-on bag only",
    "hand baggage only",
]

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


def extract_priced_offers_with_checked_bag(
    text: str, min_value: float = 150, max_value: float = 15_000
) -> list[float]:
    """Like extract_prices_from_text, but only keeps an amount that sits on
    the same line as an explicit "checked bag included" mention, and always
    drops one on a line marked carry-on-only/no checked bag. An amount with
    no baggage wording on its own line is dropped too - missing a fare is
    safer than quietly counting one that has no checked bag. Deliberately
    scoped to a single line (not a wider character/line window): different
    fare options usually render as adjacent lines, and a wider window ends
    up mixing one fare's price with a neighboring fare's baggage wording."""
    offers = []
    for line in text.splitlines():
        lower_line = line.lower()
        if not _PRICE_RE.search(line):
            continue
        if any(hint in lower_line for hint in _CHECKED_BAG_EXCLUDED_HINTS):
            continue
        if not any(hint in lower_line for hint in _CHECKED_BAG_INCLUDED_HINTS):
            continue
        for m in _PRICE_RE.finditer(line):
            value = _to_float(m.group(0))
            if value is not None and min_value <= value <= max_value:
                offers.append(value)
    return offers


def apply_extracted_price(result: PriceResult, text: str, log: logging.Logger | None = None) -> None:
    """Fill in result.price_brl/status/note from page text, accepting only an
    offer whose nearby text confirms a checked bag is included."""
    bag_offers = extract_priced_offers_with_checked_bag(text)
    if bag_offers:
        result.price_brl = min(bag_offers)
        result.status = "ok"
        return
    raw_offers = extract_prices_from_text(text)
    result.status = "no_price_found"
    if raw_offers:
        result.note = (
            f"{len(raw_offers)} preco(s) encontrados, mas nenhum com bagagem despachada "
            "confirmada no texto da pagina."
        )
        if log is not None:
            # The wording sites use for baggage inclusion can differ from
            # _CHECKED_BAG_INCLUDED_HINTS - log the actual price-bearing
            # lines so the hint lists can be tuned against real text
            # instead of guessing blind.
            price_lines = [line.strip() for line in text.splitlines() if _PRICE_RE.search(line)]
            for sample in price_lines[:8]:
                log.info("    linha com preco (sem bagagem confirmada): %r", sample)
    else:
        result.note = "Nenhum preco reconhecido no texto da pagina."


def wait_for_price_text(page, timeout_ms: int) -> None:
    """Actively wait until the page shows at least one BRL amount, instead of
    a blind fixed delay - a fixed delay can fire before the real results
    replace a loading/teaser state, which is how an unrelated number (a promo
    banner, a placeholder) ends up getting scraped instead of an actual fare.
    Best-effort: if nothing shows up in time, move on and let the extraction
    step report no_price_found."""
    try:
        page.wait_for_function("() => /R\\$\\s?\\d/.test(document.body.innerText)", timeout=timeout_ms)
    except Exception:
        pass


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
