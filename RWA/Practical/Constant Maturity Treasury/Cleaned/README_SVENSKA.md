# Slå ihop och rensa FRED-data för statsobligationer med konstant löptid

## Syfte

Detta steg konsoliderar flera **Constant Maturity Treasury (CMT)**-serier från FRED-databasen till en enhetlig tidsserie. Alla räntor justeras efter datum, saknade värden fylls i framåt i tiden, och resultatet blir färdigt för användning i durationkänslig Basel III-modellering.

- Kör först `Constant_Maturity_Treasury_Cleaned2a.py`

---

## Indata

Dagliga räntedata för statsobligationer (nedladdade från FRED):

| Löptid   | Filnamn     |
|----------|-------------|
| 1 år     | `DGS1.csv`  |
| 3 år     | `DGS3.csv`  |
| 5 år     | `DGS5.csv`  |
| 10 år    | `DGS10.csv` |
| 20 år    | `DGS20.csv` |
| 30 år    | `DGS30.csv` |

Filerna förväntas ligga i:

`/RWA/FRED/`

### `observation_date` är för närvarande inte korrekt formaterad  
Varje fil måste innehålla:
- En kolumn `observation_date` (t.ex. `12/31/23`)
- En kolumn för räntesatsen (t.ex. `DGS10`)

---

## Utdata

Skriptet genererar:

`/RWA/Practical/Constant Maturity Treasury/Cleaned/combined_fred_treasury_data.csv`

Denna utdata:
- Har en rad per `observation_date`
- Innehåller kolumner för varje löptids ränta
- Sorteras i **omvänd kronologisk ordning**
- Fyller i saknade värden via **backfill** (`bfill`)

---

## Metod

1. **Ladda `Basel3_Global_Filepath.py`** för att dynamiskt lösa sökvägar  
2. Läs in alla CMT-serier med `'observation_date'` som nyckel  
3. Slå ihop serierna horisontellt efter datum  
4. Konvertera `observation_date` till datetime och sortera fallande  
5. Fyll i saknade räntor med nästa tillgängliga framtida värde  
6. Skriv resultatet till `combined_fred_treasury_data.csv`

---

## Exempelutdata (Head)

| observation_date | DGS1 | DGS3 | DGS5 | DGS10 | DGS20 | DGS30 |
|------------------|------|------|------|-------|-------|-------|
| 2023-12-29       | 4.85 | 4.63 | 4.52 | 4.12  | 4.05  | 4.00  |
| 2023-12-28       | 4.82 | 4.60 | 4.50 | 4.10  | 4.03  | 3.98  |
| ...              | ...  | ...  | ...  | ...   | ...   | ...   |

---

## Användningsområde

Denna enhetliga Treasury-dataset används för:
- **Räntestrukturmodellering**
- **Kalibrering av riskvikter**
- **Interpolering av avkastningskurvor**
- **Scenariogenerering i RWA/PDMM-Heston-modeller**

---

## Nästa steg

Fortsätt till **Differencing**: `Constant_Maturity_Treasury_Differenced5a.py`  
- Katalogstrukturen håller på att fixas
