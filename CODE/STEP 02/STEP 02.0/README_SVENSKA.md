# Steg 02 — Slå ihop Call Report-scheman till rensade kvartalsvisa CSV-filer

## Översikt

Detta skript konsoliderar FFIEC Call Report-scheman från varje kvartal till en enhetlig `.csv`-fil på banknivå. Det sammanfogar viktiga scheman till en basfil `ENT` (`Entity Information`) med `IDRSSD` som nyckel, hoppar över dubbletter och hanterar strukturella variationer över olika år.

Resultatet är en serie kvartalsvisa "Rensade Call Report"-filer som placeras i:
- <ROOT_DIR>`/Call Report/CSV/Cleaned/Cleaned_Call_Report_<YYYYMMDD>.csv`

Dessa rensade utdatafiler används direkt i **STEP 02.1**, där longitudinella transformationer, fördröjda nyckeltal och dynamiska mått beräknas för Jensen-Shannon-divergens (JSD), CET1 och modeller för likviditetsrisk.

---

### Katalogstruktur
<ROOT_DIR>/Call Report/
- `CSV/`: Undermapp som innehåller alla CSV-filer
  - `Cleaned/`: Innehåller individuella rensade scheman som CSV innan de slås ihop till en enhetlig kvartalsfil.
    - `FFIEC CDR Call Bulk All Schedules 20240630/`: Rensade scheman för ett specifikt kvartal.
      - `FFIEC CDR Call Schedule RC 03312024.csv`  
      - `FFIEC CDR Call Schedule RC-B 03312024.csv`  
      - etc.
  - `Schedules/`: Innehåller sammanslagna scheman per kvartal för vertikal och retrospektiv analys i `Interleaved/`.
  - `Interleaved/`:  
  - `Distributed/`:  
    - `RAW/`:  
    - `Cleaned/`:  
  - `Dynamic/`:  
    - `RAW/`:  
    - `Cleaned/`:  

---

## Viktiga Funktioner

### `find_code_dir()`
Traverserar mapphierarkin dynamiskt för att hitta `CODE/` och gör skriptet oberoende av absolut sökväg.

### `merge_files_sequentially(base_file_path, files_to_append, output_path)`
Slår ihop schema-CSV:er till en enskild DataFrame genom att lägga till kolumner sekventiellt. Ser till att kolumner endast läggs till om de inte redan finns.

### `determine_files_to_append(input_directory, subfolder)`
Returnerar en lista över förväntade schemanamn för ett givet kvartal. Logiken varierar beroende på:
- FFIEC:s formatversioner (som ändrats över åren)
- Antalet delar i varje schema

---

## Utdatstruktur

Varje `Cleaned_Call_Report_<YYYYMMDD>.csv` innehåller:

- En rad per bank (`IDRSSD`)
- Kolumner från:
  - ENT (metadata om institutet)
  - RC (balansräkning)
  - RC-B (värdepapper)
  - RC-R Del I och II (kapital)
  - RC-O (off-balance sheet-poster)
  - RCE (eget kapital)
  - Övriga scheman beroende på år

---

## Användning

Säkerställ att:

1. Du har kört **Steg 01** och genererat `.csv`-scheman i:
   - <ROOT_DIR>`/Call Report/CSV/Schedules/<YYYYMMDD>/`
