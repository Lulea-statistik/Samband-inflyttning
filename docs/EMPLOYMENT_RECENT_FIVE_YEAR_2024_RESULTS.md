# Sysselsättning och inflyttning: fem års träning 2019–2023, test 2024

Källa: [körning #38607762801](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38607762801), [maskinläsbart resultat](data/employment_2019_2023_fixed_window_2024.json). **Endast retrospektivt explorativt; inte ett orört prognostest.**

Samtliga fyra modeller är skattade på samma 1 450 observationer (290 kommuner × 2019–2023) och testade på samma 290 kommuner 2024. Fast Ridge-alpha 10 och kontrollvariablerna laggad log-folkmängd och laggad tätortsgrad.

| Modell | RMSE | MAE | Luleå beräknad inflyttning per 1 000 |
|---|---:|---:|---:|
| Basmodell | 14,255 | 11,108 | 62,772 |
| + bostadsbaserad sysselsättningstillväxt | 13,889 | **10,693** | 63,073 |
| + arbetsställebaserad sysselsättningstillväxt | 13,986 | 10,825 | 63,333 |
| + båda måtten | **13,860** | 10,695 | 63,336 |

Faktisk inflyttning Luleå 2024: **51,742 per 1 000**. **Luleå-felet försämras** i samtliga tillägg. Nationellt minskar RMSE ca 2,6 % med bostadstillväxt och ca 2,8 % med båda.

## Metodreservationer

- Prognosår **2024 är redan återkommande granskat** i modellprojektet. Resultatet får inte användas för att slutligt välja tillägg, styrka eller produktionsmodell.
- **2020 saknar jämförbar sysselsättningsförändring** i detta upplägg. Träningsmedian har använts som numerisk ersättning **med en explicit indikator**; den ersättningen är inte faktisk observerad tillväxt. Indikatorn kan fånga allmänna 2020-effekter snarare än en metodlucka, och är samma för alla kommuner det året.
- Årens historiska källvintages och publiceringstidpunkter är inte verifierade; därför är detta inte ett reproducerat as-of-test.
- För **procentuell årsförändring inom en regim** gör en konstant BAS/RAMS-nivåfaktor ingen skillnad. Testet stöder möjligt informationsvärde i *längre sysselsättningshistorik*, inte en kausal fördel av *nivåkalibreringen*.
- Modellen är en enkel basmodell. Projektets mer omfattande strukturella kandidatmodell har inte jämförts på samma tränings- och testrader.
- Tre extra geografiska panelkoder exkluderades genom att välja de 290 SCB-kommunerna.

## Nästa beslutsgate

1. Jämför befintlig strukturell modell + / − sysselsättningsvariabler på **identiska kommun-år och prognosår**, utan att förvälja bort konkurrerande kandidater.
2. Specificera i förväg om båda sysselsättningsmåtten ska testas gemensamt eller separat, och hantera 2020-luckan med samma konsekventa policy.
3. Utvärdera beroende mellan bostads- och arbetsställebaserad tillväxt samt hur effekten varierar mellan kommungrupper.
4. Behåll 2024 som hypotesgenererande och reservera senare ej granskade år eller verkliga historiska as-of-vintages för bekräftelse.
5. Gör ingen produktionsförändring utan separat metodbeslut.

**Produktionsmodell och rådata oförändrade.**
