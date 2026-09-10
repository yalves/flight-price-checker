"""Ponto de entrada do crawler de precos de passagens.

Roda os tres scrapers de sites (google_flights, decolar, latam) para cada
busca definida em config.SEARCHES (cada uma um trecho so-de-ida: origem,
destino e data). So os resultados com preco encontrado (status "ok") viram
linha no CSV configurado; buscas sem sucesso (bloqueio, sem voo direto,
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


def main() -> int:
    setup_logging()
    cleanup_old_logs()
    log = logging.getLogger("crawler")
    log.info(
        "Iniciando coleta: %d buscas x %d sites (nonstop=%s)",
        len(config.SEARCHES),
        len(SITE_MODULES),
        getattr(config, "NONSTOP_ONLY", False),
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
            for search in config.SEARCHES:
                log.info(
                    "Coletando %s: %s (%s) %s -> %s em %s",
                    site_module.SITE_NAME,
                    search["group"],
                    search["leg"],
                    search["origin"],
                    search["destination"],
                    search["flight_date"],
                )
                try:
                    results = site_module.scrape(context, search)
                except Exception as exc:
                    log.exception(
                        "Erro nao tratado em %s (%s %s-%s)",
                        site_module.SITE_NAME,
                        search["group"],
                        search["origin"],
                        search["destination"],
                    )
                    results = [
                        PriceResult(
                            site=site_module.SITE_NAME,
                            group=search["group"],
                            group_label=search["group_label"],
                            leg=search["leg"],
                            origin=search["origin"],
                            destination=search["destination"],
                            flight_date=search["flight_date"].isoformat(),
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
