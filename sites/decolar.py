"""Coleta o preco mais baixo exibido no Decolar.com para uma rota e datas.

O Decolar roda sobre a mesma plataforma do grupo Despegar, que aceita
busca por URL direta no formato usado abaixo. Se o site mudar essa
estrutura, o resultado desta funcao vem com status "error" ou
"no_price_found" e uma nota explicando o motivo — ajuste _search_url()
e rode de novo.
"""
from __future__ import annotations

import logging
from datetime import date

import config
from common import PriceResult, extract_prices_from_text, save_debug_artifacts

SITE_NAME = "decolar"

log = logging.getLogger(__name__)

_CONSENT_LABELS = ["Aceitar", "Aceitar todos", "Entendi", "OK"]


def _search_url(origin: str, destination: str, depart: date, ret: date) -> str:
    return (
        "https://www.decolar.com/shop/flights/results/rt/"
        f"{origin}/{destination}/{depart.isoformat()}/{ret.isoformat()}/"
        f"{config.ADULTS}/0/0/NA?flexDates=false&sc=RT"
    )


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
        # Resultados carregam de forma assincrona; espera mais que o padrao.
        page.wait_for_timeout(config.POST_LOAD_WAIT_MS + 5000)
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
        log.exception("Falha ao buscar no Decolar (origem %s)", origin)
    finally:
        save_debug_artifacts(page, SITE_NAME, origin)
        page.close()
    return [result]
