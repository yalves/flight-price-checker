"""Le o CSV de precos e grava docs/data.json, para a pagina do GitHub Pages
ler com fetch(). Roda no fim de crawler.py, e tambem pode rodar sozinho:
`python build_site_data.py`.
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime

import config


def build(csv_path: str | None = None, out_path: str | None = None) -> int:
    csv_path = csv_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), config.CSV_FILENAME)
    out_path = out_path or config.SITE_DATA_JSON

    rows = []
    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                price = row.get("price_brl") or ""
                row["price_brl"] = float(price) if price else None
                rows.append(row)
    rows.sort(key=lambda r: r["collected_at"])

    # Display groups, in the order they first appear in config.SEARCHES. The
    # dashboard renders one card/tile per group; several airport pairs can
    # share a group (e.g. the Rio return via GIG and via SDU).
    groups = []
    seen = set()
    for s in config.SEARCHES:
        if s["group"] in seen:
            continue
        seen.add(s["group"])
        groups.append(
            {
                "group": s["group"],
                "group_label": s["group_label"],
                "leg": s["leg"],
                "flight_date": s["flight_date"].isoformat(),
            }
        )

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "nonstop_only": getattr(config, "NONSTOP_ONLY", False),
        "airports": config.AIRPORTS,
        "groups": groups,
        "rows": rows,
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return len(rows)


if __name__ == "__main__":
    count = build()
    print(f"Escreveu {count} linhas em {config.SITE_DATA_JSON}")
