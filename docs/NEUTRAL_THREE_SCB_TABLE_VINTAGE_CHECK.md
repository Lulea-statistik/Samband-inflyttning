# Exakta tabeller: kontroll av belägg och historiska dataversioner

Datum: 2026-10-15. Syfte: skilja identiteten på en tabell från första tillgängliga versionen av en viss årsuppgift.

| Konstant i projektet | Full tabellidentitet (från Python) | Dokumentationsbelägg | Arkiverad exakt årsvintage? | As-of-status |
|---|---|---|---|---|
| POPULATION_URL | BE/BE0101/BE0101A/BefolkningNy | SCB:s PxWeb-dokumentation från 2022 använder själv BefolkningNy som exempel på tabell och API-adress. https://www.scb.se/globalassets/vara-tjanster/px-programmen/pxweb-configuration_2022.pdf | Nej | Blockerad |
| MIGRATION_URL | BE/BE0101/BE0101J/Flyttningar97 | Exakt tabell-ID belagt i `scripts/build_analysis.py`. Publiceringsnyheter om flyttningar beskriver *statistiken*, inte första databasversionen av Flyttningar97. | Nej | Blockerad |
| HOUSING_URL | BO/BO0104/BO0104D/BO0104T04 | Exakt tabell-ID belagt i `scripts/build_analysis.py`; statistiknyhet för bostadsbestånd per 2023-12-31 publicerades 2024-04-18, men visar inte vilket datum BO0104T04 fick just de kommunvärdena. | Nej | Blockerad |

## Kontroll mot statistikproduktens släppdatum

För referensåret **2023** finns tidigare dokumenterade produktankare: befolkningsstatistikens helår 2023 den 2024-02-22 och bostadsbestånd 2023 den 2024-04-18; se `NEUTRAL_SCB_FIRST_RELEASE_EVIDENCE_2026_10_15.md`. Dessa datum är inte ersättningar för fryst tabellvintage. Ett separat publicerat länsmaterial om flyttningar den 2024-03-22 **får inte tolkas som första släppdatum för kommunala Flyttningar97**.

För ett prognosursprung 2024-01-01 kan inte sen publicerad *ny* helårsinformation tas in i ursprungsscenariot. För ett ursprung 2024-05-01 behöver vi fortfarande exakt vintage och eventuella senare revisioner. Det finns ännu inga certifierade as-of-kolumner bara för att årgångar syns i dagens API.

## Vad som behövs för nästa statusändring

1. En arkiverad PxWeb-/API-ögonblicksbild eller officiell SCB-ändringshistorik som visar tabellens värden och tillgänglighetsdatum.
2. Kommunvis täckning i just den äldre dataversionen, inte bara i dagens panel.
3. Kodkedjan från respektive tabellmått till `lag1_`-variabeln och en uttrycklig prognosbrytpunkt.
4. Kontroll av skillnader mellan dåvarande och nuvarande värden samt eventuella metodbrott.

**Ingen variabel as-of-godkänd, ingen ny tidsregression startad och ingen produktionsändring.**
