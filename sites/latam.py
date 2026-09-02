"""Coleta o preco mais baixo exibido no site da LATAM para uma rota e datas."""
from __future__ import annotations

import logging
import urllib.parse
from datetime import date

import config
from common import PriceResult, extract_prices_from_text, save_debug_artifacts

SITE_NAME = "latam"

log = logging.getLogger(__name__)

_CONSENT_LABELS = ["Aceitar", "Aceitar todos os cookies", "Aceito"]


def _search_url(origin: str, destination: str, depart: date, ret: date) -> str:
    params = {
        "origin": origin,
        "destination": destination,
        "outbound": f"{depart.isoformat()}T12:00:00.000Z",
        "inbound": f"{ret.isoformat()}T12:00:00.000Z",
        "adt": str(config.ADULTS),
        "chd": "0",
        "inf": "0",
        "trip": "RT",
        "cabin": "Economy",
        "redemption": "false",
        "sort": "RECOMMENDED",
    }
    return "https://www.latamairlines.com/br/pt/oferta-voos?" + urllib.parse.urlencode(params)


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
        log.exception("Falha ao buscar na LATAM (origem %s)", origin)
    finally:
        save_debug_artifacts(page, SITE_NAME, origin)
        page.close()
    return [result]
