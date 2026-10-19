# Status – BAS arbetsmarknadsgrader 25–29 år

Datum: 2026-10-19

## Slutsats

Den starkaste family-2-signalen är förändring i **sysselsättningsgrad** och **arbetskraftsdeltagande** för åldersgruppen **25–29 år**, uttryckt som årsförändring i procentenheter.

Kandidaten benämns `rates_25_29`.

Den är fortfarande **provisorisk** och ändrar inte den frysta långsiktiga core-4-modellen.

## Robusthet mot regularisering

### +6 månader
- alpha 3: RMSE -7,49 %
- alpha 10: RMSE -6,34 %
- alpha 30: RMSE -3,78 %

### +9 månader
- alpha 3: RMSE -14,13 %, MAE -19,59 %
- alpha 10: RMSE -11,47 %, MAE -17,13 %
- alpha 30: RMSE -6,10 %, MAE -12,37 %

### +12 månader
- alpha 3: RMSE -15,12 %, MAE -21,05 %
- alpha 10: RMSE -11,87 %, MAE -18,14 %
- alpha 30: RMSE -5,54 %, MAE -13,13 %

## Tolkning

- Signalens styrka är inte beroende av ett enda Ridge-alpha.
- 25–29 år är tydligt starkare än 20–24 år.
- Full kombination av båda åldersgrupperna är svagare än 25–29 år ensamt.
- Arbetslöshetsgruppen ska inte tas vidare i nuvarande form.
- `rates_25_29` är därför den primära BAS-kandidaten för nästa gate.

## Nästa gate

Kandidaten ska testas i pseudo-realtime med realistisk publiceringsfördröjning.

Minimikrav:
1. lag 0 månader som hindsight-övre gräns,
2. lag 1 månad,
3. lag 2 månader,
4. samma rolling-origin-regel och benchmark,
5. ingen omoptimering av featurefamilj per lagg.

Om förbättringen försvinner vid lag 1–2 månader ska kandidaten inte användas som realtime-prognosfeature.
