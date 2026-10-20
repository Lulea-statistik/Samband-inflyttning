# Slutstatus – 12 månaders bakåtblick för korttidsmodulen

Datum: 2026-10-20

## Beslut

Den låsta 12-månaderslinan är slutförd.

`rates_25_29` är den tydligt starkaste korttidskandidaten i common-origin-jämförelsen.

Kandidaten använder:
- årsförändring i sysselsättningsgrad 25–29 år, procentenheter
- årsförändring i arbetskraftsdeltagande 25–29 år, procentenheter
- realistisk BAS-lagg 1–2 månader

Frozen core-4 ändras inte.

## Common-origin-resultat

Alla armar använder exakt samma forecast origins och targetperioder.

### 3 månader
`rates_25_29`:
- lag 1: RMSE cirka -3,4 till -4,1 % mot säsongsnaiv
- lag 2: cirka -4,2 till -5,7 %

Family1 BAS YoY:
- lag 1: liten förbättring, cirka -0,4 till -0,9 %
- lag 2: ungefär neutral till något sämre

### 6 månader
`rates_25_29`:
- lag 1: cirka -6,6 till -11,7 %
- lag 2: cirka -8,0 till -14,3 %

Family1 BAS YoY:
- cirka +6,7 till +7,7 % sämre än säsongsnaiv

### 9 månader
`rates_25_29`:
- lag 1: cirka -8,3 till -17,5 %
- lag 2: cirka -7,9 till -17,0 %

Family1 BAS YoY:
- cirka +5,0 till +8,4 % sämre RMSE än säsongsnaiv

### 12 månader
`rates_25_29`:
- lag 1: cirka -1,7 till -10,6 %
- lag 2: cirka -1,1 till -10,4 %

Family1 BAS YoY:
- cirka +8,4 till +12,5 % sämre RMSE än säsongsnaiv

## Tolkning

`rates_25_29`:
- förbättrar RMSE på alla fyra horisonter,
- förbättrar både lag 1 och lag 2,
- förbättrar vid alpha 3, 10 och 30,
- är särskilt stark på 6–9 månader,
- behåller tydlig signal på 12 månader,
- minskar även MAE och negativ bias.

Family1 narrow BAS YoY:
- behålls endast som diagnostisk referens,
- bör inte vara huvudkandidat för 6–12 månader.

## Status

12-månaders bakåtblick:
**VALD REFERENSSPECIFIKATION FÖR NÄSTA KÄNSLIGHETSSTEG**

Detta är fortfarande inte en produktionspromovering.

## Nästa steg

Testa alternativa bakåtblicksfönster som challengers mot denna låsta referens:

1. 9 månader
2. 6 månader
3. eventuellt 3 månader

Varje challenger ska använda:
- samma featurefamilj 25–29,
- samma två arbetsmarknadsgrader,
- samma forecast origins,
- samma targetperioder,
- samma lag 1/2,
- samma alpha 3/10/30,
- samma 3/6/9/12 månaders prognoshorisonter.

Ingen feature-reselection får ske.
