# SCB-källvintages: första belagda publiceringsankare (2026-10-15)

Status: **publiceringsbelägg på statistikprodukt-/årgångsnivå**, ännu inte verifierad as-of-behörighet för enskilda modellvariabler.

## Belagda ankare

| Statistik | Referensperiod | Publiceringsbelägg | SCB-källa | Slutsats |
|---|---|---|---|---|
| RAMS, sista årgången | 2021 | 2022-11-24 | https://www.scb.se/am0207 | RAMS 2021 kan inte ha varit tillgänglig före detta datum. RAMS 2019 har metodförändring mot AGI. |
| BAS, statistikproduktens start | januari 2020 och framåt | Maj 2022, första produktpublicering | https://www.scb.se/hitta-statistik/temaomraden/sveriges-ekonomi/fordjupningsartiklar_Sveriges_ekonomi/ny-arbetslosheten-okar-for-inrikes-fodda/ | Att 2020 ingår som referensperiod innebär inte att alla BAS-tabeller var tillgängliga 2020. Publiceringsdatum för exakt tabell och årgång återstår. |
| Befolkningsstatistik helåret 2023 | 2023 | 2024-02-22 kl 08 | https://www.scb.se/hitta-statistik/statistik-efter-amne/befolkning-och-levnadsforhallanden/befolkningens-sammansattning-och-utveckling/befolkningsstatistik/pong/statistiknyhet/befolkningsstatistik-helaret-2023/ | Fullårsbefolkning 2023 ej offentligt redovisad via denna release vid början av 2024. Kontroll av tidigare preliminära tabeller och databasvintage krävs. |
| Bostadsbestånd per 31 dec 2023 | 2023 | 2024-04-18 kl 08 | https://www.scb.se/hitta-statistik/statistik-efter-amne/boende-bebyggelse-och-mark/bostader-och-boende/bostadsbestand/pong/statistiknyhet/bostadsbestandet-31-december-2023/ | Komplett helårsbostadsbestånd 2023 ej publicerat via denna release vid ingången av 2024. Kontroll av exakta tabeller behövs. |

## Tillämpning

För målår 2024 definieras minst två **separata forskningsscenarier** som inte får jämföras som samma informationsuppsättning:
- Ursprung **2024-01-01**: de ovannämnda helårsstatistikerna för 2023 kan inte antas vara tillgängliga; tillåt endast verifierade tidigare årgångar.
- Ursprung **2024-05-01**: SCB:s ovan angivna helårsreleaser har passerat; detta bevisar dock *inte* att varje härledd kolumn i `panel.csv` existerade eller hade samma värde i dåvarande statistikdatabas.

Ingen prognos- eller CV-beräkning skall köras som strikt as-of innan variabel-till-tabell-koppling, publiceringsarkiv, eventuella revideringar samt transformationskedjan är verifierade. Den nuvarande neutrala rapporten har 80 variabler och 0 individuellt as-of-godkända.

## Nästa kontroll
1. Extrahera källkonstanter och ursprungstabellernas ID för befolknings-, bostads-, arbetsmarknadsvariabler i `scripts/build_analysis.py`.
2. Matcha var och en mot SCB:s äldre statistiknyheter, kvalitetsdeklarationer och en versionsbevarad datakälla.
3. Spärra automatiskt varje variabel som saknar datering **före det explicita prognosursprunget**.
4. Rekonstruera befintlig aktiv produktionsmodell separat innan direkt utvärdering.

**Detta dokument registrerar belagda källankare; det uppgraderar inte en enda modellvariabel till historiskt verifierad.** Produktionsmodellen ändras inte.
