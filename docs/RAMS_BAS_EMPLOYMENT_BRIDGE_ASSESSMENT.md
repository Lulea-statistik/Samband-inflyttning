# RAMS–BAS: sysselsättning efter bostadskommun och arbetsställekommun

Status: explorativ nivåjämförelse, 2026-10-14. Underlag: [rams_bas_employment_level_bridge.json](data/rams_bas_employment_level_bridge.json), framgångsrik Actions #38599277015. **Ingen sammanfogad produktionsserie och ingen modelländring.**

## Överlapp 2020–2021

BAS minus RAMS, uttryckt som nivåskillnad i procent av RAMS.

| Indelning | Median 2020 | Median 2021 | Antal kommuner med absolut avvikelse >5 % 2021 |
|---|---:|---:|---:|
| Bostadskommun | +0,208 % | +0,406 % | 2 |
| Arbetsställekommun | +0,231 % | +0,400 % | 5 |

Median absolut logförändring i BAS/RAMS-kvot mellan åren: bostadskommun 0,00275 (~0,28 %), arbetsställekommun 0,00520 (~0,52 %). 90:e percentil 0,00754 respektive 0,01639.

Luleå: BAS/RAMS bostadskommun 2020 **0,99841**, 2021 **1,00086**; arbetsställekommun 2020 **1,00098**, 2021 **0,99955**.

## Fortsatt granskning före att använda syntetiskt historiskt förlängda serier

1. **Tre separata regimer:** RAMS 2004–2018, RAMS/AGI 2019–2021 och BAS 2020–2024. De ska behålla regimetiketter. Beskriv skillnader i populationsdefinition, ålder och redovisning; samma antal betyder inte nödvändigtvis identiska definitioner.
2. **Bro 2020–2021:** testa utan justering och med kommunvis, robust nivåkvot. Krymp extremt brusiga kommunfaktorer mot riksnivån; använd enbart överlapp från träningstidpunkten vid historiskt prognostest. En bro kan inte ha 2021 som känd information i ett test med ursprung före 2021.
3. **2018/2019-brottet:** saknar direkt dubbelmätt nivåserie. Skilj möjlig verklig förändring från metodomläggning med stöd av SCB-dokumentation och stabilitet i regionala trender; skapa inte en automatisk faktor på basen av ett enstaka års differens.
4. **Kommunspecifik diagnostik:** granska de 2 respektive 5 kommunerna med >5 % BAS–RAMS-avvikelse 2021, stora årsförändringar och skillnader i effekten av val av bryggmetod.
5. **Variabeldefinition:** bostadskommun = bor och arbetar i samma kommun + utpendlare; arbetsställekommun = lokalt arbetande + inpendlare. Ställ dessa bredvid den ursprungliga BAS-definitionen före användning av nivåer och differenser.
6. **Validering:** analys av årlig tillväxt i sysselsättning ska göras separat för arbetställe och bostad, inom regimer och över bryggan. Jämför rå nivå, nivåjusterad och explicit brytindikator. Först därefter eventuellt gemensamt forskningspanelmaterial med metadata.
7. Den historiska publiceringstidpunkten måste verifieras separat. 2023–2024 är redan inspekterade prognosår och inte orörda testdata.

## Tolkning

En liten BAS–RAMS-nivåskillnad 2020–2021 gör en historisk förlängning tekniskt lovande, men bevisar inte att de två serierna eller deras förändringstal är metodmässigt utbytbara över 2018/2019 och 2020/2021. Ingen utjämning ska ta bort faktiska sysselsättningsförändringar.
