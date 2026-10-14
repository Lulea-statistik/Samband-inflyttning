# Neutral modellomstart – beslut efter granskning av överanpassning

Datum 2026-10-14. Status: **forskning, inte produktionsgodkännande**.

Källor:
- [Geografisk nästlad korsvalidering](data/neutral_geographic_nested_selection_results.json), [körning #38614216580](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38614216580)
- [Komplexitetsgranskning](data/neutral_nested_cv_overfitting_audit.json), [körning #38615021933](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38615021933)

## Resultat (samma observationer inom varje modellspår)
| Spår | Tidigare variabler RMSE | Neutralt RMSE | Förändring | Geografiska foldar med förbättring | Aktiva neutrala variabler, medel / totalt |
|---|---:|---:|---:|---:|---:|
| Blind, 2019–2023 | 11,336 | 8,649 | −23,7 % | 5/5 | 44,2/51 |
| Blind, 2021–2023 | 10,740 | 8,140 | −24,2 % | 5/5 | 64,2/73 |
| Prognos, 2019–2023 | 5,356 | 5,239 | −2,2 % | 5/5 | 37,8/56 |
| Prognos, 2021–2023 | 5,009 | 5,031 | +0,4 % | 2/5 | 48,6/78 |

Minsta testade Elastic Net-alpha, 0,03, valdes i 5/5 yttre foldar för vart och ett av de fyra spåren, totalt 20/20. Detta är en indikator på att den befintliga sökrymden inte har prövat komplexitetsbegränsningar grundligt. Det är **inte ett bevis på klassisk överanpassning**, och valet av lägre alpha betyder inte automatiskt att ännu lägre är rätt väg.

## Metodbeslut för nästa studie
1. **Ingen produktionsöverföring.** Nuvarande resultaten gäller geografisk generalisering, inte prognos för osedda framtida år.
2. **Separat, förhandsregistrerat förenklingsspår.** Undersök mindre antal aktiva variabler genom uttrycklig modellbudget eller förutbestämd stärkning av regularisering, med samma regler för gamla och neutrala kandidater. Urval, skalning och eventuell imputering ska ligga helt inom träningsfoldarna.
3. **Undvik nytt val på samma valideringsresultat.** Upprepade tester och godtyckliga gridjusteringar baserade på resultat från 2019–2023 skulle överanpassa även utvärderingsprotokollet. Tidigare granskade 2023 och 2024 är inte orörda testår.
4. **Tidsgrind krävs.** Definiera tidsframåtriktade perioder med källvintages som verkligen var publicerade vid respektive prognosursprung. Om detta inte kan säkras: märk testen retrospektivt explorativa.
5. **Befintlig produktion jämförs separat.** Återtränad delmängd med Elastic Net är inte samma sak som en exakt rekonstruktion av produktionspipeline. Kontrollera modellen direkt innan några slutsatser om produktionsöverlägsenhet.
6. **Kandidaternas osäkerhet:** två historiska RAMS/BAS-serier måste hanteras som alternativa historikmått, inte ytterligare oberoende modeller; 2020-luckan är kvar.
7. **Förhandsbestäm jämförelse:** redovisa RMSE och MAE, antal aktiva variabler, variabelstabilitet, kommungruppers fel och både förbättrade och försämrade grupper. Luleå analyseras separat och får inte ensam styra urvalet.

## Beslut
**Fortsätt med tidsmässig och komplexitetsmässig metodgranskning innan nästa neutrala urvalstest.** Inga variabler tas bort och ingen produktionsmodell ändras av denna rapport.
