# Utflyttning – produktionsstatus 2026-10-20

## Huvudspecifikation

Den valda årliga utflyttningsmodellen är:

```
forecast_utflyttning_per_1000 =
    0.25 * forecast_lag1_3y
  + 0.75 * forecast_lag1_10y
```

Båda komponenterna använder endast:

`lag1_utflyttning_per_1000`

Komponentfönster:

- 3 år
- 10 år

## Produktionsstatus

### Modell- och metodstatus

- statistisk promotion-gate: **godkänd**
- metoddefinition: **verifierad**
- policybaserad annual as-of: **verifierad**
- forecast-origin-regel: **1 april eller senare**
- SCB-källor:
  - BE0101J/Flyttningar97
  - BE0101A/BefolkningNy
- inflyttningsmodellen: **oförändrad**

Den årliga utflyttningsspecifikationen är därmed **produktionsmässigt användbar inom den verifierade forecast-origin-regeln**.

## Begränsningar

Certifieringen bygger på SCB:s policy för slutliga helårsdata och gäller inte:

- forecast origins före 1 april,
- preliminär månads- eller kvartalsstatistik,
- framtida metodbrott eller revisionspolicyändringar hos SCB.

Någon exakt arkiverad PxWeb-cell för varje historiskt år har inte återfunnits. Det behövs inte för denna policybaserade final-annual-certifiering, men bör fortsatt dokumenteras som begränsning.

## 2025 untouched validation

2025-prognosen är fryst före outcome:

- 290 kommuner
- inga 2025-utfall lästa eller frågade efter
- tränings- och prediktionsfiler hashade
- Luleå blendprognos: **46.6958682408 per 1 000**

Frysmanifest:

`docs/data/preoutcome_2025_outmigration/manifest.json`

När SCB publicerar 2025 års slutliga data körs:

1. `Build SCB 2025 untouched outmigration outcome`
2. `Score untouched 2025 outmigration outcome`

Outcome-steget får inte läsa frysta modeller eller prognoser. Scorern får inte refitta, retuna eller välja om modellen.

## Tolkning

2025-testet är en **extern slutlig kvalitetsbekräftelse**, inte ett krav för att använda den redan verifierade årsmodellen inom dess definierade forecast-origin-regel.

Om 2025-resultatet avviker kraftigt ska det utlösa granskning, inte automatisk omträning eller promotion av en challenger.
