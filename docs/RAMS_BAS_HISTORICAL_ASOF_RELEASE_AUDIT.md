# Publiceringstidpunkt och historisk tillgänglighet: RAMS och BAS

Status 2026-10-14: **delvis källverifierad, modellspärr kvarstår**. Underlag: [lag1-rapport](data/employment_lag1_availability_gate_status.json) ([Actions #38605851399](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38605851399)).

## Verifierade officiella uppgifter

- RAMS 2018 publicerades **november 2019** enligt SCB:s rapport om AKU-händelsen 2019: https://www.scb.se/hitta-statistik/statistik-efter-amne/arbetsmarknad/utbud-av-arbetskraft/arbetskraftsundersokningarna-tidigare-definitioner/produktrelaterat/fordjupad-information/rapport-om-aku-handelsen-2019/
- RAMS 2019 publicerades **26 november 2020** (SCB:s statistiknyhet), och SCB rekommenderar ingen rak årsjämförelse 2018–2019 p.g.a. ny källa/metod: https://www.scb.se/hitta-statistik/statistik-efter-amne/arbetsmarknad/utbud-av-arbetskraft/registerbaserad-arbetsmarknadsstatistik-rams/pong/statistiknyhet/registerbaserad-arbetsmarknadsstatistik-rams-och-registerbaserad-lonesummestatistik-lsum-2019/
- RAMS 2021 var sista RAMS-referensåret; statistiken publicerades **24 november 2022**: https://www.scb.se/am0207
- SCB:s årsredovisning 2023 anger att **BAS årsversion publicerades i november 2023 med historik tillbaka till 2020**. Därför kan dagens BAS-årsvärden 2020 och 2021 **inte automatiskt anses vara tillgängliga** för prognoser utfärdade 2021 eller 2022: https://www.scb.se/contentassets/e6e3bb34eaa84f7b9e2244283c4cc8b0/scbs-arsredovisning-2023.pdf
- SCB redovisar också att BAS finns i preliminär och slutlig version; statistikens **arbetsställebaserade** utfall kan ha annan publiceringstidpunkt än den generella BAS-årsversionen. För varje exakt OD-tabell behöver publiceringsdatum verifieras separat: https://www.scb.se/contentassets/7f87974715b0400191c6faca0b6bb17e/nr0001_2024m05_ti_a28ti2405.pdf

## Regler för as-of-godkännande

1. Ange exakt **prognosdatum** och tillåten statistikvintage, inte bara prognosår.
2. För prediktorn `lag1_sysselsatta_*_forandring_pct` för prognosår T behöver man statistik för referensåren **T-1 och T-2**. Att kalla detta lag1 innebär inte att den redan publicerats i januari T.
3. BAS-seriens 2020–2022 värden får inte sättas till 'historiskt tillgänglig' bara för att de senare backfyllts till 2020. Markera `source_release_verified=false` tills den **exakta kommunenheten/pendlingstabellen** och dess release är verifierad.
4. De redan beräknade BAS-kalibreringsfaktorerna kräver **båda överlappsåren 2020 och 2021 samt senare BAS-releaser**. Faktorerna från den nutida serien får **inte** appliceras på historiska träningsrader som om de varit kända vid prognostidpunkten; skatta om inom varje historiskt träningsfönster när detta över huvud taget blir möjligt. Alternativt klassificera historisk jämkad serie som retrospektiv **förklaringsanalys**, ej genuin historisk prognos/backtest.
5. Behåll markering av brotten **2011, 2019, 2024**, samt saknade förändringar vid regimövergång. Publiceringsspärr och brottspärr är två olika krav.
6. Experimentell retrospektiv regression utan prognosanspråk får använda dagens reviderade historiska serie om det märks explicit; den får inte jämföras mot en strikt as-of-prognos och användas för produktionsbeslut på samma villkor.

## Slutsats
Den laggade serien täcker **17 prognosår / 9 860 måttvärden**, men **0 är as-of-godkända** i nuvarande maskinella underlag. Inga gamla värden får släppas igenom enbart genom att tolka historiska kalenderår som publiceringsdatum. Utred exakt tabells release och definiera prognosdatum innan en rättvis modellkörning.

**Produktion oförändrad.**
