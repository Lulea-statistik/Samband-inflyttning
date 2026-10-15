# Tidsmässig valideringsgrind för neutralt variabelurval

Datum: 2026-10-15. Ingen automatisk produktionsändring.

## Skillnad mellan två frågeställningar
- **Geografisk korsvalidering:** Kan modellen förklara inflyttningen i kommuner som inte ingår i träningen, men inom samma historiska år?
- **Tidsmässig validering:** Kan modellen, tränad på tidigare år, förutsäga utfall i ett senare år utan att använda senare publicerade variabelvärden eller ompröva urvalet efteråt?

Tidigare geografi-CV för 2019–2023 och femårstestet mot 2024 uppfyller endast delar av den andra definitionen. **2023 och 2024 har redan studerats upprepade gånger** och får inte betecknas som oberoende slutprov.

## Strikt behörighetsgrind
För varje modellvariabel och tänkt prognos för målår T skall följande loggas:
1. Prognosens ursprungsdatum och sista tillåtna publiceringsdatum.
2. Vilken SCB-/Kolada-/annan källversion som var publicerad före ursprungsdatum.
3. Källans eventuella metodbrott och revideringar sedan prognosdatum.
4. Vilka kommuner som hade giltiga värden på prognosdatum.
5. Beslut om saknade värden och transformation, fastställt utan tillgång till T:s utfall.
6. Hela träningsfönstrets tillgänglighet i ursprungsvintage, inte enbart dagens tillbakareviderade panel.

Om ett enda steg saknar evidens får försöket användas som **retrospektiv associationsanalys**, inte som verklig as-of-prognosvalidering.

## Tidsmässig provplan
- **Primärt nutida metodfall:** träning 2019–2023 och utfall 2024, men endast explorativt. Komplettera gärna med historiskt kända vintages, annars etikett 'retrospektivt'.
- **Alternativ:** träning 2019–2022 och utfall 2023, likaså redan utforskat.
- Treårigt deluniversum 2021–2023 omfattar 78 kandidater. Femårsunderlaget 2019–2023 omfattar 56. Håll varje arm på exakt samma kommun-år och samma urvalsregler.
- **Framtida bekräftelse:** lås hela protokollet, samla ett framtida utfallsår som inte redan använts för urval eller explorativa jämförelser, och tillämpa enbart variabler tillgängliga vid prognostidpunkten.
- Blanda inte in utfall för valideringsåret i feature engineering eller komplementära kommun-/riksaggregat.
- Ta med Luleås fel separat och redovisa års- och kommungruppsstabilitet; modellval får inte styras av enbart Luleå.

## Modellkomplexitet
Separat test för **5, 10 eller 20 aktiva variabler** med en i förväg låst tvåstegsmetod (träningsexklusiv korrelationsrangordning, därefter standardiserad Ridge alpha 10). Budgeten väljs i inre 3-delad geografisk CV; ytternivån består av fem kommungrupper. Det är en förregistrerad **explorativ förenklingsstudie**, inte oberoende bekräftelse, eftersom dataset och geografiska test har granskats tidigare.

Begränsning: univariat screening kan missa variabler som hjälper först efter kontroll för andra, och eventuella starka korrelationer mellan kandidater skall redovisas. Ingen avstämning mot produktionsmodellens riktiga pipeline har ännu gjorts.

## När produktion får omprövas
Först efter källvintagegranskning, tidsframåtriktad utvärdering enligt fryst protokoll och jämförelse med *verklig befintlig produktion* på identiska rader. En lägre retrospektiv CV-RMSE räcker inte.
