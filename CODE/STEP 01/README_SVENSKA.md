# STEP 01 — Förbehandling: TXT till CSV med FDIC-certifikatskomplettering

## Översikt

Detta förbehandlingsskript konverterar FFIEC Call Report-`.txt`-filer till ett standardiserat `.csv`-format. Det lokaliserar och laddar projektspecifika sökvägar dynamiskt, bearbetar varje kvartalsmapp med textfiler, extraherar FDIC-certifikatsnumret (`FDIC CERT`) med hjälp av `POR`-filen och skriver ut rensade och kompletterade `.csv`-filer i en strukturerad undermappslayout.

De färdiga filerna sparas i: <ROOT_DIR>`Call Report/CSV/Schedules/`

---

## Beroenden

- Python ≥ 3.6  
- `csv`, `os`, `sys`, `importlib.util`

## Funktionalitet

- **Dynamisk sökvägsupplösning**  
  Lokaliserar `Basel3_Global_Filepath.py` oavsett var den finns på systemet.

- **Katalogskapande**  
  Säkerställer att nödvändiga kataloger under `/TXT` och `/CSV` finns.

- **Komplettering med FDIC-certifikat**  
  Använder `FFIEC CDR Call Bulk POR.txt` för att matcha `IDRSSD → FDIC CERT`.

- **Batchkonvertering TXT → CSV**  
  Konverterar alla icke-POR-`.txt`-filer i kvartalsundermappar till `.csv`-format och injicerar FDIC-certifikatsnumret som andra kolumn.

- **Felfångst**  
  Hoppar över undermappar som saknar giltig `POR`-fil eller `IDRSSD`-mappning.

## Utdatstruktur

Varje `.csv`-utdatafil kommer att innehålla:

1. `IDRSSD` — Institutionsidentifierare  
2. `FDIC Certificate Number` — Mappad från POR-filen  
3. Återstående kolumner — Ursprungliga schemakolumner  

---

## Användning

Säkerställ följande:

1. `Basel3_Global_Filepath.py` finns och definierar `ROOT_DIR`.  
2. FFIEC Call Report-textdata placeras i: <ROOT_DIR>`Call Reports/TXT/`  
3. Filerna är nedladdade från FFIEC CDR, uppackade, och datumformatet för slutdatum är konverterat från MM:DD:YYYY → YYYY:MM:DD  
