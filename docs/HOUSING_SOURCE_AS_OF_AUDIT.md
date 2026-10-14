# Bostadsvariabler: källspårning och prognostidsgranskning

Status: **källkod och beräkningsdefinition spårad; historiska publiceringstidpunkter ej verifierade** (2026-10-14). Framtagen under [Issue #2](https://github.com/Lulea-statistik/Samband-inflyttning/issues/2). Ingen produktionstillåtelse.

## Spårade källor

| Variabel i modell | Källa i `scripts/build_analysis.py` | Beräkning och begränsning | Prognostidsstatus |
|---|---|---|---|
| `lag1_fardigstallda_bostader_per_1000` | SCB BO0101, `LghReHtypUfAr`, `COMPLETED_HOUSING_URL` | 1 000 × färdigställda bostadslägenheter i nybyggda hus / folkmängd, föregående referensår. Ombyggnationer ingår inte nödvändigtvis. | Ej verifierad |
| `lag1_bostadsbestandsforandring_pct` | SCB BO0104T04, `HOUSING_URL`, bostadsbestånd | 100 × årlig procentuell förändring i `bostader_totalt`, beräknat med `pct_change()`, därefter laggad ett år. Kräver minst två beståndsår. | Ej verifierad |
| `lag1_smahusforsaljningar_per_1000_smahus` | SCB BO0501B, `FastprisSHRegionAr`, `HOUSE_PRICE_URL`; nämnare BO0104T04 | 1 000 × antal köp av permanentbostadsfastigheter (ej tomträtt) / antal bostäder i småhus. Olika populationsdefinitioner mellan täljare och nämnare; inte omsättningen av samtliga småhus. | Ej verifierad |
| `lag1_log_fritidshus_per_1000_inv` | SCB BO0104T08, `LEISURE_HOUSE_URL_CANDIDATES`, samt folkmängd SCB BE0101 | Logtransformerad fritidshustäthet, 1-årslag. Kontrollera exakt loggfunktion och eventuella nollor i `build_analysis.py` vid separat definitional audit. | Ej verifierad |

Källornas kodreferenser: [build_analysis.py](https://github.com/Lulea-statistik/Samband-inflyttning/blob/main/scripts/build_analysis.py).

SCB-API-tabeller:
- BO0101 `https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0101/BO0101A/LghReHtypUfAr`
- BO0104T04 `https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104D/BO0104T04`
- BO0501 `https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0501/BO0501B/FastprisSHRegionAr`
- BO0104T08 `https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104H/BO0104T08` (kod innehåller fallback-URL:er; verifiera faktiskt löst tabell-ID).

## Kontrollkrav före prognosgodkännande

1. Ange prognosursprung och informationsstopp (datum) för 2023 och 2024.
2. Hämta SCB:s publiceringskalender, första publicering för respektive referensår, samt revideringspolicy separat per tabell. Att data nu finns i API:et är **inte** bevis för historisk tillgänglighet.
3. Dokumentera om rapportens `lag1_` är tillräcklig för att undvika publiceringsfördröjning. Om värde för år t-1 publicerades efter prognosdatumet ska det inte ingå i t-prognosen.
4. För `bostadsbestandsforandring_pct`: båda beståndsåren måste ha publicerats.
5. Kontrollera källdefinitioner i SCB:s tabellmetadata; särskilt nybyggda kontra ombyggda lägenheter, permanentbostadsköp och fritidshusdefinition.
6. Först därefter markeras variabeln tidsmässigt godkänd. Vid bristande historik: använd konservativt längre eftersläpning eller klassificera retrotestet som ej publikationssäkert.
7. Slutligen genomför oberoende rolling-origin med låst urvalsmetod; äldre 2023–2024-test är utforskande och kan inte användas för slutlig modellantagning.

## Metodologiskt resultat hittills

I det retrospektiva, redan inspekterade testet 2023/2024 var `lag1_log_fritidshus_per_1000_inv` bäst av de fyra ensamma tilläggen på nationell RMSE (12,013/10,997). Detta visar inte att variabeln varit publicerad i tid, eller att den bör väljas för produktion.

**Issue #2 kvarstår öppet tills SCB:s publiceringstidpunkter och revisionsrisker är verifierade.**
