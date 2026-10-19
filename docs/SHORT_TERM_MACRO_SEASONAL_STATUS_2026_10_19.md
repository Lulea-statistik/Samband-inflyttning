# Status – as-of makro + säsong v1

Datum: 2026-10-19

## Beslut

Den första as-of-kompatibla makro+säsong-baslinjen **avvisas som månadsbaseline**.

Frozen core-4 ändras inte.

## Resultat

Makro+säsong är sämre än säsongsnaiv prognos på samtliga testade horisonter och för alla forecast-origin-offsets.

### +7 dagar
- 3m RMSE: +11,74 %
- 6m: +7,85 %
- 9m: +9,49 %
- 12m: +9,07 %

### +10 dagar
- 3m: +11,62 %
- 6m: +8,45 %
- 9m: +9,92 %
- 12m: +9,29 %

### +14 dagar
- 3m: +14,91 %
- 6m: +34,87 %
- 9m: +29,71 %
- 12m: +22,52 %

MAE försämras också genomgående.

## Tolkning

Den frysta annual core-4-modellen fungerar inte som direkt nivåankare för återstående månadsinflyttning med denna enkla säsongsallokering.

Detta innebär inte att core-4 ska ändras eller avvisas för sitt långsiktiga årsprognosspår.

Det innebär endast att:
- annual core-4 inte ska användas som direkt månadsbaseline i v1,
- säsongsnaiv prognos kvarstår som formell korttidsbaseline,
- `rates_25_29` ska jämföras mot säsongsnaiv på identiska origins,
- framtida integration mellan års- och månadsmodul kräver en annan brygga än direkt årsankare × historisk månadsandel.

## Nästa gate

Kör common-origin-kandidatjämförelse för:
1. säsongsnaiv,
2. Family1 narrow BAS YoY,
3. `rates_25_29` med realistisk lag 1 och lag 2,
4. samma forecast origins och targetperioder,
5. alpha 3/10/30 där relevant.

Prioritera 9 och 12 månader, men redovisa även 3 och 6 månader.
