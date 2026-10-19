# Kortsiktig månadsmodul – familjeablation

Syftet är att avgöra om den eventuella korttidssignalen bärs av BAS, BNP eller asylstatistik.

Alla varianter testas på exakt samma forecast origins och med samma Ridge-inställning.

Armar:
- säsongsnaiv
- BAS
- BNP
- asyl
- BAS + BNP
- BAS + asyl
- BNP + asyl
- alla tre

Ingen ny feature selection görs i detta steg. Resultatet används för att avgöra vilken kandidatfamilj som är värd nästa robusthetstest.
