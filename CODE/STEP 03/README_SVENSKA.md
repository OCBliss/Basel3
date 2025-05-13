# Steg 03 — Feature-extraktion och interleaving av Call Report-observationer

## Översikt

Detta skript tar bankspecifika Call Report-CSV-filer från katalogen `/Cleaned/` och genererar analytiska features genom nyckeltalsberäkningar baserade på balansräkning, värdepapper och regulatoriska kapitalkomponenter.

Varje banks kvartalsvisa post bearbetas till två parallella observationer (`entry1` och `entry2`) från separata kolumnuppsättningar (RCON och RCFD). Dessa interleavas och avdubbleteras för att skapa en slutlig feature-vektor per bank och kvartal.

---

## Retrospektiva skript: CET1 och RWA-anmärkningar

Detta repo innehåller flera skript för vertikal aggregering av Call Report-data, med olika avvägningar mellan stabilitet och täckning:

### `call_reports_vertical_retrospective3c.py`
- ✅ **Stabilt** — ger **inga** typkonverterings- eller tvångsfel
- ✅ Behandlar historiska rapportstrukturer säkert för aggregering och linjering
- ❌ **Inkluderar ej** CET1-tröskelvärden eller durationjusteringar för riskvägda tillgångar (RWA)
- ➤ Rekommenderas för strukturell validering, pre-JSD eller filtersteg i pipen

### `call_reports_vertical_retrospective4.py`
- ✅ **Inkluderar** CET1-tröskelvärden och RWA-duration för kapitalkalibrering
- ⚠️ **Kan ge typkonverteringsfel** p.g.a. celler med procentformat (t.ex. `"34.5%"`) tolkas som strängar
- ✅ Dessa fel kan lösas manuellt:
  - Öppna `.csv`-filen i Excel  
  - Ändra kolumnformat från `Procent` → `Tal`  
  - Spara och kör skriptet igen
- ➤ Denna lösning fungerar konsekvent och möjliggör fullständig kapitalrekonstruktion

> 📌 Obs: Automatisk typkonvertering bör nu vara löst i version 1.0 av `call_reports_vertical_retrospective4.py`

---

## Indata

- Katalog: <ROOT_DIR>`/Call Report/CSV/Cleaned/`

Varje fil måste innehålla:
- `RCON9999` som heltalskodat datum
- FDIC-certifikatnummer tilldelade
- `RCON9224` borttaget (gjort i Steg 02.1)

---

## Utdata

- Katalog: <ROOT_DIR>`/Call Report/CSV/Interleaved/`

Varje utdatfil innehåller:
- En rad per `IDRSSD` (bank), med interleavade `entry1` och `entry2`
- Feature-kolumner som fångar:
  - AFS-till-HTM-kvoter
  - Marknadsvärde vs amortiserad kostnad
  - CET1 / RWA kapitalkvalitet
  - Nyckeltal baserade på RC, RC-B och RC-R
  - Löptidsspann för värdepapper
- Dubbletter hanteras genom att behålla raden med minst antal tomma celler

---

## Feature-metodik

- **Entry 1** härleds från variabler med prefix `RCON`  
- **Entry 2** härleds från variabler med prefix `RCFD`  
- Feature-beräkningarna använder villkorsstyrd logik beroende på kvartal för att hantera förändringar i rapportdefinitioner över tid

- Kategorier inkluderar:
  - **Balansräkningssammansättning:** Tillgångar/skulder/eget kapital (Schema RC)
  - **Värdepappersböcker:** HTM och AFS (Schema RC-B)
  - **Löptidsspann:** Baserat på omprisningshorisonter (Memoranda M2a, M2b)
  - **Regulatoriskt kapital:** CET1, CET1 justerat för AOCI, RWA (Schema RC-R)
  - **Domänspecifika kvoter:** t.ex. `G300` bostads-MBS jämfört med total exponering

---

## Användning

Säkerställ att följande katalogstruktur finns:

<ROOT_DIR>/Call Report/:

  - CSV/
    - Cleaned/
    - Interleaved/: **Steg 03**
      - Cleaned/: **Steg 03.1**
