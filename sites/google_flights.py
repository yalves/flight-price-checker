"""Coleta o preco mais baixo exibido no Google Flights para um trecho (ida ou
volta) e data especificos. Cada chamada busca uma passagem so de ida entre
`origin` e `destination`, nunca a viagem completa — assim o preco fica
identificado com o trecho a que se refere."""
from __future__ import annotations

import logging
import urllib.parse
from datetime import date

import config
from common import PriceResult, apply_extracted_price, extract_prices_from_text, save_debug_artifacts, wait_for_price_text

SITE_NAME = "google_flights"

log = logging.getLogger(__name__)

_AIRPORT_NAMES = {
    "GIG": "Rio de Janeiro Galeao Airport (GIG)",
    "SDU": "Rio de Janeiro Santos Dumont Airport (SDU)",
    "AEP": "Buenos Aires Aeroparque Jorge Newbery (AEP)",
}

_CONSENT_LABELS = ["Aceitar tudo", "Aceitar", "I agree", "Accept all"]

# Google Flights' results list only marks checked-bag inclusion with an icon
# next to the price - the page's plain text never says it (confirmed from a
# real run's screenshot), so a text-based check can never find it there. The
# reliable way to get a checked-bag-inclusive price is Google's own
# "Bagagens"/"Bags" filter, which recalculates the displayed prices to
# include the selected number of checked bags. Label lists (not one fixed
# string) because Google_flights can serve pt-BR or en-US copy depending on
# the run, and the exact accessible name can shift between minor UI updates.
_BAGGAGE_FILTER_BUTTON_LABELS = ["Bagagens", "Bags", "Baggage"]
_CHECKED_BAG_INCREMENT_LABELS = [
    "Aumentar bagagens despachadas",
    "Adicionar bagagem despachada",
    "Increase checked bags",
    "Increase number of checked bags",
    "Add checked bag",
]
_FILTER_DONE_LABELS = ["Concluído", "Concluido", "Aplicar", "Done", "Apply"]


def _search_url(origin: str, destination: str, flight_date: date) -> str:
    query = (
        f"flights from {_AIRPORT_NAMES.get(origin, origin)} to "
        f"{_AIRPORT_NAMES.get(destination, destination)} "
        f"{flight_date.isoformat()} one way"
    )
    params = {"hl": "pt-BR", "gl": "BR", "curr": "BRL", "q": query}
    return "https://www.google.com/travel/flights?" + urllib.parse.urlencode(params)


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


def _dump_controls(page, where: str) -> None:
    """Diagnostic: log the accessible name (aria-label) and visible text of
    every clickable control currently on the page, so a broken filter
    interaction can be fixed against the real accessible names instead of
    guessed ones. Never raises."""
    try:
        controls = page.evaluate(
            """() => {
                const sel = 'button, [role=\"button\"], [role=\"checkbox\"], [role=\"menuitemradio\"], [role=\"menuitemcheckbox\"], [role=\"spinbutton\"], [role=\"radio\"], input, select';
                const rx = /bagag|mala|despach|carry|mão|\\bbag/i;
                const relevant = [];
                const others = [];
                for (const el of document.querySelectorAll(sel)) {
                    const label = el.getAttribute('aria-label') || '';
                    const text = (el.innerText || el.value || '').trim().replace(/\\s+/g, ' ').slice(0, 60);
                    if (!label && !text) continue;
                    const entry = (label ? 'aria=' + JSON.stringify(label) : '') +
                                  (text ? ' text=' + JSON.stringify(text) : '');
                    if (rx.test(label) || rx.test(text)) relevant.push('BAG> ' + entry);
                    else others.push(entry);
                }
                // Baggage-related controls first (unbounded), then a sample of
                // the rest, so the stepper is never hidden by a size cap.
                return relevant.concat(others.slice(0, 60));
            }"""
        )
        log.info("DIAG [%s] %d controles (bag-relevantes primeiro):", where, len(controls))
        for c in controls:
            log.info("    %s", c)
    except Exception as exc:
        log.warning("DIAG [%s] falha ao enumerar controles: %s", where, exc)


