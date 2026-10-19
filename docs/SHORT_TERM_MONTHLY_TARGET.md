# Kortsiktig målserie – månadsvis flyttning

## Beslut

Den kortsiktiga modulen använder en separat månadsvis målserie för Luleå.

### Historik
- **2000M01–2024M12:** SCB `ManadBefStatRegion`
- **2025M01–:** SCB `MBefStatRegionCKM`

Båda tabellerna innehåller kommunvisa befolkningsförändringar såsom samtliga inflyttningar, utflyttningar, inrikes flyttningar, invandring och utvandring.

## Stitching

År 2025 markeras som käll-/metodbrytning. Serien får användas genom brytet, men:
- backtest rapporteras både totalt och separat före/efter brytet när det är möjligt,
- inga parametrar får väljas för att optimera just övergången 2024–2025,
- CKM från 2025 innehåller kontrollerad slumpmässig osäkerhet i publicerade uppgifter och behandlas därför som en ny källa.

## Primärt mål

Första versionen använder:
- `samtliga inflyttningar` per månad

Sekundära mål:
- samtliga inrikes inflyttningar
- invandringar
- samtliga utflyttningar
- flyttningsöverskott totalt

## Prognoshorisonter

För forecast origin månad t utvärderas framtida summerad inflyttning:
- t+1 … t+3
- t+1 … t+6
- t+1 … t+9
- t+1 … t+12

Detta motsvarar en faktisk korttidsprognos för kommande kvartal/halvår/tre kvartal/år.

## Benchmark

Minst:
1. säsongsnaiv: samma framtida månader föregående år
2. trailing-12 / säsongsprofil
3. makrobas + månadsmodul

Core-4 ändras inte.
