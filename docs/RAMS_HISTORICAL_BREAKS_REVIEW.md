# RAMS: kontroll av metodbrott 2011 och 2019

Resultat från [rams_2011_2019_break_diagnostic.json](data/rams_2011_2019_break_diagnostic.json), GitHub Actions [#38600057390](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38600057390). Status: explorativ; ingen produktionsändring.

| Kommunvis mått | 2011 medianavvikelse från 3 föregående års medianförändring (procentenheter) | 2019 motsvarande | Antal kommuner abs(avvikelse) >5 pp 2011 / 2019 |
|---|---:|---:|---:|
| Sysselsatta efter bostadskommun | +2,798 | −0,240 | 41 / 0 |
| Sysselsatta efter arbetsställekommun | +3,171 | −0,206 | 73 / 16 |

Luleå: bostadskommun årlig förändring 2011 +2,599 %, 2019 −0,692 %; arbetsställekommun 2011 +2,508 %, 2019 −0,261 %.

## Viktig tolkning
Måttet jämför ett brytår mot kommunens historiska medianförändring och **identifierar inte statistisk bryteffekt kausalt**. Särskilt 2011 kan påverkas av återhämtning efter finanskrisen och förändrad arbetsmarknad. 2019 saknas parallella observationsserier för att direkt skatta brottets nivåskillnad. En gemensam automatisk korrigeringsfaktor är därför inte motiverad.

## Fortsättning – avskilj från produktionsdata
1. Kontrollera äldre [AM0207PendlKomA04](https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__AM__AM0207__AM0207L/AM0207PendlKomA04/) mot redan importerad `PendlingK` för några utvalda år och alla kommuner; verifiera lokal-, in- och utpendling samt totalmått (inklusive okänt arbetsställe och eventuella tabellavvikelser).
2. Behåll tre etiketterade källregimer: RAMS 2004–2018, RAMS/AGI 2019–2021 och BAS 2020–2024. Verifiera ålders- och definitionsskillnader.
3. Innan sammanfogning: jämför årliga förändringar med dels ojusterad serie, dels bro med osäkerhetsintervall, dels brytindikator i prognosmodellen. En brytindikator gör inte ensam regimerna helt jämförbara.
4. Testa konsekvens för regressionsmodellens geografiska jämförelser *utan* att upprepade 2024-försök styr modellvalet. Bevara valideringsåren och publiceringstidpunkt.
5. Godkänn inte justeringar innan äldre seriers definition och brytårsosäkerhet har dokumenterats.

**Ingen sammanslagning, bakåtjustering eller produktionsmodelländring är beslutad.**
