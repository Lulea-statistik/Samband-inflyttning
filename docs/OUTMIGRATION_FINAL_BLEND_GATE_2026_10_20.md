# Utflyttning – slutlig huvudspecifikation efter blend-gate

Datum: 2026-10-20

## Beslut

Den årliga huvudmodellen för utflyttning promoveras till en viktad blend av två lag1-modeller:

```
forecast_utflyttning_per_1000 =
    0.25 * forecast_lag1_3y
  + 0.75 * forecast_lag1_10y
```

Där båda komponenterna använder samma enda prediktor:

`lag1_utflyttning_per_1000`

Skillnaden mellan komponenterna är endast träningsfönstret:

- kort komponent: 3 års rullande träning
- lång komponent: 10 års rullande träning

Inflyttningsmodellen ändras inte.

## Varför blend?

På identiska rolling-origin-år 2013–2024 och 290 kommuner:

| Modell | RMSE |
|---|---:|
| 3 år | 5.7025 |
| 10 år | 5.6885 |
| **25/75 blend** | **5.6832** |

Blenden har lägre pooled RMSE än båda komponenterna.

Bootstrap över kommuner:

- sannolikhet att blend slår 3-årsmodellen: **97.0 %**
- sannolikhet att blend slår 10-årsmodellen: **94.8 %**

## Luleå

På samma 2013–2024-period:

| Modell | RMSE per 1 000 |
|---|---:|
| 3 år | 2.4234 |
| 10 år | **2.3828** |
| 25/75 blend | 2.3846 |

Blenden är endast cirka **0.074 %** sämre än den bästa Luleå-referensen och klarar därmed den förhandsdefinierade toleransen på 0.5 %.

## Promotion-gate

Samtliga krav klarades:

- nationell RMSE bättre än 3 år: ja
- nationell RMSE bättre än 10 år: ja
- bootstrap-sannolikhet >90 % mot 3 år: ja
- bootstrap-sannolikhet >90 % mot 10 år: ja
- Luleå inom 0.5 % från bästa referens: ja

## Modellstatus

Huvudspecifikation:
- target: `utflyttning_per_1000`
- prediktor: `lag1_utflyttning_per_1000`
- komponent A: 3 års rullande träning
- komponent B: 10 års rullande träning
- blend: **25 % A + 75 % B**

Referenser:
- 3-årsmodellen behålls som kort-historisk komponentreferens
- 10-årsmodellen behålls som lång-historisk känslighetsreferens

Nyare strukturvariabler promoveras inte. Ingen av dem klarade challenger-gaten 2022–2024.

## Viktig metodnot

Blenden förbättrar pooled accuracy endast marginellt. Promotionen motiveras därför inte av en stor effekt utan av att förbättringen:

1. går i rätt riktning mot båda referenserna,
2. stöds av bootstrap,
3. inte innebär materiell försämring för Luleå,
4. kombinerar kort och lång historik utan att introducera ytterligare variabler.

Nästa steg är produktionsmässig as-of/source-vintage-granskning samt slutlig kontroll av 2024/aktuell prognos innan modellen används operativt.
