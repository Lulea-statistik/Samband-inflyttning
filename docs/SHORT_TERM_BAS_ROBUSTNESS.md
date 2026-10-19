# Kortsiktig månadsmodul – BAS-robusthet

Familjeablationen pekar ut BAS som den enda kandidatfamiljen som konsekvent ligger nära säsongsbaslinjen och som bär nästan hela den förbättring som syns efter 2025.

Detta test håller därför BNP och asyl utanför och jämför fasta BAS-representationer:
- arbetsställe + bostad, årstakt
- endast arbetsställe/bostad-gap
- årstakt + gap
- 3-månadersförändring + gap
- 6-månadersförändring + gap
- årstakt + 3-månadersförändring

Varje representation testas med Ridge alpha 3, 10 och 30.

Ingen variant får produktionsstatus från detta test ensam. Signalen ska vara robust över flera horisonter och regulariseringsnivåer.
