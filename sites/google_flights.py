"""Coleta o preco mais baixo exibido no Google Flights para uma rota e datas."""
from __future__ import annotations

import logging
import urllib.parse
from datetime import date

import config
from common import PriceResult, extract_prices_from_text, save_debug_artifacts

SITE_NAME = "google_flights"

log = logging.getLogger(__name__)

_AIRPORT_NAMES = {
    "GIG": "Rio de Janeiro Galeao Airport (GIG)",
    "SDU": "Rio de Janeiro Santos Dumont Airport (SDU)",
    "AEP": "Buenos Aires Aeroparque Jorge Newbery (AEP)",
}

_CONSENT_LABELS = ["Aceitar tudo", "Aceitar", "I agree", "Accept all"]


def _search_url(origin: str, destination: str, depart: date, ret: date) -> str:
    query = (
        f"flights from {_AIRPORT_NAMES.get(origin, origin)} to "
        f"{_AIRPORT_NAMES.get(destination, destination)} "
        f"{depart.isoformat()} through {ret.isoformat()} round trip"
    )
    params = {"hl": "pt-BR", "gl": "BR", "curr": "BRL", "q": query}
    return "https://www.google.com/travel/flights?" + urllib.parse.urlencode(params)


def _dismiss_consent(page) -> None:
    for label in _CONSENT_LABELS:
        button = page.get_by_role("button", name=label)
        try:
            if button.count() > 0:
                button.first.click(timeout=3000)
                page.wait_for_timeout(1000)
                return
        except Exception:
            continue


def scrape(context, origin: str, destination: str, depart: date, ret: date) -> list[PriceResult]:
    url = _search_url(origin, destination, depart, ret)
    page = context.new_page()
    result = PriceResult(
        site=SITE_NAME,
        origin=origin,
        destination=destination,
        depart_date=depart.isoformat(),
        return_date=ret.isoformat(),
    )
    try:
        page.goto(url, timeout=config.NAV_TIMEOUT_MS, wait_until="domcontentloaded")
        _dismiss_consent(page)
        page.wait_for_timeout(config.POST_LOAD_WAIT_MS)
        text = page.inner_text("body")
        prices = extract_prices_from_text(text)
        if prices:
            result.price_brl = min(prices)
            result.status = "ok"
        else:
            result.status = "no_price_found"
            result.note = "Nenhum preco reconhecido no texto da pagina."
    except Exception as exc:
        result.status = "error"
        result.note = f"{type(exc).__name__}: {exc}"
        log.exception("Falha ao buscar no Google Flights (origem %s)", origin)
    finally:
        save_debug_artifacts(page, SITE_NAME, origin)
        page.close()
    return [result]
