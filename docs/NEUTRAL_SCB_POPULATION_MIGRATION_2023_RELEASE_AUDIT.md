# SCB publiceringsbelägg: befolknings- och flyttningsstatistik 2023

Granskning: 2026-10-15. Detta är en begränsad källgranskning av officiella SCB-publikationer och inte ett påstående om att modellkolumnernas ursprungsvintages har återskapats.

## Direkt belagda uppgifter

| Produkt och årgång | Publiceringsdag | Primärkälla | Vad belägget faktiskt visar |
|---|---|---|---|
| Befolkningsstatistik, helåret 2023 | **2024-02-22** | [SCB Befolkning 2024 – artikelsamling](https://www.scb.se/contentassets/30ffc37d07c64c1e8e4064bfff7952ac/be0701_2024a01_br_be51br2406.pdf) | SCB anger uttryckligen att helårstexten om 2023 publicerades denna dag. Inte bevis på exakt innehåll i API-tabellen BefolkningNy den dagen. |
| Flyttningar under 2023, länsanalys | **2024-03-22 kl 08** | [SCB Statistiknyhet – fler inflyttare än utflyttare i åtta län](https://www.scb.se/hitta-statistik/statistik-efter-amne/befolkning-och-levnadsforhallanden/befolkningens-sammansattning-och-utveckling/befolkningsstatistik/pong/statistiknyhet/befolkningsstatistik-helaret-20232/) | Datum för *denna artikel* och dess länsfördelning. Detta får **inte** användas som belägg för första publiceringsdag för alla kommunala flyttningsvärden i `Flyttningar97`; de kan ha publicerats tidigare. |

## Viktig skiljelinje
- *Referensår* 2023 anger vilken period statistiken beskriver.
- *Nyhetens publiceringsdatum* anger när just den presentationen släpptes.
- *Tabellens först publicerade vintage* kräver särskilt databas-/arkivbevis.
- *Modellvariabelns as-of-godkännande* kräver dessutom korrekt transformation, ursprungsdatum och revisionshantering.

## Kandidatkoppling att kontrollera
- `POPULATION_URL`: `BE0101A/BefolkningNy`. Undersök `lag1_log_folkmangd` och andra föregående-årsvärden med avseende på lagg och datum.
- `MIGRATION_URL`: `BE0101J/Flyttningar97`. Undersök resultatvariabel `inflyttning_per_1000` och demografiskt tillåtna laggade variabler; **förhindra att flyttningsutfall för målåret används på prognosursprunget**.
- `HOUSING_URL`: `BO0104D/BO0104T04`. Publiceringsankaret för bostadsbestånd per 31 december 2023 enligt tidigare [granskning](NEUTRAL_SCB_FIRST_RELEASE_EVIDENCE_2026_10_15.md) är **18 april 2024**; kontroll av exakta tabellårgångar återstår.
- SCB anger att tidigare preliminära befolkningssiffror kan revideras på grund av sena aviseringar: [SCB första halvåret 2024](https://www.scb.se/hitta-statistik/statistik-efter-amne/befolkning-och-levnadsforhallanden/befolkningens-sammansattning-och-utveckling/befolkningsstatistik/pong/statistiknyhet/befolkningsstatistik-forsta-halvaret-2024/).

## Beslut
Ingen variabel markeras som exakt historiskt as-of-verifierad utifrån dessa statistiknyheter. Nästa kontroll ska vara tabell-/versionsspecifik och utgå från tydligt deklarerade prognosursprung, t.ex. 2024-01-01 respektive 2024-05-01. 2023 och 2024 är sedan tidigare granskade modellår och inte orörda bekräftelsetest.

Produktionsmodellen är oförändrad.
