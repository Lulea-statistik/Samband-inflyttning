# Fryst forskningsutmanare: dynamisk modell med pendlingsinteraktion

Beslut 2026-10-14. **Ej produktionsmodell.** Resultat: [geografiskt stresstest #1](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38521761367). Maskinläsbar rapport: `docs/data/commuting_geographic_stress_test.json`.

## Fryst princip

- Demografisk prognosmodell för kommunvis inflyttning per 1 000 invånare.
- Dynamiskt urval från samma godkända variabelpool och samma träningsbaserade selektionsfunktion som `scripts/test_commuting_geographic_stress.py`. Inget urval utifrån testutfall.
- Basfunktion: RidgeCV med `StandardScaler` och `alphas=np.logspace(-3,3,25)`.
- Två förutbestämda pendlingsfunktioner: `commute_c = outcommuting_share(t-1) - mean_train(outcommuting_share)` och `commute_jobs = commute_c * (lag1_andel_fa_arbetsplatser_i_egen_kommun - mean_train(regional_job_share))`.
- Statistikregim: BAS. RAMS får inte poolas med BAS utan separat harmonisering. Alla pendlingsprediktorer är ett år fördröjda.
- Primär jämförelse mot fryst dynamisk modell **utan** pendlingsvariabler och mot befintlig produktionsmodell, med identiska observationsurval och träningsfönster.
- Luleå samt kvartiler av utpendlingsandel redovisas som förutbestämda delgrupper.
- Varken interaktionsdefinition, regulariseringsgrid, variabelpool, urvalsalgoritm eller gate ska ändras utifrån framtida testutfall utan att ett nytt kandidatnamn skapas.

## Retrospektiv evidens (inte oberoende prospektivt bevis)

Geografiskt kommuntest 2024 (fem fold, kommuner separerade under samtliga träningsår, 290 kommuner):

| Modell | RMSE |
| --- | ---: |
| Befintlig | 6,160 |
| Dynamisk utan utpendling | 5,768 |
| Dynamisk + linjär utpendling | 5,593 |
| **Dynamisk + interaktion** | **5,552** |
| Dynamisk + mjuk viktning | 5,580 |
| Dynamisk + linjär och mjuk | 5,555 |

Parvis bootstrap med 2 000 resamplingar: interaktion minus dynamisk utan pendling som RMSE-förbättring +0,216 (95 %-intervall 0,110–0,315). Interaktion minus linjär utpendling +0,041 (0,001–0,080). Intervallen tar inte hänsyn till retrospektiv modellutveckling.

Nationell årsvis RMSE för dynamisk interaktion: 2022 RAMS 6,508, 2023 BAS 6,174, 2024 BAS 5,605. Geografiskt stresstest 2024: Q1 5,507 (grundmodell 5,545), Q2 5,402 (grundmodell 5,252), Q3 5,533 (grundmodell 5,783), Q4 5,757 (grundmodell 6,420). Luleå: verkligt 51,742, interaktion 47,092, dynamisk utan pendling 47,507.

## Krav innan produktionsprövning

1. Testa utan omkalibrering på ett framtida, tidigare oanvänt utfallsår när officiella migrationsdata och motsvarande fördröjda BAS-data finns.
2. Redovisa national RMSE och MAE, parvis prognosfel, bootstrap/osäkerhet, Luleå, samt Q1–Q4 utan att efterhandsjustera specifikationen.
3. Kräv ett substantiellt och stabilt bidrag mot såväl dynamisk modell utan pendling som befintlig produktion. Säkerställ att systematiska försämringar i Q2 eller lågpendlingskommuner inte blir oacceptabla.
4. Dokumentera serie- och definitionsbrott, läckagekontroll, samt datafördröjning. Håll produktionsmodellen oförändrad tills beslut fattas utifrån ny validering.

**Status:** fryst forskningsutmanare, ej vald till produktion.
