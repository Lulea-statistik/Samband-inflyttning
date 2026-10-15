# Familjemedveten neutral CV – resultat och beslutsgrind (2026-10-15)

Källa: [GitHub Actions #38734412332](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38734412332), [maskinläsbar rapport](data/neutral_family_aware_cv_results.json).

## Geografisk nästlad korsvalidering, retrospektiv
| Gren och träning | Omtränade tidigare variabler RMSE | Neutralt familjeurval RMSE | Förändring | Kandidater efter familjehantering | Aktiva, intervall |
|---|---:|---:|---:|---:|---:|
| Blind, 2019–2023 | 11,314 | 8,500 | −24,9 % | 47 | 38–43 |
| Blind, 2021–2023 | 10,767 | 8,202 | −23,8 % | 67 | 32–61 |
| Prognos, 2019–2023 | 5,356 | 5,263 | −1,7 % | 52 | 35–40 |
| Prognos, 2021–2023 | 5,009 | 5,023 | +0,3 % | 72 | 43–52 |

Den neutrala blinda varianten förbättrade RMSE i samtliga fem yttre geografi-foldar, för både 3- och 5-årsmodellen. Femårig blind neutral RMSE 8,500 jämfört med första neutrala Elastic Net-studiens 8,649; skillnaden är dock **inte** oberoende prövad eftersom samma underlag har analyserats flera gånger.

## Viktiga begränsningar
- Familjescreeningen jämför representationer med träningsbaserad korrelation till utfallet; varje familjeval görs i träningsfolden, inte i testfolden.
- Sex förhandsidentifierade representationspar hanteras (småhuspris, fritidshus, centrumavstånd, arbetskraftsdeltagande/utanför arbetskraften, snöskoterandel och gymnasieinriktning). Bredare korrelationsnätverk har inte automatiskt begränsats.
- Modellens stora aktiva variabelantal och återkommande val av svag regularisering visar att förenklingen ännu är begränsad; inga bevis för optimal komplexitet.
- Fem års och tre års träningsperiod har olika kandidatuppsättningar; korsjämförelser isolerar inte effekten av familjehantering.
- Geografisk CV mäter inte generalisering till ett nytt kalenderår. 2023–2024 är sedan tidigare inspekterade; inga resultat från dessa år får kallas orört sluttest.
- Tidigare variabler jämförs med samma Elastic Net-familj men produktionsmodellens verkliga estimator/pipeline är inte rekonstruerad.
- SCB/andra datavintages vid historiskt prognosursprung är ännu inte verifierade. Historiska RAMS/BAS-tillväxtserier har en avsiktlig lucka vid metodbrottet 2020.

## Beslut
1. Klassificera utfallet som **förklarande/lovande för blind strukturmodell, ej produktionsvalt**.
2. Ingen ytterligare justering av regularisering, familjeskärning eller features får motiveras som oberoende bekräftelse av samma geografiska uppdelningar.
3. Nästa prioriterade steg är **tidsmässig datavintagegrind**: förutbestäm ursprungsdatum, verifiera faktiska publiceringstidpunkter och möjliga train/test-år för respektive kandidat. Där det inte går, utför endast uttryckligen retrospektiv känslighetsanalys.
4. Jämför senare med den faktiska befintliga produktionsmodellen på samma observationer och vid samma informationsgräns.
5. Ingen automatisk ändring av produktionsmodellen eller den publika webbplatsens modellresultat.
