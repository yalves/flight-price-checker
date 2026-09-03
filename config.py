"""Parametros da busca. Edite aqui para mudar rota, datas ou aeroportos."""
import os
from datetime import date

ORIGINS = ["GIG", "SDU"]  # Rio de Janeiro: Galeao e Santos Dumont
DESTINATION = "AEP"  # Buenos Aires, Aeroparque Jorge Newbery
DEPART_DATE = date(2026, 11, 21)
RETURN_DATE = date(2026, 11, 28)
ADULTS = 1

CSV_FILENAME = "precos_rio_buenosaires.csv"
LOG_DIR = "logs"
LOG_RETENTION_DAYS = 14

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DATA_JSON = os.path.join(_THIS_DIR, "docs", "data.json")

NAV_TIMEOUT_MS = 45_000
# Actively wait for a price to actually show up on the page (up to this long)
# instead of a blind fixed delay - a fixed delay can fire before real search
# results replace a loading/teaser state and end up scraping the wrong number.
PRICE_WAIT_TIMEOUT_MS = 40_000
# Small fixed buffer after a price first appears, to let the results list
# finish settling/re-sorting.
SETTLE_WAIT_MS = 1_500

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
