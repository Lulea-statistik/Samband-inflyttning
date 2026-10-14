# Neutral omstart – metodgrind efter korrelationsklassificering

Datum: 2026-10-14. Status: **förregistrerad analysplan, inte modellval eller produktionsändring**.

## Verifierat underlag
- [Neutral inventering](data/neutral_variable_pool_reboot.json): 80 unika poster; 75 preliminära för demografiskt blind gren, fem demografiska endast för prognosgren.
- [Korrelationsgranskning](data/neutral_variable_family_correlation_audit.json): 33 par med absolut Spearman-rho >= 0,85 på 2019–2023 för 290 kommuner.
- [Familjematris](data/neutral_family_review_matrix.json): 11 sammanhängande nätverksgrupper (inte 11 exklusiva urvalsgrupper).
- [Klassificering](data/neutral_correlated_pair_classification.json): 27 empiriska par, tre monotona transformationer, ett möjligt komplement, ett olika nämnare, ett möjligt kompositionellt komplement. Alla sex särskilda kopplingar är **preliminära**, utan verifierad algebraisk identitet.

## Låsta principer för nästa urval
1. **Lika villkor:** 27 äldre modellvariabler har inga undantag eller större förhandsvikt. Pröva deras bidrag, bortfall och ersättning på samma villkor som nya kandidater.
2. **Två separata mål:** Demografiskt blind modell förbjuder historiska demografiska utfall/åldersstruktur; prognosgrenen får utvärdera demografi separat. Gemen­sam folkmängd som strukturell kontroll behöver eget uttryckligt metodbeslut.
3. **Först datagrind:** Skapa feature-år-kommuntäckning för alla 80, inklusive särskilda forskningsserier. Dokumentera definition, publiceringsdatum vid prognostillfället, metodbrott och geografisk täckning. Luckan i historisk sysselsättning 2020 får inte maskeras som observerad tillväxt.
4. **Ingen korrelationsbaserad tvångsexkludering:** Pröva nära relaterade variabelformer i fördefinierade familjer. Spearman-rho = 1 för logtransformerade variabler är inte samma sak som identisk linjär effekt.
5. **Gemensamt jämförelseunderlag:** För varje konkurrerande modell jämför på identiska kommun-år, med oförändrat utfall, lagg, testår och vägningsprincip. Redovisa effekten av hur komplett urvalet blir.
6. **Train-only:** Normalisering, saknade värden, sambandsscreening, all hyperparameteroptimering och alla stegvisa urval görs enbart inom respektive träning/inner-fold; geografin grupperas vid geografisk validering. Undvik läckage från framtida publicerade BAS/RAMS-vintages.
7. **Stabilitet:** Redovisa vilka kandidater och teman som återkommer mellan geografiska och tidsmässiga tester, osäkerhet och felvariation, inte bara ett vinnande modellutfall.
8. **2024-status:** Utfall 2023–2024 har upprepade gånger granskats. Femårsexemplet 2019–2023 -> 2024 är explorativt; det får inte ensamt avgöra modell eller hyperparametrar. Behåll 2010 som sekundär känslighetskontroll, inte primärt modernt jämförelseår.
9. **Rikare baslinje:** En ny strukturmodell jämförs mot dagens befintliga modell **på samma datarader**. Tidiga variabler förlorar inte automatiskt, men får inget företräde.
10. **Beslut:** Ingen automatisk uppdatering av publik webbplats, panel eller produktionsmodell. Ett separat beslutsprotokoll krävs.

## Kvarstående spärrar innan regression
- Verifiera sex provisoriskt definierade matematiska familjer vid källkod och rådefinitioner.
- Se över om variablerna utanför aktuella 78 panelkolumner kan anslutas till valideringsdatan på ett jämförbart sätt utan förväxling av BAS/RAMS-källor.
- Lås relevant prognosögonblick och SCB-publiceringsvintages för historiskt genuina as-of-test.
- Förregistrera konkreta tids- och geografiska splitar samt modellkandidater utan att optimera mot redan granskade år.

**Resultatet av denna arbetsfas är ett neutralt urvalsprotokoll, inte en godkänd modell.**
