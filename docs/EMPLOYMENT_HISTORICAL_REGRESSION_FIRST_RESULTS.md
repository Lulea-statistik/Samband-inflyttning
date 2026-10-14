# Historiskt regressionstest av sysselsättningstillväxt – första tolkning

Källa: [testresultat](data/employment_historical_fixed_regression_test.json) och [lyckad GitHub Actions-körning #38606426045](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38606426045).

## Upplägg
Retrospektiv, explorativ analys av inflyttning per 1 000 invånare. Samma 290 kommuner och 3 föregående kommun-år (870 observationer) i varje årstest. Basmodell med laggad log-folkmängd och laggad tätortsgrad. Tre tillägg jämförs: sysselsättningstillväxt efter bostadskommun, efter arbetsställekommun och båda. Ridge, fast alpha=10; ingen sökning efter bästa hyperparameter utifrån teståret.

| Testår | Bas RMSE | Bostad RMSE | Arbetsställe RMSE | Båda RMSE |
|---|---:|---:|---:|---:|
| 2009 | 13,358 | 12,717 | 12,979 | 12,772 |
| 2010 | 12,451 | 16,258 | 13,270 | 16,281 |
| 2011 | 12,749 | 12,759 | 12,739 | 12,756 |
| 2016 | 18,604 | 17,829 | 18,465 | 17,862 |
| 2017 | 16,686 | 16,273 | 16,435 | 16,275 |
| 2018 | 16,448 | 16,216 | 16,402 | 16,216 |
| 2019 | 17,542 | 15,848 | 17,037 | 15,871 |
| 2024* | 14,187 | 13,940 | 13,952 | 13,915 |

*2024 tidigare frekvent inspekterat; ej oberoende modellvalsår.*

**Tolkning:** Bostadstillväxt förbättrar RMSE 6 av 8 rapporterade testår, men 2010 ökar RMSE markant (12,451 till 16,258). De övriga förbättringarna bevisar inte en stabil effekt och 2010 får inte tas bort post hoc. Bostadstillväxt 2011 i tränings-/testdefinitionen korsar inte det spärrade förändringsåret 2010–2011: testår 2011 har förändring 2009–2010, men utfall under 2011 kan ändå påverkas av samtidiga konjunkturchocker. Betydelsen av krisperioden måste förstås innan en produktionskandidat godkänns.

## Särskilt viktig kalibreringsinsikt
En **konstant kommunvis BAS/RAMS-nivåfaktor** ger exakt samma procentuella förändring inom en RAMS-delperiod. Detta test visar därför värdet av **historisk sysselsättningstillväxt**, inte att den BAS-justerade serien i sig förbättrar tillväxtregressionen relativt ojusterad RAMS. Nivåvärden och indikatorer över regimgränser kräver ett separat test.

## Nästa robusthetsgrind
1. Kartlägg 2010-försämringen med tränings-/testfördelning, extrema kommunvärden, teckenskiften och påverkan av finanskrisens återhämtning. Alla år skall rapporteras.
2. Undersök robusta, **förhandsdefinierade** alternativ som winsorisering utifrån enbart träningsperioden och användning av enbart arbetsställe- eller bostadsbaserat tillväxtmått; inte välja tröskel genom att optimera 2010.
3. Utvärdera 3-/5-åriga träningsfönster när båda är historiskt komplett täckta, inte blandade stickprov. Redovisa beroendet mellan rullande testår och geografisk osäkerhet.
4. Jämför med befintlig rikare strukturmodell på **samma rader** innan någon ny variabel marknadsförs som bättre än dagens modeller.
5. Publiceringsdatum för de exakta SCB-värdena och en fixerad prognostidpunkt behövs för att resultaten skall kunna användas för genuint prognostest.
6. Ingen ändring av produktionsmodellen eller av standardvariabler utan en separat beslutsgrind.

**Status: hypotesgenererande; ingen produktionsevidens.**
