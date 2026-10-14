# Historiskt valideringsutrymme: nästa prioritet i modellomprövningen

Status: metodisk avgränsning, 2026-10-14. **Ingen produktionsändring.** SCB:s alternativa tabelljämförelse pausad enligt önskemål.

## Varför ingen ny 2024-optimering nu?

Den tematiska jämförelsen, ablationen och det parvisa bostadstestet använde redan granskade år (2023–2024). Nya iterationer mot samma testår kan ge alltför optimistiska modellval. Bostadsmåtten har visat både variation och överlappning; detta ger kandidater till framtida validering, inte bevis för införande.

## Dokumenterade historiska begränsningar

Historikrapporten [structural_historical_bottlenecks.json](data/structural_historical_bottlenecks.json) visar att vissa strukturella basmått har god historik:
- Målvariabel inflyttning/1 000: alla 290 kommuner åren 2002–2024.
- Laggad logaritmerad folkmängd: 2003–2024.
- Laggad tätortsgrad: 2006–2024.
- Laggad inkomst och eftergymnasial utbildning: 2019–2024.
- Laggad andel FA-arbetsplatser i egen kommun och regionalt centrumavstånd: 2021–2024, alltså inga fem hela träningsår + ett separat testår i det aktuella panelmaterialet.

[Fresh structural candidate coverage](data/fresh_structural_historical_coverage.json) visar exempelvis:
- LOK-stöd per invånare: komplett 2021–2024; endast prognosår 2024 kan prövas med tre träningsår inom befintliga observationsserien.
- Variabler för årlig förändring av sysselsättning: komplett endast 2022–2024; otillräckligt för tre års träning.
- Säsongsvariation för sysselsatta: komplett 2021–2024; treårsmodell kan endast testas för 2024.

**Observera:** att en variabel finns i det nuvarande panelmaterialet är inte ett bevis på att exakt det historiska värdet var publicerat vid prognostillfället.

## Beslutsordning för nästa forskningsetapp

1. **Bevara 2023–2024 som utforskande**. Gör inte omval styrt av nytt testutfall för samma år.
2. Gör en gemensam täckningsmatris för de 73 variablerna, uppdelad på tidigare basvariabler, nya kandidater och fasta teoretiska kontrollmått. För varje kandidat: första kompletta år, 3/5/10-åriga möjliga prognosfönster och om publiceringsdatum är fastställt.
3. Dela ett historiskt väl täckt basmodellspår från ett nyare kandidatspår. Jämför bara modeller på identiska rader och prognosår; redovisa när en variabel inte kan prövas på grund av historikbrist.
4. Reservera ett verkligt orört framtida utfallsår eller data med historiska as-of-snapshots för bekräftande validering. Predefiniera modellstorlek, temaregler, kollinearitetsspärr, felmått och referens innan utvärdering.
5. Rapporter från tidigare 2024-körningar ska beskrivas som **hypotesgenererande**, inte som definitiva prioriteringar av fritidshus, färdigställda bostäder eller LOK-stöd.

## Föreslagen nästa implementation

Skapa en **icke-prediktiv** maskinläsbar täckningsmatris utifrån redan producerade data, med tydliga statusfält `completely_covered`, `too_short`, `not_yet_audited`, `as_of_unknown`. Denna inventering kräver inga nya modellkörningar och förhindrar att historiskt korta serier ges skenbart likvärdig validering.

Separata prognos- och demografiskt blinda strukturmodeller kvarstår. En variabel kan behållas som **förklarande kandidat** även om den inte får ingå i en bekräftande historisk prognostest.

## Uppdatering efter fullständig 73-variabelsgranskning (2026-10-14)

[Maskinläsbar täckningsmatris](data/fair_all_candidate_historical_coverage.json) från framgångsrika Actions #38595729089 ersätter de äldre, mer begränsade screeningrapporterna när det gäller **förekomst i den nuvarande panelen**:

| Historiskt träningsfönster | Antal kandidater med minst ett helt täckt prognosår av 73 |
|---|---:|
| 3 år | 71 |
| 5 år | 51 |
| 10 år | 6 |

45 kandidater blir fullständiga först 2019. En kandidat med första helt täckta år 2019 kan med fem års träning endast användas för teståret 2024 i den befintliga panelen. Bland de 73 finns 18 med första kompletta år 2021 och 2 med första kompletta år 2022.

**Korrigering:** Den äldre rapporten `fresh_structural_historical_coverage.json` redovisade LOK-stöd som komplett 2021–2024. Den fullständiga nya panelinventeringen redovisar däremot `lag1_kolada_utbetalt_lok_stod_kr_per_inv` som komplett från **2019** (femårsfönster för 2024). Detta är en skillnad mellan två rapporter som måste förstås som olika granskningstidpunkter och/eller panelunderlag; den gamla uppgiften ska inte längre presenteras som säker aktuell paneltäckning. De verkliga publiceringsdatumen är fortfarande **inte kontrollerade**.

Viktigt: 51 individuellt godkända femårsfönster betyder **inte** 51 samtidigt förenliga variabler i valfri multivariabel modell. En modell behöver ett gemensamt identiskt års-/kommunurval och alla variabler måste ha varit tillgängliga vid prognostillfället.

**Beslut:** Inga nya tränings-/testkörningar mot det redan återanvända prognosåret 2024 förrän testprotokoll och historisk tillgänglighet är tydligare låsta. Produktionsmodell oförändrad.
