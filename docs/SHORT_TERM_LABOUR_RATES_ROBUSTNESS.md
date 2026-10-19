# Kortsiktig månadsmodul – robusthet för arbetsmarknadsgrader

Family-2 benchmark visar den första tydligt lovande signalen för huvudhorisonten:
- +6 månader: cirka 1,2 % lägre RMSE än säsongsnaiv
- +9 månader: cirka 5,1 % lägre RMSE
- +12 månader: cirka 7,4 % lägre RMSE

Gruppen består av årsförändring i procentenheter för sysselsättningsgrad och arbetskraftsdeltagande bland 20–24 och 25–29 år.

Robusthetstestet delar därför upp signalen i:
- sysselsättningsgrad per ålder och tillsammans
- arbetskraftsdeltagande per ålder och tillsammans
- båda måtten inom respektive åldersgrupp
- full kombination

Alla armar testas med Ridge alpha 3, 10 och 30. Ingen kandidat får produktionsstatus från detta test ensam.
