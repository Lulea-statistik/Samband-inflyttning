# Kortsiktig månadsmodul – första rolling-origin-benchmark

Första testet är medvetet litet och förregistrerat i kod.

## Mål
Summerad Luleå-inflyttning under:
- kommande 3 månader
- kommande 6 månader
- kommande 9 månader
- kommande 12 månader

## Baslinje
Samma kalenderperiod ett år tidigare.

## Challenger
Ridge-modell som endast prognostiserar **korrigeringen från säsongsbaslinjen**.

Fasta indikatorer:
- BAS sysselsättning, arbetsställe, årstakt
- BAS sysselsättning, bostad, årstakt
- BAS arbetsställe/bostad-gap
- BNP kalenderkorrigerad årsförändring
- BNP säsongsrensad månadsförändring
- asylsökande, 3-månadersförändring

Ridge alpha = 10 och minsta träningsmängd = 24 origins är fasta före testet.

## Läckagekontroll
En historisk träningsobservation används endast om hela dess framtida målperiod hade avslutats senast vid den forecast origin som utvärderas.

Core-4 ändras inte och detta är research only.
