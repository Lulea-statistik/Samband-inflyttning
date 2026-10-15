# Modellstorlek: jämförelse av Jenks, knee, 1-SE och lägsta RMSE

Datum 2026-10-15. Forskningsresultat från [Actions #38751818197](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38751818197). [Maskinresultat](data/neutral_model_size_method_comparison.json).

| Träningsspår | Minimum RMSE | 1-SE | Knee | Jenks |
|---|---:|---:|---:|---:|
| Blind 2019–2023 | 8,588 (40–51) | 8,622 (40–51) | 8,727 (40) | 11,058 (14–40) |
| Blind 2021–2023 | 8,210 (60–73) | 8,145 (60) | 10,255 (14–30) | 10,949 (6–60) |
| Prognos 2019–2023 | 5,292 (40–56) | 5,340 (20–56) | 5,336 (10–40) | 5,458 (14–30) |
| Prognos 2021–2023 | 5,054 (40–60) | 5,197 (40–60) | 5,125 (40–60) | 5,358 (14–60) |

Parentes: minsta och största modellstorlek vald bland fem geografiska ytterfoldar. Samtliga modeller använder träningsexklusiv univariat korrelationsscreening och standardiserad Ridge med fast alpha=10. Storlekskandidater 4, 6, 10, 14, 20, 30, 40, 60, 80 klipps vid aktuell kandidatpool.

## Beslut
- **1-SE** är den mest lovande principen för en förenklad modell, men bör inte upphöjas till produktionsregel utan oberoende validering. Den blir stundtals lika stor som minimi-RMSE-valet.
- **Jenks/natural breaks** tillämpades på marginala RMSE-förbättringar över modellstorlekar; det är en heuristik och gav svagare och instabila resultat. Detta diskvalificerar inte Jenks för andra diagnostiska syften (t.ex. uppdelning av variabelbetydelser).
- **Elbow/knee** gav samma storlek (40) i alla fem foldar i blind femårsspår, men fallerar som generell metod i blind treårsspår.
- Inget stöd för generell maxgräns 10, 14 eller 20; framgångsrika modeller behöver ofta 40–60 kandidater med den aktuella enkla screeningmodellen.
- Storlek är inte likvärdigt med antal oberoende faktorer eller effektiv frihetsgrad: högt korrelerade och regulariserade variabler kräver särskild redovisning.
- Fyra metoder utvärderades på **redan många gånger granskade år och geografiska foldar**. Utfallet är explorativt. Att välja bästa metoden från deras yttre CV och därefter hävda samma yttre CV som orörd kontroll vore metodläckage.
- Nästa utvecklingssteg ska jämföra *förregistrerade* 1-SE och alternativ på temporalt separerade år samt granska om variabelurvalet drivs av proxy-korrelation. Gör olika slutsatser om explanatory blind respektive forecast.
- Befintlig produktionsmodell ändras inte.

## Två likprioriterade leveranser
**Förklaring:** dokumentera hur många representativa strukturfamiljer modellen behöver, pröva partiella bidrag och kontrollvariabler utan historiska demografiska utfallsvariabler.

**Prognos:** jämför tillgänglig historisk data och rolling-origin, och särskilj aktuellt retrospektivt experiment från verkligt as-of-test.
