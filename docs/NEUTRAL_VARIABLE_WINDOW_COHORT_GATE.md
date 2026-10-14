# Neutral omstart: täckningsgrind och jämförbara kohorter

Datum 2026-10-14. Underlag: [80-variable data gate](data/neutral_80_candidate_data_gate.json) från [Actions #38610921275](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38610921275). **Endast metoddokumentation, inget modellurval eller produktionsbyte.**

## Fullständiga kommun-år per träningsperiod

| Träningsår inför explorativt utfall 2024 | Variabler med 290/290 kommuner varje år |
|---|---:|
| 2019–2023 (5 år) | **56 av 80** |
| 2020–2023 (4 år) | 58 av 80 |
| 2021–2023 (3 år) | **78 av 80** |
| 2022–2023 (2 år) | **80 av 80** |

Alla 80 kandidater finns i data för 2024. Kandidaternas underlag kan vara retrospektivt, och täckning är **inte** ett publicerings-/as-of-godkännande.

## Rekommenderad analysdesign
1. **Huvudspår: fem år 2019–2023** med 56 komplett observerade kandidater. Inom spåret jämförs baslinje och nya modeller på exakt samma kommun-år och tränings-/testperiod.
2. **Utmanarspår: tre år 2021–2023** med 78 kandidater för att ge de kortare serierna rättvisa villkor. De två historiska RAMS/BAS-kandidaterna är kompletta under dessa tre år. Jämför inte 3-årsmodellens resultat direkt med 5-årsmodellens resultat och tillskriv skillnader enskilda variabler: tidsunderlagen är olika.
3. **Känslighet: två år 2022–2023** med 80 kandidater, inklusive befintliga korta BAS-tillväxtserier. För kort period för huvudurval; statistisk instabilitet förväntas. Behandla utfall som hypotesgenererande.
4. Ingen artificiell ifyllnad av 2020:s saknade sysselsättningstillväxt får göras som om det vore observerad statistik; separat dokumenterad imputering i train-only-steg kan undersökas som känslighet men inte kallas en observerad femårsserie.
5. Befintliga och nya variabler skall konkur­rera under samma kandidatgrind. Historisk modellstatus ger ingen förtur. Bevara strukturmodellens demografiska exklusioner och prognosgrenens bredare kandidatlista.
6. 2024 har granskats upprepade gånger och får endast användas explorativt. För prognosvalidering krävs separat förhandslåst, opåverkat test och verifierade källors tillgänglighet före prognostidpunkt.

## Numeriska definitionskontroller
- Arbetskraftsdeltagande och utanför arbetskraften summerar till exakt 100 i 870 tillgängliga jämförbara observationer; definitionskod/SCB-nämnare återstår att kontrollera innan formell identitetsklassning.
- Tre logtransformerade mått och nivåmått har monoton men inte likvärdig linjär representation.
- Snöskoterandelar nästan linjärt identiska men inte exakt samma värde.
- Gymnasieinriktningar summerar till mellan 65,517 och 98,785 i observerade jämförbara data: ej komplementandelar.

## Spärrar före urval
- Bestäm fördefinierade geografiska och tidsmässiga splitar för respektive spår samt vilka kontrollvariabler som skall vara teoretiskt tvingande.
- Granska källvintages och dolda omkodningar/definitioner för korrelerade mått.
- Om flera familjemedlemmar tävlar: samma träning, samma missingnessprincip, samma feature-budget och samma modellklass.
- Ingen automatisk ändring av produktion, publik rapport eller rådata.