def _apply_checked_bag_filter(page) -> bool:
    """Best-effort: open Google Flights' "Bagagens" filter and set checked
    bags to 1, so the prices shown afterwards already include a checked bag,
    instead of trying to detect that from page text. Returns True only if
    the whole sequence (open filter -> increment -> close) completed, so the
    caller knows whether it can trust the displayed prices as checked-bag-
    inclusive. Never raises: any failure here just means the caller falls
    back to the stricter (and safer) text-based check, which is more likely
    to end in no_price_found than in wrongly counting a bare fare. On each
    failure point it dumps the real accessible names via _dump_controls, so
    the selectors can be tuned from a run's log."""
    try:
        filter_button = None
        for label in _BAGGAGE_FILTER_BUTTON_LABELS:
            candidate = page.get_by_role("button", name=label, exact=False)
            if candidate.count() > 0:
                filter_button = candidate.first
                break
        if filter_button is None:
            _dump_controls(page, "barra de filtros (botao Bagagens nao encontrado)")
            return False

        filter_button.click(timeout=3000)
        page.wait_for_timeout(800)

        inc_button = None
        for inc_label in _CHECKED_BAG_INCREMENT_LABELS:
            candidate = page.get_by_role("button", name=inc_label, exact=False)
            if candidate.count() > 0:
                inc_button = candidate.first
                break
        if inc_button is None:
            _dump_controls(page, "painel de bagagem aberto (stepper nao encontrado)")
            page.keyboard.press("Escape")
            return False

        inc_button.click(timeout=3000)
        page.wait_for_timeout(400)

        for done_label in _FILTER_DONE_LABELS:
            done_button = page.get_by_role("button", name=done_label, exact=False)
            if done_button.count() > 0:
                done_button.first.click(timeout=3000)
                page.wait_for_timeout(500)
                return True

        # No explicit "done" control found - close the panel and trust the
        # selection already applied (Google Flights re-filters live as the
        # stepper changes).
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        return True
    except Exception as exc:
        log.warning("Erro ao aplicar filtro de bagagem: %s", exc)
        return False


def scrape(
    context, origin: str, destination: str, flight_date: date, trip_leg: str, rio_airport: str
) -> list[PriceResult]:
    url = _search_url(origin, destination, flight_date)
    page = context.new_page()
    result = PriceResult(
        site=SITE_NAME,
        trip_leg=trip_leg,
        rio_airport=rio_airport,
        origin=origin,
        destination=destination,
        flight_date=flight_date.isoformat(),
        url=url,
    )
    try:
        page.goto(url, timeout=config.NAV_TIMEOUT_MS, wait_until="domcontentloaded")
        _dismiss_consent(page)
        # Wait for the results (and the filter bar) to actually render before
        # touching the baggage filter - trying to click it too early was why
        # earlier runs never found the button.
        wait_for_price_text(page, config.PRICE_WAIT_TIMEOUT_MS)
        page.wait_for_timeout(config.SETTLE_WAIT_MS)
        filter_applied = _apply_checked_bag_filter(page)
        if filter_applied:
            # Prices recalculate after the filter is applied - let them settle.
            page.wait_for_timeout(config.SETTLE_WAIT_MS + 1500)
        text = page.inner_text("body")
        if filter_applied:
            # Prices on the page now already include a checked bag - no
            # need for (and no way to do) the same-line text check.
            prices = extract_prices_from_text(text)
            if prices:
                result.price_brl = min(prices)
                result.status = "ok"
            else:
                result.status = "no_price_found"
                result.note = "Filtro de bagagem despachada aplicado, mas nenhum preco reconhecido no texto da pagina."
        else:
            log.warning(
                "Nao foi possivel aplicar o filtro de bagagem despachada (%s, %s); "
                "caindo para verificacao por texto.",
                rio_airport,
                trip_leg,
            )
            apply_extracted_price(result, text, log=log)
    except Exception as exc:
        result.status = "error"
        result.note = f"{type(exc).__name__}: {exc}"
        log.exception("Falha ao buscar no Google Flights (%s, %s)", rio_airport, trip_leg)
    finally:
        save_debug_artifacts(page, SITE_NAME, rio_airport, trip_leg)
        page.close()
    return [result]
