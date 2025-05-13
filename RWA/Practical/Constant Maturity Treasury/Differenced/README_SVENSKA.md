# Generera rullande 1-åriga ränteschocker (Differensierade avkastningskurvor)

## Syfte

Detta steg omvandlar avkastningsdata för **Constant Maturity Treasury (CMT)** till **framåtriktade differenser över ett år**, vilket simulerar 1-åriga förändringar i räntestrukturen. Detta format är användbart för:

- **Volatilitetsestimering**
- **Scenarioanalys**
- **Kalibrering av chocker enligt Basel III**

---

## Indata

Rensade och sammanslagna avkastningskurvor producerade i **Steg 9**:

`/RWA/Practical/Constant Maturity Treasury/Cleaned/`

Varje fil måste innehålla:
- En kolumn `observation_date`
- Flera avkastningskolumner (t.ex. `DGS1`, `DGS5`, `DGS10`, etc.)

---

## Utdata

Skriptet genererar framåtdifferensierade filer i:

`/RWA/Practical/Constant Maturity Treasury/Differenced/`

Utdatanamnet följer formatet: `differenced_<original_file>.csv`

---

## Metod

1. **1-års förskjutning (Standard: 252 bankdagar)**:  
   För varje datum `t`, subtraheras räntan vid `t - 252` från räntan vid `t` för varje löptid.

2. **Filtreringströskel (Standard: 0.0)**:  
   Endast positiva differenser (`ΔRänta > tröskel`) behålls. Alla andra ersätts med tomma celler, vilket fokuserar på **renodlade chockscenarier**.

3. **Transformationslogik**:  
   För varje löptid:  
   - ΔRäntaₜ = Räntaₜ − Räntaₜ₋₂₅₂

4. **Kolumnnamn**:  
   - `observation_date` behålls  
   - Övriga kolumner motsvarar ursprungliga löptider (`DGS1`, `DGS10`, etc.)

---

## Exempelutdata (Head)

| observation_date | DGS1 | DGS5 | DGS10 |
|------------------|------|------|--------|
| 2023-12-29       | 0.30 |      | 0.15   |
| 2023-12-28       | 0.10 | 0.25 |        |
| ...              | ...  | ...  | ...    |

Tomma celler representerar noll eller negativa förändringar (filtrerade bort).

---

## Parametrar

- `offset = 252`  
  Antal bankdagar (~1 år) att förskjuta för differensberäkning

- `threshold = 0.0`  
  Minsta differens som ska behållas; övriga ersätts med `''`

---

## Användningsområde

Dessa framåtdifferensierade kurvor kan användas för att:
- Skatta empiriska chockfördelningar  
- Kalibrera volatilitetsparametrar i PDMM-Heston  
- Simulera historiska scenarier för stresstester  
