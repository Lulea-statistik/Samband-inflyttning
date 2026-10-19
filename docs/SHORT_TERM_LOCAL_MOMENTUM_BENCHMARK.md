# Kortsiktig månadsmodul – lokal momentum-baseline

Första externa kandidatfamiljen förbättrade inte säsongsnaiv prognos totalt, men såg betydligt bättre ut från 2025. Innan detta tolkas som effekt av BAS/BNP/asyl testas därför om samma mönster kan fångas av en enklare lokal realtidssignal.

Fasta jämförelsearmar:
- samma månader föregående år
- säsongsnaiv × senaste 3 månaders nivåkvot mot föregående år
- säsongsnaiv × senaste 6 månaders nivåkvot mot föregående år
- säsongsnaiv + additivt 3-månaders nivåskifte
- säsongsnaiv + additivt 6-månaders nivåskifte

Ingen parameter optimeras mot utfallet. Syftet är att skapa en starkare benchmark för den externa månadsmodulen.
