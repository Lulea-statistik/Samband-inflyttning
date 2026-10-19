# Historical forecast-origin as-of table

Den här tabellen kopplar varje historiskt prognosår till en realistisk forecast origin baserad på SCB:s faktiska riksprognosdag + 10 dagar.

Syftet är att avgöra vilka års- och månadsvariabler som faktiskt var tillgängliga vid prognostillfället.

Viktigt:
- befolkning/flyttning för Y-1 används när publicerad före origin,
- bostadsbestånd använder faktisk dag där känd, annars konservativ fallback,
- Kolada arbetslöshet markeras tills vidare som ej fullständigt certifierad,
- BAS 25–29 hanteras separat med 1–2 månaders realtime-lagg.

Makro core-4 får inte kallas fullständigt as-of-certifierad förrän alla fyra predictorernas historiska publiceringstidpunkter är dokumenterade.
