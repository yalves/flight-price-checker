"""Parametros da busca. Edite aqui para mudar rota, datas ou aeroportos."""
import os
from datetime import date

ADULTS = 1

# So voos diretos (sem escala). Cada site aplica isso do jeito que da:
# Google Flights via a busca ("nonstop" na query); Decolar via parametro de
# URL (stops=0). Coloque False para voltar a considerar voos com conexao.
NONSTOP_ONLY = True

# Aeroportos que aparecem nas buscas (so para rotular no painel/logs).
AIRPORTS = {
    "GIG": "Galeao (GIG)",
    "SDU": "Santos Dumont (SDU)",
    "AEP": "Buenos Aires - Aeroparque (AEP)",
    "FTE": "El Calafate (FTE)",
}

# Cada busca e um trecho SO DE IDA (origin -> destination numa data). Buscas
# com o mesmo `group` aparecem juntas no painel (um card/grafico), agregadas
# pelo menor preco - ex.: a volta ao Rio via Galeao e via Santos Dumont sao
# o mesmo grupo. Edite aqui para mudar/adicionar rotas.
#
# Viagem atual:
#   - Rio -> Buenos Aires (ida) JA FOI COMPRADA, entao nao e mais buscada.
#   - Volta Buenos Aires -> Rio (28/11), Galeao ou Santos Dumont.
#   - Bate-volta Buenos Aires <-> El Calafate: ida 25/11, volta 28/11.
SEARCHES = [
    {
        "group": "rio_volta",
        "group_label": "Volta ao Rio (Buenos Aires → GIG/SDU)",
        "leg": "volta",
        "origin": "AEP",
        "destination": "GIG",
        "flight_date": date(2026, 11, 28),
    },
    {
        "group": "rio_volta",
        "group_label": "Volta ao Rio (Buenos Aires → GIG/SDU)",
        "leg": "volta",
        "origin": "AEP",
        "destination": "SDU",
        "flight_date": date(2026, 11, 28),
    },
    {
        "group": "elcalafate_ida",
        "group_label": "Ida El Calafate (Buenos Aires → El Calafate)",
        "leg": "ida",
        "origin": "AEP",
        "destination": "FTE",
        "flight_date": date(2026, 11, 25),
    },
    {
        "group": "elcalafate_volta",
        "group_label": "Volta El Calafate (El Calafate → Buenos Aires)",
        "leg": "volta",
        "origin": "FTE",
        "destination": "AEP",
        "flight_date": date(2026, 11, 28),
    },
]

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
