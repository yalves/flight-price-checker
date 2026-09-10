"""Coleta o preco mais baixo exibido no Decolar.com para um trecho (ida ou
volta) e data especificos.

O Decolar roda sobre a mesma plataforma do grupo Despegar, que aceita busca
por URL direta no formato usado abaixo (somente ida, "ow"). Se o site mudar
essa estrutura, o resultado desta funcao vem com status "error" ou
"no_price_found" e uma nota explicando o motivo — ajuste _search_url() e
rode de novo.
"""
from __future__ import annotations

import logging
from datetime import date

import config
from common import PriceResult, apply_fare_price, save_debug_artifacts, wait_for_price_text

SITE_NAME = "decolar"

log = logging.getLogger(__name__)

_CONSENT_LABELS = ["Aceitar", "Aceitar todos", "Entendi", "OK"]


def _search_url(origin: str, destination: str, flight_date: date) -> str:
    url = (
        "https://www.decolar.com/shop/flights/results/ow/"
        f"{origin}/{destination}/{flight_date.isoformat()}/"
        f"{config.ADULTS}/0/0/NA?flexDates=false&sc=OW"
    )
    # Best-effort filtro de voos diretos (stops=0). Nao verificado, pois o
    # Decolar bloqueia o acesso a partir do runner - se um dia desbloquear e
    # esse parametro nao filtrar, ajuste aqui.
    if getattr(config, "NONSTOP_ONLY", False):
        url += "&stops=0"
    return url


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
        # Resultados carregam de forma assincrona; espera mais que o padrao
        # depois que o primeiro preco aparece, para a lista terminar de assentar.
        page.wait_for_timeout(config.SETTLE_WAIT_MS + 5000)
        text = page.inner_text("body")
        apply_fare_price(result, text)
    except Exception as exc:
        result.status = "error"
        result.note = f"{type(exc).__name__}: {exc}"
        log.exception("Falha ao buscar no Decolar (%s %s-%s)", search["group"], origin, destination)
    finally:
        save_debug_artifacts(page, SITE_NAME, f"{search['group']}_{origin}-{destination}")
        page.close()
    return [result]
