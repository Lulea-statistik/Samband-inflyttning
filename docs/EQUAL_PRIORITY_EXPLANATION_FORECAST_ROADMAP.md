# Två likvärdiga modellspår: förklaring och prognos

Beslut 2026-10-15. **50/50-prioritet i kommande forsknings- och utvecklingsarbete.** Ingen produktionsändring.

## Spår A – förklaringsmodell (demografiskt blind)
**Fråga:** Vilka observerade kommunegenskaper förklarar skillnader i inflyttning, givet andra kommunegenskaper?

- Utgå från neutrala kandidatpoolen (75 preliminärt tillåtna icke-demografiska variabler; 51 med full täckning 2019–2023 och 73 för 2021–2023).
- Ingen historisk inflyttning, utflyttning, inflyttarnas åldersprofil, befolkningstillväxt eller åldersstruktur som förklarande variabel. `lag1_log_folkmangd` behandlas som uttrycklig strukturell kontroll.
- Testa självständigt **villkorligt** förklaringsvärde, partiellt R² / förbättring relativt gemensam baslinje och stabilitet mellan år, kommungrupper och modeller; använd tidsmässigt separerade målfönster där möjligt.
- Håll nära relaterade representationer i samma rapport men anta inte att stark korrelation betyder orsakssamband, identisk innebörd eller att båda ska uteslutas.
- Redovisa osäkerhet, påverkan av kommunstorlek, uteliggare, geografiska kontroller och saknade uppgifter. Skillnader i inflyttning är inte automatiskt kausala effekter.
- **Nästa körbara leverans:** granskningsrapport med variabelfamiljernas villkorliga bidrag inom förhandslåsta tränings-/geografiska uppdelningar, utan produktionsuppdatering.

## Spår B – faktisk prognosmodell
**Fråga:** Hur bra kan modellen förutse kommande års inflyttning med uppgifter som redan fanns vid prognostillfället?

- Tillåt de fem demografiska variablerna och samma breda strukturpool på rättvisa villkor.
- Använd rolling-origin med separat inner-fold-urval, en gemensam incumbent-baslinje på identiska kommun-år och felmåtten RMSE, MAE, P90-fel samt Luleås residualer.
- Dokumentera klart om varje test är **retrospektivt** (dagens historiska data) eller **verkligt as-of** (historiskt verifierad publiceringsvintage). Reflektera statistikens referensår och faktiskt publiceringsdatum separat.
- Kontrollera SCB/Kolada-vintages främst för prognosspåret; detta är inte en generell spärr för att studera retrospektiva strukturella samband.
- 2023–2024 är tidigare granskade år och **inte orörda bekräftelseset**. Använd dem bara explorativt tills ett nytt, fryst test finns.
- **Nästa körbara leverans:** rolling-origin-design med fördefinierade brytpunkter och en matris som visar vilka variabler som är tillgängliga enligt observerad historik, respektive verifierade ursprungsvintages. Kör bara retrospektivt där vintage saknas.

## Gemensamma regler
1. **Lika resurser och uppföljning:** varje iteration rapporterar status, resultat, risker och nästa steg för både A och B. Ett spår får inte stoppas av krav som bara är relevanta för det andra.
2. **Gemensam datagrund:** 290 SCB-kommuner, identiskt dokumenterade definitioner och datafönster vid direkta jämförelser.
3. **Ingen incumbency-förtur:** variabler från befintlig modell och senare tillagda kandidater tävlar på samma villkor. Jämför återtränad incumbent-variabellista separat från den exakta aktiva produktionspipeline.
4. **Läckagekontroll:** all skalning, imputering, rangordning och justering sker endast inom aktuell träning; ingen testårsrespons i variabelbyggande.
5. **Separata slutsatser:** en variabel kan förklara variation utan att förbättra prognos, eller förbättra prognos utan att vara en kausalt belagd drivkraft.
6. **Beslutsgrind:** inget nytt modellval och ingen automatisk publicering i produktion utan uttryckligt nytt beslut.

## Närmaste milstolpe
Publicera en **tvåspårig forskningsöversikt** som presenterar strukturmodellens villkorliga förklaringsresultat bredvid prognosmodellens tidsmässiga generalisering, utan att sammanblanda R²-förklaring och prognosfel. Historiska SCB-releasedatum hör hemma i prognosspårets granskningsdel, inte som huvuduppgift för hela projektet.
