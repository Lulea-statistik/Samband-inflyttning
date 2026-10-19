# rates_25_29 – common-origin gate klar

Datum: 2026-10-19

## Resultat

`rates_25_29` klarar common-origin-testet. Exakt samma forecast origins används för lag 0, 1 och 2.

### +9 månader
- alpha 3: lag 1 -17,45 % RMSE, lag 2 -17,03 %
- alpha 10: lag 1 -14,48 %, lag 2 -14,01 %
- alpha 30: lag 1 -8,32 %, lag 2 -7,92 %

### +12 månader
- alpha 3: lag 1 -10,55 %, lag 2 -10,41 %
- alpha 10: lag 1 -7,63 %, lag 2 -7,21 %
- alpha 30: lag 1 -1,73 %, lag 2 -1,12 %

MAE förbättras också genomgående.

## Status

Kandidaten är validerad som separat kortsiktig 9–12-månaderssignal, men är fortfarande inte aktiverad i produktion och ändrar inte frozen core-4.

## Makrointegrationsgate

Den historiska core-4-serien är årsvis och bygger på ettårsprognoser. En naiv månadsallokering av core-4 över targetmånader som korsar kalenderår kan därför använda ett annual-forecast-värde som inte var känt vid forecast origin.

Makro+säsong får därför inte byggas genom att bara slå upp core-4-prediction för varje targetårs kalenderår.

Nästa makrotest måste först skapa en explicit as-of-tabell:
- forecast origin månad,
- vilket annual core-4-värde som faktiskt skulle ha varit tillgängligt då,
- publicerings-/datatillgänglighetsregel,
- hur årsbelopp fördelas över månader med enbart tidigare observerad säsongsprofil.

Tills detta är gjort fortsätter säsongsnaiv att vara den formella månadsbenchmarken.
