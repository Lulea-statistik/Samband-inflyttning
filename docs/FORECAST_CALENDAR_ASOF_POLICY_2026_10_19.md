# Prognoskalender och as-of-logik för kortsiktig månadsmodul

Datum: 2026-10-19

## Praktisk prognoskalender

Prognosen ska inte modelleras som om kalenderår och statistiska år sammanfaller.

### Befolkning
- Slutlig befolkningsstatistik för föregående kalenderår publiceras normalt av SCB omkring mitten av februari året efter.
- Det innebär att exempelvis utfall för kalenderår Y blir definitivt känt först omkring februari Y+1.

### Prognosorigin
- Kommunprognosen görs normalt cirka 1–2 veckor efter att SCB publicerat sina riksprognosantaganden i mitten av april.
- En realistisk standardorigin är därför **slutet av april**.

Vid denna origin är:
- slutlig befolkning för föregående kalenderår normalt känd,
- vissa övriga årsvariabler kända med sina respektive publiceringslaggar,
- SCB:s aktuella nationella prognosantaganden kända,
- utfallet för innevarande kalenderår ännu inte känt.

### Prognoshorisont
En prognos gjord i slutet av april år Y omfattar återstoden av år Y fram till december samt efterföljande år enligt vald prognoshorisont.

Utfallet för år Y blir i normalfallet inte slutligt observerbart förrän omkring mitten av februari år Y+1.

## Konsekvens för backtest

Varje historisk forecast origin ska efterlikna en verklig prognoskörning.

För en origin i slutet av april år Y får modellen endast använda variabler som hade publicerats senast vid denna tidpunkt.

Det innebär att varje årsvariabel behöver en explicit as-of-regel:

1. referensår,
2. faktisk eller konservativ publiceringsmånad,
3. vilket värde som var senaste tillgängliga vid prognosorigin,
4. om värdet var preliminärt eller slutligt.

## Befolkningsregel

Vid prognosorigin april Y får slutlig befolkningsstatistik för Y-1 användas.

Slutligt utfall för Y får däremot inte användas eftersom det publiceras först omkring februari Y+1.

## Månadsmodulen

Månadsvariabler som BAS ska behandlas separat från årsvariabler.

För varje forecast origin används endast senaste publicerade månad enligt en konservativ publiceringslagg, exempelvis lag 1 eller lag 2 månader.

`rates_25_29` har redan klarat common-origin-test med lag 1–2 månader.

## Makro + säsong

Makrointegrationen ska därför byggas runt en årlig forecast origin i april, inte runt kalenderårsskiften.

För varje historiskt år Y:

1. skapa fryst core-4-prognos med information tillgänglig vid prognosorigin i april Y,
2. prognostisera återstående månader maj–december Y,
3. vid längre horisont fortsätta över efterföljande kalenderår utan att använda framtida årsutfall,
4. fördela års-/periodnivån över månader med en säsongsprofil beräknad enbart från tidigare observerade månader,
5. testa `rates_25_29` som residualkorrigering ovanpå denna makro+säsong-baseline.

## Valideringsdatum

När prognosen för kalenderår Y utvärderas ska den betraktas som fullt verifierbar först när slutlig befolkningsstatistik för Y publicerats omkring februari Y+1.

Detta skiljer:
- forecast origin,
- forecast period,
- outcome availability date.

Dessa tre datum får inte blandas ihop i backtestet.
