"""Ponto de entrada do crawler de precos de passagens.

Roda os tres scrapers de sites (google_flights, decolar, latam) para cada
aeroporto de origem em config.ORIGINS, buscando o trecho de ida
(aeroporto -> AEP, em DEPART_DATE) e o trecho de volta (AEP -> aeroporto,
em RETURN_DATE) separadamente, para que cada preco fique identificado com
o trecho a que se refere. So os resultados com preco encontrado (status
"ok") viram linha no CSV configurado; buscas sem sucesso (bloqueio,
selector quebrado, etc.) ficam so no log, sem gerar linha vazia. Ao final,
atualiza docs/data.json para a pagina do GitHub Pages. Pensado para rodar
uma vez por dia, pelo workflow agendado em
.github/workflows/flight-price-crawler.yml.
"""
from __future__ import annotations

import logging
import os
import sys

from playwright.sync_api import sync_playwright

import build_site_data
import config
from common import PriceResult, append_results, cleanup_old_logs, setup_logging
from sites import decolar, google_flights, latam

SITE_MODULES = [google_flights, decolar, latam]

# (trip_leg, flight_date) - "ida" searches rio_airport -> DESTINATION on
# DEPART_DATE, "volta" searches DESTINATION -> rio_airport on RETURN_DATE.
LEGS = [
    ("ida", config.DEPART_DATE),
    ("volta", config.RETURN_DATE),
]


def main() -> int:
    setup_logging()
    cleanup_old_logs()
    log = logging.getLogger("crawler")
    log.info(
        "Iniciando coleta: origens=%s destino=%s ida=%s volta=%s",
        config.ORIGINS,
        config.DESTINATION,
        config.DEPART_DATE,
        config.RETURN_DATE,
    )

    all_results: list[PriceResult] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=config.USER_AGENT,
            locale="pt-BR",
            viewport={"width": 1366, "height": 900},
        )
        for site_module in SITE_MODULES:
            for rio_airport in config.ORIGINS:
                for trip_leg, flight_date in LEGS:
                    if trip_leg == "ida":
                        flight_origin, flight_destination = rio_airport, config.DESTINATION
                    else:
                        flight_origin, flight_destination = config.DESTINATION, rio_airport

                    log.info(
                        "Coletando %s: %s (%s) %s -> %s em %s",
                        site_module.SITE_NAME,
                        rio_airport,
                        trip_leg,
                        flight_origin,
                        flight_destination,
                        flight_date,
                    )
                    try:
                        results = site_module.scrape(
                            context, flight_origin, flight_destination, flight_date, trip_leg, rio_airport
                        )
                    except Exception as exc:
                        log.exception(
                            "Erro nao tratado em %s (%s, %s)", site_module.SITE_NAME, rio_airport, trip_leg
                        )
                        results = [
                            PriceResult(
                                site=site_module.SITE_NAME,
                                trip_leg=trip_leg,
                                rio_airport=rio_airport,
                                origin=flight_origin,
                                destination=flight_destination,
                                flight_date=flight_date.isoformat(),
                                status="error",
                                note=f"{type(exc).__name__}: {exc}",
                            )
                        ]
                    for r in results:
                        log.info("  -> status=%s preco=%s nota=%s", r.status, r.price_brl, r.note)
                    all_results.extend(r for r in results if r.status == "ok" and r.price_brl is not None)
        browser.close()

    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.CSV_FILENAME)
    append_results(csv_path, all_results)
    log.info("Gravadas %d linhas com preco em %s", len(all_results), csv_path)

    row_count = build_site_data.build(csv_path=csv_path)
    log.info("Atualizado %s com %d linhas", config.SITE_DATA_JSON, row_count)

    if not all_results:
        log.error("Nenhum preco foi coletado com sucesso nesta execucao.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
