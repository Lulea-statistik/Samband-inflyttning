# Rättvis omprövning av samtliga modellvariabler

Status: **beslutad metodplan – genomförs stegvis** (2026-10-14). Detta dokument är projektets persistenta arbetsplan. Forskningsresultat innebär inte automatiska ändringar av produktionsmodellen.

## Varför
Tidigt införda variabler har inte genomgått samma valideringskrav som nya kandidater. Att bedöma nytillkomna variabler enbart som tillägg till en låst äldre modell kan skapa incumbency bias, multikollinearitet och överanpassning till tidigare studerade 2023–2024.

## Fast metodregel
1. Inventera **alla** använda, uteslutna och föreslagna variabler: källkod, definition, år, täckning, publiceringstid, dataläckage, tidigare beslut och testhistorik.
2. Två separata spår: **prognosmodell** (historisk demografi tillåts) och **demografiskt blind strukturmodell** (historisk inflyttning, utflyttning, befolkningstillväxt, inflyttarprofil och åldersprofil förbjuds som prediktorer; strukturellt log-folkmängd tillåts).
3. Specificera obligatoriska teoretiska kontrollvariabler *före* test. Skilj dem från variabler som väljs efter prognosnytta.
4. Lås gemensamma, identiska jämförelsedata, tränings-/testperioder, urvalsmetod, modellklass, hyperparameterprocess och felmått. Urval och skalning görs enbart på träningsdata (inklusive eventuell inre korsvalidering). Inga globala imputerings- eller selektionssteg före split.
5. Testa (a) omval från noll, (b) borttagning av varje befintlig variabel med omträning, (c) rättvis ersättning med nya kandidater och (d) urvalsstabilitet över geografiska och tidsmässiga splitar. Undersök korrelerade variabelgrupper tillsammans.
6. Rapportera RMSE, MAE, R², utfallet för Luleå, spridning per kommungrupp, osäkerhet, urvalsfrekvens och komplett kandidatförteckning. Skilj **förklarande samband** från **orsakssamband**.
7. Utfall: vald / kandidat / förklarande proxy / ej vald / otillräcklig data, med öppet beslutsmotiv.
8. Använd tidigare 2023–2024 och återanvända geografiska foldar endast som **explorativa** robusthetstester. Före införande krävs separat prospektiv eller annars verkligt orörd validering och verifierad publiceringstid för varje variabel. Om orörd testdata saknas: säg det och ge inget produktionsgodkännande.

## Genomförande
- **Etapp A – inventering och granskning av historiska urval:** generera maskinläsbar audit; identifiera vilka variabler som är incumbents, alternativa kandidater och fasta kontroller, samt luckor i täckning.
- **Etapp B – rättvist omval:** frys design före utvärdering, jämför tre alternativ (ursprunglig modell, omval utan incumbency-förtur, förenklad modell) på samma observationsmängd inom respektive spår.
- **Etapp C – ablation och substitution:** testa om incumbents fortfarande tillför självständig nytta, och om kandidater kan ersätta dem. Rapportera grupper av samvarierande variabler.
- **Etapp D – robusthet och beslut:** kontrollera temporal/geografisk generaliserbarhet, uppdatera forsknings-/testlogg och metodtexter; endast separat godkänt beslut får ändra produktionsmodellen.

## Begränsningar
Att ha samma höga ribba för alla kräver inte att varje teoretiskt fördefinierad kontroll har positivt individuellt RMSE-bidrag. Varje sådan kontroll måste dock motiveras och dokumenteras separat. Full historisk datatäckning är ett eget krav som kan blockera vissa jämförelser.
