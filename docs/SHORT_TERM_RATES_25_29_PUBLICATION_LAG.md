# BAS 25–29 år – pseudo-realtime och publiceringslagg

Den provisoriska kandidaten använder:
- årsförändring i sysselsättningsgrad, procentenheter, 25–29 år
- årsförändring i arbetskraftsdeltagande, procentenheter, 25–29 år

Testet jämför samma fasta featurepar vid:
- lag 0 månader: hindsight-övre gräns
- lag 1 månad: föregående publicerade månad
- lag 2 månader: konservativ realtime-approximation

Ingen featurefamilj ändras mellan lagginställningarna. Ridge alpha 3, 10 och 30 testas. Huvudbedömningen gäller +9 och +12 månader.
