# Familjemedveten neutral modell: fryst testplan 2026-10-15

## Utgångspunkt
Tidigare geografiska tester visade att den stora neutrala modellen gav lägre RMSE, medan modeller med högst 20 variabler inte behöll hela förbättringen. Det är en hypotes om modellkomplexitet, inte ett godkännande för produktion.

## Mellanmodell
1. Använd samma 290 SCB-kommuner och samma mål: inflyttning per 1 000 invånare.
2. Testa separat 2019–2023 (56 kandidater) och 2021–2023 (78 kandidater), med separata demografiskt blinda och prognostillåtande urval.
3. Använd fem yttre och tre inre geografiska kommunfoldar. Inga observationer från samma kommun får finnas i både träning och test.
4. Behandla redan definierade alternativa representationer som familjer: småhuspris, fritidshus, centrumavstånd, arbetskraftsdeltagande/utanför arbetskraften, snöskoterandel och gymnasieinriktning. Detta är en experimentell familjeprior, inte ett påstående att alla är matematiska dubbletter.
5. Familjeval görs endast inom respektive träningsfold. Bredare korrelationsnätverk får inte automatiskt reduceras till en variabel.
6. Utvärdera i förväg fastställda regulariseringsnivåer och modellstorlek inom inre CV; visa RMSE, MAE och aktiva variabler i yttre CV. Låt tidigare valda och nya kandidater följa samma process.
7. Gör en separat jämförelse med korrekt rekonstruerad befintlig produktionspipeline, inte bara dess omtränade variabellista.

## Separat tidsgrind
Geografisk CV på samma redan använda år är en explorativ jämförelse. Varken 2023 eller 2024 utgör oberoende sluttest. En genuin tidsvalidering kräver låsta prognosursprung och verifierade historiska källvintages; utan dem får bara retrospektiva associationsresultat rapporteras.

## Beslutsregler
Ingen produktionsmodell ändras automatiskt. Ingen serie med ofullständigt observerad 2020-tillväxt behandlas som fullständig. En efterhandsförbättring på redan använda testår räcker inte för att välja slutmodell.
