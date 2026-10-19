# Samband-inflyttning

Interaktiv analys av vilka kommunala faktorer som statistiskt samvarierar med inflyttning till svenska kommuner.

## Grundidé

Analysen byggs som paneldata där en observation är **kommun × år**.

Primära utfallsvariabler:

- antal inflyttade
- inflyttade per 1 000 invånare
- inrikes inflyttning
- invandring
- på sikt: inflyttning per åldersgrupp

Rapporten skiljer mellan tre huvudsakliga **analysuppgifter**:

1. **Fryst core-4-prognosmodell** – huvudmodell för nästa års inflyttning. Den använder föregående års inflyttning, utflyttning, arbetslöshet och förändring i bostadsbestånd. Variabeluppsättningen är fryst och öppnas inte av geografiska eftertester.
2. **Demografiskt blind strukturmodell** – söker strukturella samband utan tidigare migration, befolkningstillväxt, åldersstruktur eller inflyttarprofil som genväg.
3. **Prognososäkerhet och robusthet** – analyserar var core-4 får större fel och testar challengers. Befolkningsstorlek är den tydligaste felrisksignalen. SKR, demografi och geografi används främst som diagnostik och underlag för framtida osäkerhetsintervall, inte som automatisk punktkorrigering.

### Aktuell modellstatus, 2026-10-19

- **Core-4:** fryst huvudmodell.
- **Population/reliability-blend:** kvar som research-challenger. Den gav bättre total RMSE och p95 i den breda retrospektiva perioden 2019–2024 men var inte stabil varje enskilt år.
- **SKR/demografi/nord–syd:** används för felprofilering. C7/C8 har historiskt större överprognos, men nordkoordinaten i sig visar nästan inget linjärt residualsamband.
- **Rolling SKR-korrigering:** förkastad som punktprognos. Den försämrade RMSE med cirka 4,24 % jämfört med population-blenden 2020–2024.
- **Nästa gate:** prospektiv validering av population/reliability och utveckling av osäkerhetsintervall snarare än ytterligare geografisk efterkorrigering på samma retrospektiva data.


## Första kandidatvariabler

### Demografi
- folkmängd
- befolkningstillväxt
- åldersstruktur
- andel 20–34 år
- födelseöverskott
- tidigare års inflyttning och utflyttning

### Arbetsmarknad
- sysselsättningsgrad
- arbetslöshet
- antal sysselsatta
- utveckling av sysselsättning
- pendlingsrelaterade variabler där jämförbara kommunserier finns

### Ekonomi
- median/medel förvärvsinkomst
- inkomstutveckling

### Utbildning
- andel med eftergymnasial utbildning

### Bostäder
- bostadsbestånd per 1 000 invånare
- färdigställda bostäder per 1 000 invånare
- upplåtelseformer
- förändring i bostadsbestånd

### Inflyttarnas profil
Inflyttarnas åldersprofil och genomsnittsålder används primärt som **utfallsbeskrivning** eller i laggad form. Samma års profil ska inte användas som prognosförklarare eftersom den observeras samtidigt med utfallet.

## Modellstrategi

Baslinjer bör jämföras innan komplexare modeller införs:

- naiv modell: föregående års inflyttning
- enkel OLS
- multipel OLS
- kommun- och/eller årseffekter
- regulariserad regression (Ridge/Lasso/Elastic Net)
- vid behov icke-linjära jämförelsemodeller

Utvärdering ska inte bara göras med R² på träningsdata. Minst följande bör visas:

- R²
- justerat R²
- RMSE
- MAE
- out-of-sample R²
- residualdiagnostik
- multikollinearitet/VIF
- koefficienternas riktning och osäkerhet

Valideringen ska göras tidsmässigt, exempelvis träning till och med år t och test på t+1, så att framtida information inte läcker in i modellen.

## SCB-källor – start

Bekräftade kandidater i Statistikdatabasen:

- Migration efter region, ålder och kön
- Befolkning efter region och ålder
- Befolkning efter region, ålder och utbildningsnivå
- Sammanräknad förvärvsinkomst efter region
- Färdigställda lägenheter i nybyggda hus efter region
- Bostadsbestånd efter region och upplåtelseform
- Arbetsmarknadsvariabler på kommunnivå där en tillräckligt lång jämförbar tidsserie finns

## Rapportens tänkta sidor

1. **Översikt**
   - vald målvariabel
   - antal kommun-år
   - tidsperiod
   - bästa modell
   - R² / out-of-sample R² / RMSE

2. **Samband**
   - scatterplot mellan vald faktor och inflyttning
   - regressionslinje
   - korrelation
   - filter på år, kommuntyp och befolkningsstorlek

3. **Multipel regression**
   - koefficienter
   - standardiserade effekter
   - konfidensintervall
   - VIF
   - modelljämförelse

4. **Validering**
   - observerat mot predikterat
   - residualer
   - test per år
   - kommuner med störst över-/underskattning

5. **Kommunprofil**
   - välj kommun
   - faktisk och predikterad inflyttning över tid
   - vilka faktorer som bidrar mest till modellens skattning

6. **Prognososäkerhet & robusthet**
   - core-4 som fast referens
   - felprofil efter befolkningsstorlek, SKR, demografi och geografi
   - RMSE, MAE, P90/P95 och stora kommunfel
   - population/reliability som research-challenger
   - historiska geografiska modellförsök redovisas som diagnostik, inte som produktionsmodell

7. **Metod & data**
   - definitioner
   - datakällor
   - metodbrott
   - begränsningar

## Viktiga metodval

Absolut antal inflyttade kommer nästan automatiskt att korrelera starkt med kommunstorlek. Därför ska modellen alltid jämföras mot **inflyttning per 1 000 invånare**, alternativt använda folkmängd som offset/kontrollvariabel.

Samma års bostadsbyggande, arbetsmarknad och inflyttning kan påverka varandra. Prognosmodellen bör därför i första hand använda laggade förklaringsvariabler.
