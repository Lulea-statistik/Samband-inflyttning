# Kortsiktig precisionsmodul – kandidatfamilj 1

## Syfte

Den kortsiktiga modulen ska komplettera den frysta långsiktiga core-4-modellen med månadsvisa signaler för ungefär 3, 6, 9 och 12 månaders prognoshorisont.

Den får **inte** ändra core-4 eller dess variabelurval. Den ska i stället modellera kortsiktiga avvikelser runt makrobasen.

## Kandidatfamilj 1

| Källa | Roll | Primär geografi | Frekvens | Första användning |
|---|---|---|---|---|
| SCB BAS, YrkStallningM | Lokal arbetsmarknad | kommun | månad | sysselsättningsmomentum |
| SCB månadsbefolkning, MBefStatRegionCKM | Lokal realtid/demografi | kommun | månad | flytt- och befolkningsmomentum |
| SCB BNP-indikator | Nationell konjunktur | riket | månad | konjunkturkontroll |
| SCB asylsökande, AsylsokandeN | Exogen migrationssignal | riket | månad/kvartal | migrationschock |

## Prognoshorisonter

Separata horisonter ska testas:
- +3 månader
- +6 månader
- +9 månader
- +12 månader

Informationsvärdet får avta med horisonten; därför ska ingen gemensam koefficientuppsättning antas i förväg.

## Första härledda signaler

### BAS
- nivå
- årsförändring
- 3-månaders momentum
- 6-månaders momentum
- arbetsställe minus bostad som lokal arbetsmarknadsbalans
- endast laggade värden som var publicerade vid prognosdatumet

### Månadsbefolkning
- folkmängdens årstakt
- 3- och 6-månaders förändring
- inrikes inflyttning och utflyttning när dessa finns i tabellen
- invandring och utvandring när dessa finns i tabellen
- nettoflyttning och komponenter
- kort historik från CKM behandlas som realtidsindikator och får inte ge sken av lång backtesthistorik

### BNP-indikator
- säsongsrensat index
- säsongsrensad månadsförändring
- kalenderkorrigerad årsförändring
- 3-månaders momentum

### Asylsökande
- månadsnivå
- rullande 3-månaderssumma
- årsförändring
- endast exogen nationell signal; ingen direkt kommunfördelning antas utan separat test

## Realtidsprincip

Varje kandidat ska ha:
- referensmånad
- faktisk publiceringsdag eller dokumenterad normal publiceringslagg
- revisionsstatus
- första och sista tillgängliga period
- geografi
- eventuell definitions-/metodbrytning

Backtest ska bygga på information som rimligen var tillgänglig vid respektive forecast origin.

## Modellprincip

Kortsiktsmodulen ska i första hand förklara:
`utfall - makrobas`

och inte ersätta den långsiktiga makromodellen.

Första benchmark:
1. makrobas/core-4
2. makrobas + enkel persistence/momentum
3. makrobas + kortsiktiga månadsindikatorer

Produktionsstatus kräver rolling-origin-förbättring på flera forecast origins och flera horisonter.
