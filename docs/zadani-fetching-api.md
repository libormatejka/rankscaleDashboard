# Fetching API

Z rankScale API je třeba stáhnout data ohledně využití promptů v AI enginech a hlavně metriky z odpovědí.

### Příklad promptu:
Která banka nabízí nejlepší úvěr ze stavebního spoření?

### Answer:
Nejvýhodnější úvěr ze stavebního spoření v roce 2026 aktuálně nabízí MONETA Stavební Spořitelna s úrokovou sazbou od 3,99 % a bonusy až 8 500 Kč. Velmi konkurenceschopné podmínky má také Česká spořitelna (Buřinka) a ČSOB Stavební spořitelna.[1][2][3]Banky.cz. Srovnání nejlepších stavebních spoření s úvěrovým tarifem 2026 | Banky.czE15.cz. Nejvýhodnější stavební spoření 2026: Srovnání bank a úroků | e15.czTOP.CZ. Nejlepší stavební spoření: Srovnání za červen 2026 - TOP.CZ

## Zadání
Potřebuji stahovat data z nástroje, abych mohl vyhodnotit úspěšnost své značky v odpovědích na prompty. Potřebuji v datech mít vždy:

- prompt
- answer
- metriky (visibility, sentiment, citations)
- datum
- ai enginy
- topic
- tags
- competitors

Potřebuji zároveň vymyslet, jak stahovat data - potřebuji mít i historicka data (backfill import) + i denní append pomocí jobu v github actions.

Logika stahování dat by měla být co nejjednodušší. Tento script má plnit fázi Extraktu, tedy plnit L0 vrstvu daty.

## Report
Report z těchto dat má zadání v report-setup.md. Data by tedy měla splňovat všechna potřebná kritéria, aby report šel vytvořit.

## Transformace
Transformace dat je potom pomocí tranformačních query do L1 (případně L2) tabulek, aby do reportu šly už připravené tabulky.

## Dotazy a odpovědi

**Čistý start nebo reuse?**
Reuse — existující raw_/L1_/L2_ tabulky a GitHub Actions zůstávají. Extract script upraven.

**Backfill — jak daleko?**
Parametr `BACKFILL_WEEKS` v GitHub Actions (počet týdnů zpět). Pro historii od února 2026 použij `BACKFILL_WEEKS=22`. Výchozí (prázdné) = jen aktuální týden.

**Granularita timeline?**
Po týdnech. Script běží denně, ale freshness check zajistí že data zapíše jen když Rankscale vytvořil nový snapshot (nový `lastSnapshotAt`). Bez zbytečných duplicit.

**Competitors — jen metriky nebo i texty?**
Metriky competitors jsou v `raw_brand_snapshots` (visibility, sentiment, rank per prompt). Texty odpovědí jsou v `raw_answer_texts` — obsahují plnou AI odpověď za celý prompt, ne per brand.

**Více brandů?**
Stahujeme vždy pro všechny brand_id. V reportu lze filtrovat per brand přes `owning_brand_id`.

