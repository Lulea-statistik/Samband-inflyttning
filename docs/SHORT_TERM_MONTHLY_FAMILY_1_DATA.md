# Kortsiktig månadsdata – kandidatfamilj 1

Denna byggkedja hämtar de första fyra korttidskällorna direkt från SCB:s API och skapar en gemensam månadsfil.

## Innehåll
- Luleå: BAS sysselsättning efter arbetsställe och bostad
- Luleå: CKM befolkningsförändringar
- Riket: BNP-indikatorns publicerade månadsserier
- Riket: asylsökande per månad

Råvärden sparas först. Härledda årstakter och 3-/6-månadersförändringar byggs därefter.

Ingen prognosmodell skattas i detta steg. Tabellen är en kandidatmatris för kommande realtids- och rolling-origin-test.
