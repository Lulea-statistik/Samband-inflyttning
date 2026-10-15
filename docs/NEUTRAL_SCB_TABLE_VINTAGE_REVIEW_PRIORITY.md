# Prioriterad tabellgranskning efter SCB-kodindex

Datum 2026-10-15. Underlag: [neutral_source_tables_derivation_index.json](data/neutral_source_tables_derivation_index.json), Actions [#38746148936](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38746148936).

## Status
Projektkoden innehåller **18 SCB-API-konstanter och en Kolada-API-basadress**. Av 80 inventerade variabler hittas 78 i lokala tilldelningar. De två historiska RAMS/BAS-måtten kommer från en separat dokumenterad kedja. **0 av 80** har verifierats mot arkiverade källvintages för ett bestämt historiskt prognosursprung. Att konstanterna finns i koden är inte bevis på historisk publicering eller direkt kausal källkoppling.

## Första granskningsordning – befintliga bokstavliga källidentifierare

| Ordning | Område | Kodkonstant | Tabellidentifierare i kod | Granska först |
|---|---|---|---|---|
| 1 | Befolkningsutfall | MIGRATION_URL | BE0101J/Flyttningar97 | Utfall, referensår, SCB-publiceringsdag och revisionshistorik |
| 1 | Befolkning | POPULATION_URL | BE0101A/BefolkningNy | Publiceringsdatum för helår och för laggade folkmängdsvärden |
| 1 | Bostadsbestånd | HOUSING_URL | BO0104D/BO0104T04 | Publiceringsdatum för årgångar och eventuella revisioner |
| 1 | Färdigställda bostäder | COMPLETED_HOUSING_URL | BO0101A/LghReHtypUfAr | Färdigställandeår och publiceringsfördröjning |
| 1 | Arbetsmarknad | LABOR_URL | AM0210A/ArbStatusAr | BAS-vintage, årsdefinition, datatillgång och metodbrott |
| 1 | Arbetsställe | MONTHLY_EMPLOYMENT_URL | AM0210B/ArbStDoNMNN | Månatlig/årsvis summering, publiceringstidpunkt, kommunvärden |
| 2 | Näringsliv | INDUSTRY_URL | AM0210F/ArRegUtb | Referensårs- och källmetod |
| 2 | Utbildning | EDUCATION_URL | UF0506B/Utbildning | Utbildningsårgång och offentliggörande |
| 2 | Studenter | STUDENT_URL | AA0003H/IntGr8Kom1N | Läsår, referensdatum och publiceringsdag |
| 2 | Inkomster | INCOME_URL | HE0110A/SamForvInk2 | Publiceringsfördröjning och definition |
| 2 | Småhuspriser | HOUSE_PRICE_URL | BO0501B/FastprisSHRegionAr | Omräkning, revisionsvintages och period |
| 2 | Vakanser | VACANCY_ALLM_URL | BO0303A/OuthAllmLghTypKom0 | Referensdatum, publicering och datatäckning |
| 3 | Geografi | AREA_URL, TATORTSGRAD_URL, LAND_USE_URL, SHORELINE_BUILDINGS_URL | MI0802, MI0810, MI0803, MI0812 | Mätår, uppdatering och eventuell geografisk eftersläpning |
| 3 | Fordon | VEHICLE_TRAFFIC_URL | TK1001A/FordonTrafik | Årsuppdatering, publiceringslagg och metod |
| 3 | Fördelningsmått | INEQUALITY_URL | HE0110I/Tab4InkDesoRegso | Tillgång och områdesgränser |
| 3 | Kolada | KOLADA_API_BASE | api.kolada.se/v3 | Här behövs även en **indikatoridentifierare** och historiskt publiceringsdatum per indikator |

## Särskilt arbetsmarknadsfall
De två alternativa forskningsmåtten för historisk sysselsättning följer `commuting_historical_rams.csv` / `commuting_flows_2020_2024.csv` genom regimstyrd beräkning till `employment_lag1_research_availability.csv`. Deras 2020-lucka är avsiktlig. En nutida preferens för BAS i överlappande år får inte behandlas som en godkänd historisk tillgänglighetsregel.

## Krav för uppgradering från kodindex till verifierad prognosvariabel
För varje variabel: (1) källtabell och indikator, (2) exakt härledning till modellkolumn, (3) referensperiod, (4) tidigaste belagda publicering för just den årgången och geografiska omfattningen, (5) revisionshantering, (6) låst prognosursprungsdatum. Alla punkter måste vara dokumenterade innan `asof_verified=true` får sättas.

**Inga modellvariabler godkänns automatiskt utifrån denna prioritering.** Ingen regression körs och produktionsmodellen ändras inte.
