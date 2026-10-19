# Core-4: rolling population + SKR challenger

Forskningsspår som testar om den kvarvarande SKR-signalen har prognostiskt värde efter population-reliability-blenden.

## Armar
1. core-4
2. population-reliability-blend, fast C=10 000
3. population-reliability-blend + shrunk SKR-residual

SKR-korrigeringen för år t använder endast residualer från tidigare år. Ingen gruppkorrigering får använda utfallet för prognosåret.

Shrinkage: n/(n+30), med K=30 fast före testet. K optimeras inte på testperioden.

Testet är forskningsmässigt och ändrar inte produktionsmodellen.
