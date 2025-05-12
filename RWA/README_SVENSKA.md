## 📈 Om CMT-data (Constant Maturity Treasury)

Detta projekt använder **CMT-data** (Constant Maturity Treasury) från **FRED** (Federal Reserve Economic Data), tillhandahållet av **Board of Governors of the Federal Reserve System (US)** via daglig publicering i *H.15 Selected Interest Rates*. 

CMT-serier representerar **avkastning på amerikanska statsobligationer interpolerade till konstruerade löptider** (t.ex. 1, 2, 5, 10, 20 eller 30 år). Dessa är inte faktiska obligationsavkastningar utan **parräntor** som härleds genom en monotont konvex interpolationsmetod baserat på marknadsdata. 

Dessa implicita räntor konstrueras utifrån indikativa bud-sidiga prisnoteringar på de senast auktionerade obligationerna. Räntorna används av det amerikanska finansdepartementet för att skapa en kontinuerlig avkastningskurva – en viktig referens för ränteanalys, durationsexponering och modellering av ränterisk.

### 🔍 Syfte i detta projekt

CMT-data används för att:
- Modella durationjusterade riskvikter enligt ett PDMM-Heston-ramverk (path-dependent multi-maturity),
- Fånga ränteexponering i HTM-portföljer,
- Skapa en teoretiskt jämförbar referenskurva för amerikanska bankers balansräkningskänslighet,
- Stödja stresstester och regulatorisk analys kopplad till Basel III-ramverket.

### 📦 Datakälla

- **Dataleverantör:** Board of Governors of the Federal Reserve System (US)
- **Publikation:** *H.15 Selected Interest Rates*
- **Frekvens:** Daglig
- **Enhet:** Procent (ej säsongsjusterad)
- **Källa:** [https://fred.stlouisfed.org/series/DGS30](https://fred.stlouisfed.org/series/DGS30)
- **Senaste åtkomst:** 12 maj 2025

> 💡 **CMT-serierna kan förändras** enligt Treasury's metodologiska uppdateringar, inklusive input-vikter och interpolationsstrategier. För detaljer, se avsnittet *Treasury Yield Curve Methodology* i H.15-dokumentationen.

### 📚 Citat (för akademisk användning)

> Board of Governors of the Federal Reserve System (US), *Market Yield on U.S. Treasury Securities at 30-Year Constant Maturity, Quoted on an Investment Basis* [DGS30], hämtad från FRED, Federal Reserve Bank of St. Louis; https://fred.stlouisfed.org/series/DGS30, 12 maj 2025.
