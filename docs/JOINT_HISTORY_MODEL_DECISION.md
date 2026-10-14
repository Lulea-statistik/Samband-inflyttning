# Beslutspunkt efter gemensam historikgranskning (2026-10-14)

Underlag: [fair_joint_historical_windows.json](data/fair_joint_historical_windows.json), lyckad Actions-körning #38597144056.

## Resultat
- 3 års träning: högst 71 av 73 kandidater samtidigt kompletta; alla tre fördefinierade kontroller tillgängliga enbart för prognosår 2024.
- 5 års träning: högst 51 kandidater samtidigt kompletta; inget prognosår där alla tre kontrollerna finns.
- 10 års träning: högst 6 kandidater samtidigt kompletta; inget prognosår där alla tre kontrollerna finns.
- Kontrollerna är laggad logaritmerad folkmängd, laggad tätortsgrad och laggat regionalt centrumavstånd.

Detta är **gemensamma årstäckningskontroller**, inte omtränade modeller. Prognosåren 2023/2024 är redan studerade och kan inte ge slutlig oberoende evidens. Historisk publiceringsdag är fortfarande okänd.

## Rekommenderad metod, innan nästa regressionskörning

1. **Spår L — historiskt tillgänglig strukturmodell:** Utforma en separat teoretiskt motiverad kontrolluppsättning som har fler än ett gemensamt äldre prognosår. Byt inte automatiskt ut kontroller för att förbättra RMSE; dokumentera i förväg varför varje kontroll behövs. Pröva samma kandidater på exakt samma kommun-år.
2. **Spår B — bredare forskningsmodell:** Behåll tre kontroller och den utökade kandidatpoolen i explorativa analyser. Detta spår kan med aktuella data inte femårigt historiskt valideras på lika villkor. Ersätt inte avsaknad av temporala valideringsår med fler varianter av 2024-test.
3. **Historikförlängning:** Undersök om regionalt centrumavstånd är en tidsinvariant, geografisk kontroll som kan beräknas för tidigare år utan framtida information. Om geografidefinitionen ändrats, dokumentera det. Undersök också källhistoriken för andra arbetsmarknadsmått.
4. **Statistiskt protokoll:** Frys uppdelning efter prognosursprung, datakälla, geografiska kontroller, variabelurval och modellstorlek *före* ytterligare utfallsjämförelser.
5. **Statusregel:** 2024-fynd (LOK-stöd, fritidshus, färdigställda bostäder) är hypotesgenererande. Ingen produktionsändring utan historiskt publiceringssäker information och oberoende validering.

## Pausat arbete
SCB:s alternativa jämförelse av två färdigställandetabeller ska **inte** återupptas här; användaren har uttryckligen valt att lägga den åt sidan.

**Produktionsmodell: oförändrad.**
