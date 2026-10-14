# Val av modellstorlek utan historisk förtur

Beslutad forskningsprincip 2026-10-14. Utvärderingen av 2024 är redan inspekterad och får inte användas för att välja hyperparametrar eller ge oberoende produktionsgodkännande.

## Huvudregel
Välj inte godtyckligt 6, 10 eller 14 variabler. Använd **nästlad gruppkorsvalidering** och **1-SE-regeln**: välj den minsta kandidatstorleken vars medelfel i inre gruppkorsvalidering är högst (minsta medelfel + ett standardfel uppskattat över valideringsfoldar). Rapportera både vald storlek och bästa medelfel, inklusive skillnaden.

- Yttre validering håller undan hela kommuner (samtliga år för samma kommun). Inre validering på yttre träningskommuner väljer antal och variabler.
- Variabelranking, korrelationsfilter, transformationer och skalning görs alltid inne i respektive träningsfold.
- Obligatoriska kontroller: log folkmängd, tätortsgrad, avstånd regionalt centrum. Deras antal ska redovisas och ingå i taket. Övriga obligatoriska kontroller måste motiveras före experimentet.
- Samma kandidatstorlekar, inre/yttre indelning och modellklass för ursprunglig och utökad pool. Alla kandidater kontrolleras för läckage och faktisk publiceringstid innan produktion.
- Utvärdera också urvalsstabilitet per variabel och tema. Antalet valda variabler är inte samma sak som modellens effektiva frihetsgrader (exempelvis splines/dummies eller regularisering).
- Principen bör testas separat för prognosmodellen och den demografiskt blinda modellen.
- **Begränsning:** endast två kompletta träningsår i denna BAS-delanalys; 290 kommuner är inte 870 helt oberoende observationer. 1-SE från få beroende foldar är osäkert. Bekräfta på framtida orört år före produktionsbeslut.
- Om standardfel med få foldar blir för opålitligt ska resultatet klassas som explorativt, och en stabilitetsanalys med upprepade geografiskt grupperade uppdelningar genomföras innan beslut.

## Mått
Primärt RMSE på undanhållna kommuner. Redovisa MAE, spridning mellan foldar, Luleås fel separat, antal valda variabler och frekvenser. För modelljämförelse på samma kommuner kan parade felskillnader redovisas; behandla inte fem foldar som ett stort oberoende urval.

## Kriterium för slutligt modellval
En mindre modell föredras när mer komplexa modeller inte förbättrar utvärdering inom rimlig osäkerhet. Teoretiskt motiverade kontrollvariabler behöver inte var för sig förbättra RMSE, men måste vara fördefinierade och motiverade. Inga produktionsändringar genom dessa forskningstester.
