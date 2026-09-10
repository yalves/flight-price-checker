"""Coleta o preco mais baixo exibido no site da LATAM para um trecho (ida ou
volta) e data especificos."""
from __future__ import annotations

import logging
import urllib.parse
from datetime import date

import config
from common import PriceResult, apply_fare_price, save_debug_artifacts, wait_for_price_text

SITE_NAME = "latam"

log = logging.getLogger(__name__)

_CONSENT_LABELS = ["Aceitar", "Aceitar todos os cookies", "Aceito"]


def _search_url(origin: str, destination: str, flight_date: date) -> str:
    params = {
        "origin": origin,
        "destination": destination,
        "outbound": f"{flight_date.isoformat()}T12:00:00.000Z",
        "adt": str(config.ADULTS),
        "chd": "0",
        "inf": "0",
        "trip": "OW",
        "cabin": "Economy",
        "redemption": "false",
        "sort": "RECOMMENDED",
    }
    # Obs: a LATAM aplica o filtro de escalas no lado do cliente e nao tem um
    # parametro de URL simples e confiavel para "sem escala"; como o site
    # tambem bloqueia o acesso a partir do runner, config.NONSTOP_ONLY nao e
    # aplicado aqui. Se a LATAM voltar a responder e o filtro for necessario,
    # sera preciso interagir com o filtro de escalas na pagina.
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


def scrape(context, search: dict) -> list[PriceResult]:
    origin, destination = search["origin"], search["destination"]
    flight_date = search["flight_date"]
    url = _search_url(origin, destination, flight_date)
    page = context.new_page()
    result = PriceResult(
        site=SITE_NAME,
        group=search["group"],
        group_label=search["group_label"],
        leg=search["leg"],
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
        apply_fare_price(result, text)
    except Exception as exc:
        result.status = "error"
        result.note = f"{type(exc).__name__}: {exc}"
        log.exception("Falha ao buscar na LATAM (%s %s-%s)", search["group"], origin, destination)
    finally:
        save_debug_artifacts(page, SITE_NAME, f"{search['group']}_{origin}-{destination}")
        page.close()
    return [result]
