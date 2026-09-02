"""Ponto de entrada do crawler de precos de passagens.

Roda os tres scrapers de sites (google_flights, decolar, latam) para
cada aeroporto de origem em config.ORIGINS, grava uma linha por
combinacao site+origem no CSV configurado, e atualiza docs/data.json
para a pagina do GitHub Pages. Pensado para rodar uma vez por dia,
pelo workflow agendado em .github/workflows/flight-price-crawler.yml.
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
            for origin in config.ORIGINS:
                log.info("Coletando %s: %s -> %s", site_module.SITE_NAME, origin, config.DESTINATION)
                try:
                    results = site_module.scrape(
                        context, origin, config.DESTINATION, config.DEPART_DATE, config.RETURN_DATE
                    )
                except Exception as exc:
                    log.exception("Erro nao tratado em %s (origem %s)", site_module.SITE_NAME, origin)
                    results = [
                        PriceResult(
                            site=site_module.SITE_NAME,
                            origin=origin,
                            destination=config.DESTINATION,
                            depart_date=config.DEPART_DATE.isoformat(),
                            return_date=config.RETURN_DATE.isoformat(),
                            status="error",
                            note=f"{type(exc).__name__}: {exc}",
                        )
                    ]
                all_results.extend(results)
                for r in results:
                    log.info("  -> status=%s preco=%s nota=%s", r.status, r.price_brl, r.note)
        browser.close()

    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.CSV_FILENAME)
    append_results(csv_path, all_results)
    log.info("Gravadas %d linhas em %s", len(all_results), csv_path)

    row_count = build_site_data.build(csv_path=csv_path)
    log.info("Atualizado %s com %d linhas", config.SITE_DATA_JSON, row_count)

    ok_count = sum(1 for r in all_results if r.status == "ok")
    if ok_count == 0:
        log.error("Nenhum preco foi coletado com sucesso nesta execucao.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
