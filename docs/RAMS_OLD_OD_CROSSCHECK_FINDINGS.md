# Kvalitetskontroll av äldre RAMS-kommunflöden

Uppdaterad 2026-10-14. Källa: [stickprovsrapport](data/rams_2004_2018_od_sample_crosscheck.json), [Actions #38601260400](https://github.com/Lulea-statistik/Samband-inflyttning/actions/runs/38601260400).

## Utfall

Detaljtabell `AM0207PendlKomA04` jämfördes med redan importerad `PendlingK` för 12 kommuner och åren 2008, 2011 och 2018, totalt 36 kommun-år.
- **Inpendling:** 36/36 observationer exakt identiska.
- **Utpendling:** 36/36 detaljsummor lägre än publicerad RAMS-summa. Detta är en systematisk definitions- eller täckningsskillnad, inte en slumpmässig summeringsavvikelse.
- **Luleå (2580):** utpendling 2008 3 799 mot detaljerad 3 772 (−27); 2011 3 994 mot 3 958 (−36); 2018 4 147 mot 4 133 (−14). Inpendling exakt densamma alla tre åren.
- **Göteborg (1480), 2018:** 53 341 mot 52 265 (−1 076).

## Tolkningsspärr

Differensen kan orsakas av arbetande med okänd arbetsställekommun, arbetsställe utomlands, ej kommunfördelade grupper eller annan avgränsning; **inget av detta är ännu verifierat**. Man får inte sätta differensen till noll, dra av den från anställda efter bostadskommun eller behandla den som verklig tillväxt utan stöd i SCB:s definitioner. Inpendlingens exakta överensstämmelse stödjer däremot att just den summeringen är korrekt.

## Nästa sakliga steg

1. Läs SCB:s tabellfotnoter och metadata för `AM0207PendlKomA04` och `PendlingK`; identifiera exakt vilka destinationer som ingår i deras respektive utpendlingsmått, särskilt okänd kommun/arbetsplats och kommun utanför Sverige.
2. Kontrollera tabellens alla kategori- och regionskoder innan eventuella nya API-uttag; inga antaganden om att alla destinationer måste vara en fyrsiffrig kommun.
3. Replikera kontrollen för 2018 med både totalsumma och eventuella särskilda kategorier, redovisa eventuell oförklarad residual separat och utan justering.
4. Om residualen identifieras, utvidga till 290 kommuner och 2004–2018. Använd inte detaljseriens kommunfördelade summa som enda täljare för sysselsatta efter bostadskommun.
5. Behåll `PendlingK`-seriens publicerade totaler för utvecklingsmått tills källornas avgränsningar dokumenterats; fortsätt separat analys av metodbrott RAMS 2019 och BAS 2020.

**Inga regressionskörningar, ingen ändring av panel eller produktionsmodell.**

## Källförklaring från SCB:s fotnot (2026-10-14)

SCB:s [PendlingK](https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__AM__AM0207__AM0207L/PendlingK/) anger uttryckligen under **Viktiga fotnoter** att tabellen inkluderar individer med svensk arbetsgivare och **arbetsställe i utlandet**. [AM0207PendlKomA04](https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__AM__AM0207__AM0207L/AM0207PendlKomA04/) har bostadskommun och arbetsställekommun som vardera innehåller 290 svenska kommuner. Detta ger en **sannolik** förklaring till att detaljmatrisen summerar till mindre utpendling än PendlingK medan inpendlingen överensstämmer exakt.

**Viktigt:** Fotnoterna visar inte ännu att *hela* differensen motsvarar utlandsplacerade arbetstagare. Dokumentera tills vidare `utpendling_RAMS_minus_summa_svenska_kommunpar` som **oidentifierad restpost, sannolikt utländska arbetsställen**. Läs inte restposten som bekräftat antal arbetstagare utomlands. Beräkning av sysselsatta efter bostadskommun bör fortsatt använda publicerad RAMS-total utan att restposten kastas bort.

SCB:s äldre detaljerade tabell anger vidare ett metodbrott 2011 där arbetsmarknadsstatus för 65+ förändras; det är en separat fråga från restposten. Den nyare detaljerade tabellen anger AGI-metodbrott 2019. 
