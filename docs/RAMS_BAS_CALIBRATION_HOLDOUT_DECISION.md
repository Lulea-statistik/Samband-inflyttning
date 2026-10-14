# Validering av RAMS till BAS: holdout på överlappsåren

Källa: [årligt utelämnat överlappsår](data/rams_bas_calibration_loo_comparison.json), [GitHub Actions #38603757061](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38603757061), avslutad med framgång 2026-10-14.

## Tvåvägs 2020–2021 holdout

Justera på 2020 och utvärdera 2021, därefter omvänt. Genomsnittligt absolut procentuellt nivåfel över 580 parvisa observationer per mått:

| Strategi | Bostadskommun | Arbetsställekommun |
|---|---:|---:|
| Ingen justering | 0,576 % | 1,062 % |
| Gemensam nationell median, log-skala | 0,534 % | 1,038 % |
| Full kommunvis nivåjustering | **0,364 %** | **0,783 %** |
| 40 % kommunvis, 60 % nationell | 0,412 % | 0,809 % |

Full kommunvis justering är bästa **nationella nivåfelkandidat** i detta överlappstest. Den gör nivån jämförbar, men en tidskonstant faktor kan inte ändra årsvisa procentuella förändringar. Den löser därför inte tillväxtskillnaden mellan RAMS och BAS. Detta är **inte en produktionströskel**.

Luleå: ojusterade undanhållna nivåfel (2021 respektive 2020), bostadskommun 0,086 % och 0,159 %, arbetsställekommun 0,045 % och 0,098 %. Full kommunvis justering ökar här felen till 0,245 % och 0,245 % för bostadskommun samt ungefär 0,144 % för arbetsställekommun. **Använd därför inte kommunvis faktor automatiskt för Luleå.** Notera att vinst/förlust för varje kommun har bedömts med samma två observerade år; detta räcker inte för datadrivet kommunvis metodval.

## Beslut för forskningsspåret

1. Behåll tre parallella, tydligt märkta alternativ: original-RAMS, nationell BAS-kalibrering och full kommunvis BAS-kalibrering. Den tidigare 40/60-serien är en fjärde känslighetsvariant, inte huvudval.
2. BAS 2020–2024 är normerande för nivåer från och med 2020. Varken justering med konstant faktor eller interpolering ska användas för att tvinga historiska tillväxttal till BAS-tillväxt.
3. Utvärdera abrupt metodbrott 2011 och 2019 samt revisionskänslighet. För 2018/19 saknas direkt överlapp och man kan inte identifiera metodandel från observerad tidsförändring.
4. Kräv historiskt tillgängliga prediktorer och temporalt/geografiskt robusta regressionstester innan användning som kandidat i prognos eller demografiskt blind strukturmodell.
5. Alla modellkörningar ska dokumentera källa, regim och justeringsmetod; rådata lämnas oförändrade.

### Begränsning

Endast ett års verklig överlappstillväxt kan utvärderas. Tvåvägs-holdout är i praktiken återanvändning av samma två kalenderår i omvänd riktning; utfallen är beroende och kan inte ses som två oberoende replikationer. Den optimala nivåkorrigeringen för 2004–2018 eller för ett enskilt år kan därför inte garanteras.

**Produktion: oförändrad. Ingen modell eller rådatakälla uppdaterad.**
