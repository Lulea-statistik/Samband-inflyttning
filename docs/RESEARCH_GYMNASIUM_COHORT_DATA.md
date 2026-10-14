# Gymnasieexamen, tidsfördröjning och ungas migration – källkritisk avgränsning

## Bekräftade källor

- Skolverket, *Beskrivande data 2014*: https://www.skolverket.se/download/18.6bfaca41169863e6a65b718/1553966086803/pdf3418.pdf. Gy 2011 infördes för elever som började 2011. Första treårsexamen 2014; äldre slutbetyg har andra krav och är inte direkt jämförbara.
- Skolverket, kommunala jämförelsetal för gymnasieskolans betyg: https://statistikdatabasen.skolverket.se/PxWeb/pxweb/sv/Skolverkets_statistikdatabas/Skolverkets_statistikdatabas__Kommunala_jamforelsetal__Gymnasieskola__Betyg_och_studieresultat/Gymnasieskola_betyg_studieresultat.px/ . 'Fullföljd utbildning med examen inom 3 år' avser nybörjarelever folkbokförda i kommunen **vid utbildningsstart**, inte personer som nödvändigtvis bor kvar i kommunen vid examen. Årtalet gäller redovisningsåret för kull som började tre år tidigare.
- SCB, *Övergång gymnasieskola–eftergymnasiala utbildningar*: https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__UF__UF0542__UF0542B/ . Har bland annat äldre kommunuppgifter om övergång till högskola samt senare examinerade grupper med övergång inom ett, tre, fem eller tio år.
- SCB, äldre kommunala gymnasienyckeltal 2000–2013: https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__OE__OE0107__OE0107G/GymnSkols/ . Historiska mått kan inte antas vara jämförbara med nya examen.

## Tidsindex: bokstavlig tolkning av användarens förslag

För kalenderår för gymnasieexamen E och antagen fördröjning n:

- Önskad träningsperiod [E+n, E+n+5], inklusive båda åren, och prognosår E+n+6.
- Detta är sex träningsår, **inte** fem.
- För prognos 2023: utbildningskohort E=2016 vid n=1, E=2015 vid n=2; träningsutfall 2017–2022.
- För prognos 2024: E=2017 vid n=1, E=2016 vid n=2; träningsutfall 2018–2023.
- Tidigare kod `scripts/audit_gymnasium_literal_cohort.py` tolkar varje historiskt utfallsår som kopplat till en **annan** examenskull med källår `t-(n+6)`. Detta är en regression med mycket lång eftersläpning, **inte ett faktiskt kohorttest med en och samma examenskull**.
- Ett strikt kohorttest kräver att vi följer samma personer från utbildning via bosättning/flyttning (persondata), eller offentlig aggregerad statistik som direkt anger kohortens bosättning/flyttar efter examen. Kommunvis totalt flyttningstal för alla ungdomar får INTE beskrivas som flyttningar av just examenskullen.
- Det är möjligt att testa över tid hur kommunens tidigare examensgrad samvarierar med senare **kommunvis** flyttning utan individkoppling, men tolkningen måste anges som ekologisk och inte som kohortkausal.
- Koladas laggade nyckeltal räknas från årsetiketten, som här avser första gymnasiestartsåret tre år tidigare för 3-årsexamen; publiceringsdatum och tillgång vid prognostidpunkt behöver verifieras.

## Resultat av tidigare tillgänglighetsgranskning

`docs/data/gymnasium_literal_cohort_sixyear_audit.json`: Kolada N17445 har komplett täckning 2014–2024; N17461 från 2015–2024. Det långa laggupplägget i den föregående auditkoden kräver data från 2009–2013 och kan därför inte köras utan backfyllnad. Dessa år ska inte imputeras och gamla slutbetyg ska inte sömlöst skarvas på.

## Nästa forskningssteg – prioritet

1. Hämta Skolverkets tabellmetadata för kommunvisa resultat. Dokumentera vilka mått före 2014 som är **samma begrepp** och vilka som inte är det, utan att förutsätta kompatibilitet.
2. Undersök om SCB har en explicit aggregerad kohorttabell som beskriver ungdomarnas framtida bostadskommun eller flytt efter examen. Statistiken om övergång till högskola är en proxy för vidare studier, **inte en mätning av flyttningar**.
3. Om kohortkopplad flyttning inte finns öppet: gör ett tydligt avgränsat kommunårs-test med examensgrad som ekologisk förklaringsvariabel, åldersspecifik in-/utflyttning, korta lags, på teståren 2023–2024 och konsekvent fönster. Märk det uttryckligen som annat än kohorttest.
4. Behåll produktionsmodellen och den frysta pendlingsutmanaren oförändrade.

## Metodbeslut

Ingen syntetisk examen 2009–2013. Inga kausala påståenden eller individbaserade flyttningsslutsatser från aggregerad kommundata. Ingen automatiserad modellpromotion.
