# Neutral omstart: urvalsprotokoll efter inventering av 80 variabler

Status 2026-10-14: **inventering slutförd, urval och produktion ej ändrade**. Källa: [maskinläsbar inventering](data/neutral_variable_pool_reboot.json) och [körning #38608305162](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38608305162).

## Avstämning
- **80 unika variabelposter**, varav 73 i äldre rättvisa kandidatpoolen, 5 äldre modellvariabler utanför denna pool, och 2 historiskt utökade RAMS/BAS-sysselsättningsserier.
- **27 tidigare använda modellvariabler** identifieras bland de 80. Tidigare modellstatus är *information för revision*, inte ett automatiskt urvalsföreträde.
- De 5 variablerna utanför poolen är `lag1_andel_20_34`, `lag1_befolkningstillvaxt_pct`, `lag1_inflyttare_medelalder`, `lag1_inflyttning_per_1000`, `lag1_utflyttning_per_1000`. De betraktas som demografiska och får inte ingå i demografiskt blind strukturmodell.
- Två nya historiska arbetsmarknadsvariabler är alternativa källhistoriker till de befintliga `lag1_sysselsatta_bostad_forandring_pct` och `lag1_sysselsatta_arbetsstalle_forandring_pct`. Dessa är **inte fyra oberoende signaler**; grupperas två och två före urval.

## Beslut före modelltest
1. Frys inventeringens variabelnamn, källfamilj, definition, tillgängliga år, mål-/läckagerisk, metodbrott, geografisk täckning, tematik och historiskt publiceringsdatum. Okänt skall förbli okänt.
2. Skapa två **separata urvalsuniversum**: (a) demografiskt blind strukturmodell och (b) prognosmodell som får använda historisk demografi. Ingen tidigare vald variabel garanteras plats.
3. Varje variabelfamilj får en rättvis jämförelse mellan gamla och nya mätmetoder. Ändrad tillgänglighet får inte misstas för högre prediktiv kvalitet: jämför kandidater på identiska tränings-/testrader och år.
4. Förhandsbesluta minimala kontrollvariabler av teoretiska skäl; de är inte modellens “vinnare”. Välj i övrigt variabler med geografiskt korsvaliderad, tidsmedveten nästlad träning. Hela förberedelsekedjan, inklusive ersättning av saknade värden och skalning, utförs enbart på träningsdata.
5. Utvärdera kollinearitet, variabelgrupper, temabalans, stabilitet mellan geografiska delmängder och närliggande år, samt om variabler överlever omval från noll. Håll modellstorlek och regularisering inom fördefinierad sökrymd.
6. **2019–2023 -> 2024** är användbart som explorativt exempel på nutida relevans, men teståret 2024 har granskats upprepade gånger och får inte användas för slutgiltigt modellval. Även 2023 är tidigare inspekterat. Bekräftelse kräver framtida orörd uppföljning eller historiska as-of-vintages med i förväg låst modell.
7. Historiska RAMS/BAS-tillväxtmått behöver en tydlig 2020-luckepolicy och as-of-kontroll. En konstant nivåkalibrering ändrar inte den procentuella tillväxten inom en regim.
8. Ingen automatisk modelloptimering, ändring i `panel.csv` eller produktionsmodell genom detta protokoll.

## Nästa arbetsordning
1. Revidera de 5 demografiska variablernas familj och grenklassificering; inventera också eventuella källfiler eller kandidater som ännu saknas i de 80.
2. Publicera familje- och metodmatris med historisk gemensam täckning per prognosår. Bedöm jämförbarhet, inte enbart förekomst.
3. Utforma en fryst pre-registrerad, lika-villkorlig selektionskörning; genomför inga nya 2024-drivna val utan separat beslut.

**Produktionsmodellen förblir oförändrad.**
