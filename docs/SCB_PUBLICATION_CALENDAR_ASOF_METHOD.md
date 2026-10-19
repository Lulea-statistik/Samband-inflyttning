# SCB publiceringskalender – source-of-truth för as-of-regler

Datum: 2026-10-19

## Källhierarki

As-of-regler ska i första hand bygga på faktisk publiceringsinformation, inte fasta schablonlaggar.

Prioritet:
1. SCB:s publiceringskalender
2. SCB:s statistik-/ämnessidor och Statistikdatabasens uppdateringsdatum
3. statistikportalen.scb.se när titel eller metadata anger publiceringsdatum
4. återkommande års-/månadsmönster härledda från närliggande år
5. konservativ fallback

Varje publiceringsdatum ska klassas som:
- `observed`
- `inferred_annual_pattern`
- `conservative_fallback`

## Befolkning och flyttningar

Observerade slutliga helårspubliceringar:
- 2023 publicerades 2024-02-22
- 2024 publicerades 2025-02-21
- 2025 publicerades 2026-02-24

Det stödjer regeln att slutlig befolkning/flyttning för Y-1 är tillgänglig vid en prognosorigin efter SCB:s aprilprognos år Y.

## SCB:s riksprognos som prognosankare

Historiska publiceringsdatum för Sveriges framtida befolkning används som faktisk tidsankare.

Exempel:
- 2022: 13 april
- 2023: 18 april
- 2024: 25 april
- 2025: 11 april
- 2026: 16 april

Historiska backtest ska därför inte använda ett enda fast datum för alla år. Forecast origin representeras som ett fönster 7–14 dagar efter årets faktiska riksprognospublicering, med 10 dagar som standardsensitivitet.

## Bostadsbestånd

Bostadsbeståndet 2025 publicerades 17 april 2026. För år där exakt historisk publiceringsdag saknas får samma säsongsmönster användas endast som inferens.

Om ett bostadsvärde inte med säkerhet var publicerat före årets forecast origin ska det betraktas som otillgängligt.

## BAS

Observerade exempel 2026:
- maj → 28 juli
- juni → 28 augusti
- oktober → 22 december

Det visar ungefär två månaders eftersläpning. Exakta kalenderdatum ska användas när de finns; lag 2 månader kvarstår som konservativ pseudo-realtime-regel där exakta historiska datum saknas.

## Återkommande publiceringar

När statistikportalen eller en SCB-sida anger att en källa för referensår Y publicerades vid en viss tidpunkt kan nästa års publicering antas ligga ungefär samma period endast som `inferred_annual_pattern`.

En infererad dag får aldrig behandlas som ett observerat historiskt faktum.

## Nästa steg

Bygg en source-specific as-of-tabell per forecast origin som anger:
- variabel
- referensperiod
- publiceringsdatum
- kvalitet
- källa
- tillgänglig/ej tillgänglig vid forecast origin

Den tabellen ska sedan styra core-4 + månadsmodulens historiska backtest.
