# Status – kortsiktig månadsmodul, kandidatfamilj 1

Datum: 2026-10-19

## Beslut

Kandidatfamilj 1 får **inte** produktionsstatus som kortsiktig prognoskomponent.

Den frysta långsiktiga core-4-modellen ändras inte.

För den separata månadsmodulen behålls tills vidare den säsongsnaiva prognosen — samma framtida kalendermånader föregående år — som benchmark att slå.

## Resultat

### BAS-only robusthet

Den mest lovande BAS-varianten var arbetsställe + bostad, årsförändring (`bas_yoy`).

Vid +3 månader slog den säsongsnaiv RMSE marginellt och konsekvent över Ridge-alpha:

| Ridge alpha | BAS YoY mot säsongsnaiv RMSE |
|---:|---:|
| 3 | -0,37 % |
| 10 | -0,50 % |
| 30 | -0,24 % |

För längre horisonter blev BAS YoY sämre:

| Horisont | alpha 3 | alpha 10 | alpha 30 |
|---|---:|---:|---:|
| +6 mån | +4,33 % | +4,48 % | +4,94 % |
| +9 mån | +6,52 % | +6,99 % | +8,03 % |
| +12 mån | +6,26 % | +7,05 % | +8,72 % |

Övriga BAS-representationer var genomgående svagare i RMSE.

## Tolkning

- BAS innehåller sannolikt viss **mycket kort** signal, främst kring +3 månader.
- Den signalen avtar eller blir skadlig när prognoshorisonten förlängs.
- Den tydliga förbättring som syntes efter 2025 är inte tillräcklig grund för att välja modellen, eftersom pre-2025-resultaten är klart sämre.
- BNP och asylstatistik bidrog inte med stabil inkrementell prognoskvalitet i kandidatfamilj 1.
- En enkel lokal momentumjustering av inflyttningen fungerade ännu sämre och ska inte användas.

## Status per variabelfamilj

- **BAS årstakt:** behåll som diagnostisk / möjlig +3-månaderssignal.
- **BAS 3m/6m momentum:** inte godkänd.
- **BAS arbetsställe–bostad-gap:** inte godkänd.
- **BNP-indikator:** inte godkänd som direkt prognosfeature i denna version.
- **Asylsökande:** inte godkänd som direkt prognosfeature i denna version.

## Nästa gate

För användarens primära mål 9–12 månader bör nästa kandidatfamilj tillföra information som ligger närmare framtida lokal migration än generell samtidssysselsättning.

Prioriterade nya familjer:
1. Arbetsförmedlingen: arbetslöshet, varsel och nyanmälda platser.
2. Bostads-/byggindikatorer med månads- eller kvartalsfrekvens.
3. Företagsdynamik: konkurser, nyföretagande eller arbetsställeförändringar.
4. Studie-/antagningssignaler inför terminsskiften.
5. Eventuella andra lokala ledande indikatorer med dokumenterad publiceringslagg.

Alla nya familjer ska testas mot exakt samma säsongsnaiva benchmark och med rolling-origin utan framtidsläckage.
