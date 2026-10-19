# Status – rates_25_29 efter common-origin laggtest

Datum: 2026-10-19

## Beslut

`rates_25_29` uppgraderas från provisorisk till **validerad kortsiktig kandidat** för 9–12 månadershorisonten.

Kandidaten består av:
- årsförändring i sysselsättningsgrad, procentenheter, 25–29 år
- årsförändring i arbetskraftsdeltagande, procentenheter, 25–29 år

Detta ändrar inte den frysta långsiktiga core-4-modellen.

## Common-origin-resultat

Exakt samma forecast origins används för lag 0, 1 och 2.

### +9 månader
- alpha 3: lag 1 -17,45 % RMSE, lag 2 -17,03 %
- alpha 10: lag 1 -14,48 %, lag 2 -14,01 %
- alpha 30: lag 1 -8,32 %, lag 2 -7,92 %

### +12 månader
- alpha 3: lag 1 -10,55 %, lag 2 -10,41 %
- alpha 10: lag 1 -7,63 %, lag 2 -7,21 %
- alpha 30: lag 1 -1,73 %, lag 2 -1,12 %

MAE förbättras samtidigt genomgående.

## Tolkning

Signalens förbättring kvarstår:
- över flera regulariseringsnivåer,
- med 1–2 månaders gammal BAS-data,
- på exakt samma forecast origins.

Det gör att kandidaten klarar pseudo-realtime-gaten.

## Nästa gate

Kandidaten ska testas mot en makroförankrad månadsbaseline:

1. frozen core-4 årsprognos,
2. fördela årsprognosen över månader med endast historisk säsongsprofil,
3. jämför makro+säsong mot säsongsnaiv,
4. lägg `rates_25_29` som residualkorrigering ovanpå makro+säsong,
5. behåll core-4 fryst.

Ingen produktionspromovering innan denna jämförelse är klar.
