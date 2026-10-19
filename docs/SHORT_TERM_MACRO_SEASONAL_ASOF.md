# As-of makro + säsong – första backtest

Detta test använder den frysta core-4 årsmodellen utan att ändra dess variabler eller refitregel.

För varje historisk forecast origin testas +7, +10 och +14 dagar efter årets faktiska SCB-riksprognos.

Regler:
- endast origins som är operationellt möjliga enligt as-of-tabellen används,
- säsongsprofil byggs endast från tidigare kompletta kalenderår,
- core-4 årsprognos omvandlas från inflyttning per 1 000 till ett årsankare med senast observerad befolkning före origin,
- core-4-ankaret används endast för återstående månader inom forecast year Y,
- månader i Y+1 använder säsongsnaiv nivå; nästa års core-4-prognos får inte användas i förtid.

Detta är en gate för att avgöra om annual core-4 ger mervärde som månadsbaseline. `rates_25_29` läggs inte på förrän denna baslinje är utvärderad.
