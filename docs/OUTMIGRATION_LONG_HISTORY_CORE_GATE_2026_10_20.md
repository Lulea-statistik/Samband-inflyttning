# Utflyttning – slutlig gate för långhistorisk kärna

Datum: 2026-10-20

## Beslut

Den långhistoriska kärnan för utflyttning sätts till:

- mål: `utflyttning_per_1000`
- prediktor: `lag1_utflyttning_per_1000`
- träningsfönster: **3 år**
- 290 kommuner
- rolling-origin
- 10 år behålls som obligatorisk känslighetsreferens
- inflyttningsmodellen ändras inte

Detta är en forsknings-/modellgate och innebär inte någon tyst ändring av produktion.

## Varför 3 år?

På gemensamma forecast-år 2013–2024:

| Fönster | RMSE | MAE | Bias | År bäst |
|---|---:|---:|---:|---:|
| 3 år | 5.7025 | 4.0675 | +0.2045 | 6/12 i fyrvägsjämförelsen |
| 5 år | 5.7134 | 4.0615 | +0.1779 | 1/12 |
| 6 år | 5.7104 | 4.0599 | +0.1795 | 2/12 |
| 10 år | 5.6885 | 4.0431 | +0.2020 | 3/12 |

Den separata 3-vs-10-gaten gav:

- 3 år bättre i **8 av 12 år**
- 10 år bättre i 4 av 12 år
- total RMSE för 3 år är bara **0,246 % sämre** än 10 år
- förhandsdefinierad praktisk likvärdighetsgräns: **0,5 %**

Därför behandlas fönstren som praktiskt likvärdiga i total RMSE och 3 år väljs på bättre år-för-år-konsistens.

## Viktig reservation

Valet av 3 år ska inte beskrivas som att 3 år är entydigt bättre.

Den parade kommunbootstrappen för skillnaden i RMSE 3 år vs 10 år gav:

- median: +0,241 %
- 95 % intervall: ungefär -0,218 % till +0,747 %
- sannolikhet att 3 år har lägre total RMSE: cirka 15,2 %

Det betyder att **10 år fortfarande har ett svagt övertag i pooled accuracy**, medan 3 år valts för bättre temporal konsistens enligt den förhandsdefinierade beslutsregeln.

## Variabelgate

`lag1_andel_20_34` promoveras inte till kärnan.

Skäl:
- liten genomsnittlig RMSE-förbättring
- inte tillräckligt stabil år för år
- 6-årsfönstret vann bara 9 av 16 år = 56,3 %, under 60 %-gaten

Övriga strukturvariabler med kort historik, exempelvis fritidshusmått, hålls utanför långhistorisk kärna och får endast testas som separata challengers.

## Låst referens

Primär långhistorisk utflyttningsreferens:

`utflyttning_per_1000 ~ lag1_utflyttning_per_1000`

med 3 års rullande träningsfönster.

Känslighetsreferens:

samma modell med 10 års träningsfönster.

Nästa challenger måste slå 3-årskärnan utan att förlora robusthet mot 10-årsreferensen.


## Senare promotion

Se `docs/OUTMIGRATION_FINAL_BLEND_GATE_2026_10_20.md`. Den tidigare 3-årskärnan ersätts som huvudspecifikation av en 25/75-blend av 3- och 10-årsmodellerna efter godkänd promotion-gate. 3-årsmodellen kvarstår som komponentreferens.
