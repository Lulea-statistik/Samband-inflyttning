# Kortsiktig månadsmodul – kandidatfamilj 2 gruppbenchmark

Första modelltestet använder små fördefinierade grupper i stället för att stoppa in alla family-2-kolumner samtidigt.

Grupper:
- student/unga
- arbetslöshet
- arbetsmarknadsgrader
- bred arbetsmarknadsstatus
- inrikes/utrikes födda
- nyregistrerade personbilar

Varje grupp används som Ridge-korrigering av samma säsongsnaiva benchmark. Alla horisonter +3, +6, +9 och +12 månader testas med strikt rolling-origin och läckagekontroll.

Månadsinkomst är inte med i huvudbacktestet eftersom serien börjar 2025.
