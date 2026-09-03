"""Coleta o preco mais baixo exibido no Google Flights para um trecho (ida ou
volta) e data especificos. Cada chamada busca uma passagem so de ida entre
`origin` e `destination`, nunca a viagem completa — assim o preco fica
identificado com o trecho a que se refere."""
from __future__ import annotations

import logging
import urllib.parse
from datetime import date

import config
from common import PriceResult, apply_extracted_price, save_debug_artifacts, wait_for_price_text

SITE_NAME = "google_flights"

log = logging.getLogger(__name__)

_AIRPORT_NAMES = {
    "GIG": "Rio de Janeiro Galeao Airport (GIG)",
    "SDU": "Rio de Janeiro Santos Dumont Airport (SDU)",
    "AEP": "Buenos Aires Aeroparque Jorge Newbery (AEP)",
}

_CONSENT_LABELS = ["Aceitar tudo", "Aceitar", "I agree", "Accept all"]


def _search_url(origin: str, destination: str, flight_date: date) -> str:
    query = (
        f"flights from {_AIRPORT_NAMES.get(origin, origin)} to "
        f"{_AIRPORT_NAMES.get(destination, destination)} "
        f"{flight_date.isoformat()} one way"
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


def scrape(
    context, origin: str, destination: str, flight_date: date, trip_leg: str, rio_airport: str
) -> list[PriceResult]:
    url = _search_url(origin, destination, flight_date)
    page = context.new_page()
    result = PriceResult(
        site=SITE_NAME,
        trip_leg=trip_leg,
        rio_airport=rio_airport,
        origin=origin,
        destination=destination,
        flight_date=flight_date.isoformat(),
        url=url,
    )
    try:
        page.goto(url, timeout=config.NAV_TIMEOUT_MS, wait_until="domcontentloaded")
        _dismiss_consent(page)
        wait_for_price_text(page, config.PRICE_WAIT_TIMEOUT_MS)
        page.wait_for_timeout(config.SETTLE_WAIT_MS)
        text = page.inner_text("body")
        apply_extracted_price(result, text, log=log)
    except Exception as exc:
        result.status = "error"
        result.note = f"{type(exc).__name__}: {exc}"
        log.exception("Falha ao buscar no Google Flights (%s, %s)", rio_airport, trip_leg)
    finally:
        save_debug_artifacts(page, SITE_NAME, rio_airport, trip_leg)
        page.close()
    return [result]
