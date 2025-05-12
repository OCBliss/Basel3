# Basel III – Automatisk JSD-analys av Call Reports

**Author:** Jonathan Waller  
**GitHub:** github.com/OCBLISS  
**Contact:** johnny.waller.nb@gmail.com  
**Affiliation:** Independent Researcher

Detta projekt automatiserar bearbetningen av Call Report-data och väsentliga händelser till regulatoriska mått, med särskilt fokus på Jensen-Shannon-divergens (JSD). Analyserna omfattar Basel III, tiden efter finanskrisen (Post-GFC) samt andra historiska perioder, och utförs över flera Call Report-scheman.

Projektet är avsett för forskningsbruk inom investeringsbanker och centralbanker. Det körs via ett Python-skript: [`Task_manager_Global_yaml_driven5a.py`](https://github.com/OCBliss/Basel3/blob/main/CODE/), som drivs av en dynamisk YAML-konfigurationsfil (`pipeline_config_dynamic4a.yaml`).

## Installation och Struktur

- Klona detta repo med förinläst data, **eller** se till att `Basel_Global_Filepath.py` placeras i en rotkatalog som är **explicit** namngiven `Basel3/`.
- Rotmappen kan placeras var som helst; alla undermappar identifieras dynamiskt.
- Pipen stöder:
  - Samtidig förgrening för parallella analyser  
  - Beroendehantering  
  - Hashning av indata för att hoppa över steg som inte ändrats  

---

⚠️ **ANMÄRKNING TILL GRANSKARE**:  
Detta repo stödjer den empiriska komponenten i **Sveriges Riksbanks** konferensbidrag 2025:  
***“Basel III Under Strain: Interest Rate Exposure, Misclassification Arbitrage, and the Illusion of Compliance”***.

All kod och alla utdata-strukturer som nämns i metodavsnittet av artikeln finns här.  
Pipen är under aktiv utveckling – nya versionsmappar kommer löpande för att simulera framtida regulatoriska scenarier.  
**Uppladdningar pågår fortfarande.**

---

**[Avslutat]**
- Mappstrukturen för STEP 08 färdigställd 2025-05-05  
- STEP 08 ska köras framgångsrikt upp till 8.0.4  
- `Task_manager_Global_yaml_driven2a.py` ändrad → `Task_manager_Global_yaml_driven5a.py`  
- `pipeline_config.yaml` uppdaterad → `pipeline_config_dynamic4a.yaml`  
- STEP 03.0 vertikal och retrospektiv analys  
  - Typkonverteringsfel lösta för CET1 och CCYB  
- STEP 03.1 rensar den vertikala analysen  
  - tar bort kolumnen `RCRI-CET1-THRES` (RCFAH311)  

**[Pågående]**
- STEP 08 framtidsscenario (ETA ej fastställt)  
  - Slutför `readme`-filer och ladda upp skript med `argparse`-injektion och separat manuell körning  
  - Slutför 8.1.x till 8.5.x  
- TXT-undermappar fylls iterativt och ska flyttas till Zenodo  

---
### 📄 Licensing

This project is dual-licensed:

- 🆓 **Apache License 2.0** — for non-commercial, academic, and personal use.
- 💼 **Commercial use requires a separate license.**  
  See [`Commercial_License.txt`](./Commercial_License.txt) for full terms.

To obtain a commercial license, contact:  
📧 [johnny.waller.nb@gmail.com](mailto:johnny.waller.nb@gmail.com)

### Syfte
- Rensa och konvertera rå Call Report-data.  
- Utför vertikal analys på hela datamängden och dela därefter upp efter schema (RC, RC-B, etc.).  
- Filtrera peer-grupper efter tidsperioder (Basel III, Post-GFC, GFC).  
- Beräkna JSD med varierande tidshorisonter (T+1, T+2, T+3, T+4) och binsstorlekar (20, 30, 50, 100).  
- Generera regulatoriska mått för granskning av BIS.

### Katalogstruktur
- `CODE/`: Rotkatalog som innehåller alla skript.
  - `pipeline.py`: Huvudpipelinens skript – kör hela arbetsflödet.
  - `pipeline_config.yaml`: Konfigurationsfil som definierar steg, beroenden och exekveringsflöde.
  - `STEP 01/`: Rensningsskript (t.ex. `call_reports_mkdir_txt_csvs_global.py`).
  - `STEP 02/`: Konverteringsskript (t.ex. `Call_Report_Merged_Cleaned_Global.py`, `numeric_only6.py`).
  - `STEP 03/`: Skript för vertikal analys (t.ex. `Call_Reports_retrospective_Vertical3c.py`).
  - `STEP 04/`: Skript för fördelning av nyckeltal (t.ex. `Call_Reports_Distributed_Ratios2.py`).
  - `STEP 05/`: Dynamiska nyckeltalsskript (t.ex. `Call_Reports_Dynamic_Ratios2.py`).
  - `STEP 06/`: Bearbetning av materiella händelser (t.ex. `Material_events_cleaned2.py`, `Material_events_de_novo_flag4.py`).
  - `STEP 07/`: Filtrering av peer-grupper (t.ex. `Material_events_peer_group_basel3_t1.py`).
  - `STEP 08/`: JSD-beräkning (t.ex. `RC_JSD_Basel_T1_Bin20.py`).
  - `Logs_V3/`: Automatgenererad loggmapp för stegresultat och status.

### Katalogstruktur – Basel3
- `Basel3/Call Reports/`
  - `CSV/`
    - `Cleaned/`: Rensade CSV-filer från Call Report-bearbetning.
    - `Interleaved/`: Sammanflätade CSV-data från flera scheman.
    - `Schedules/`: CSV-data uppdelat efter Call Report-scheman (t.ex. RC, RC-B).
    - `Distributed Lag/`
      - `Cleaned/`: Rensade resultat för distributed lag-kvoter.
      - `RAW/`: Rådata för distributed lag-kvoter.
    - `Dynamic Lag/`
      - `Cleaned/`: Rensade resultat för dynamiska lag-kvoter.
      - `RAW/`: Rådata för dynamiska lag-kvoter.
  - `PDF/`: Ursprungliga Call Report-PDF:er.
  - `TXT/`: Textfiler extraherade från Call Report-PDF:er.
    - `FFIEC CDR Call Bulk All Schedules 20240630/`
    - `FFIEC CDR Call Bulk All Schedules 20240330/`
    - etc.
- `Basel3/Material Events/`
  - `De Novo/`
    - `Cleaned/`: Rensade De Novo-händelser strukturerade för märkning.
    - `RAW/`: Rådata för De Novo-händelser.
    - `Call Reports`: Call Reports märkta med De Novo-flaggor.
  - `Failures/`
    - `Cleaned/`: Rensade data för bankfallissemang.
    - `RAW/`: Rådata för bankfallissemang.
    - `Call Reports`: Call Reports märkta med De Novo + fallissemang-flaggor.
  - `Mergers/`
    - `Cleaned/`: Rensade data för sammanslagningar.
    - `RAW/`: Rådata för sammanslagningar.
    - `Call Reports`: Call Reports märkta med De Novo + fallissemang + sammanslagningsflaggor.
  - `JSD/`
    - `Basel III/`
      - `Mergers T+1/`: JSD-resultat för banksammanslagningar under Basel III, med prognoshorisont T+1.
      - `Mergers T+2/`: JSD-resultat för banksammanslagningar under Basel III, med prognoshorisont T+2.
      - `Mergers T+3/`: JSD-resultat för banksammanslagningar under Basel III, med prognoshorisont T+3.
      - `Mergers T+4/`: JSD-resultat för banksammanslagningar under Basel III, med prognoshorisont T+4
      - `Failures T+1/`: JSD-resultat för Basel III-bankfallissemang, med prognoshorisont T+1.
      - `Failures T+2/`: JSD-resultat för Basel III-bankfallissemamg, med prognoshorisont T+2.
      - `Failures T+3/`: JSD-resultat för Basel III-bankfallissemang, med prognoshorisont T+3.
      - `Failures T+4/`: JSD-resultat för Basel III-bankfallissemamg, med prognoshorisont T+4.
    - `Post-GFC/`
      - `Mergers T+1/`: JSD-resultat för banksammanslagningar efter finanskrisen, med prognoshorisont T+1.
      - `Mergers T+2/`: JSD-resultat för banksammanslagningar efter finanskrisen, med prognoshorisont T+2.
      - `Mergers T+3/`: JSD-resultat för banksammanslagningar efter finanskrisen, med prognoshorisont T+3.
      - `Mergers T+4/`: JSD-resultat för banksammanslagningar efter finanskrisen, med prognoshorisont T+4.
      - `Failures T+1/`: JSD-resultat för bankfallissemang efter finanskrisen, med prognoshorisont T+1.
      - `Failures T+2/`: JSD-resultat för bankfallissemang efter finanskrisen, med prognoshorisont T+2.
      - `Failures T+3/`: JSD-resultat för bankfallissemang efter finanskrisen, med prognoshorisont T+3.
      - `Failures T+4/`: JSD-resultat för bankfallissemang efter finanskrisen, med prognoshorisont T+4.

### Framtida arbete: RWA och modellering av förväntad förlust
Basel3/RWA/
  - Constant Maturity Treasury/
    - FRED/: FRED-data för statsobligationer med konstant löptid.
      - FRED MLE YIELD/: Avkastningsdata enligt maximum likelihood-estimat.
      - FRED MLE VOL/: Volatilitetsdata enligt maximum likelihood-estimat.
      - FRED MLE CORR/: Korrelationsdata enligt maximum likelihood-estimat.
      - FRED HESTON/: Utdata från Heston-modellen för FRED-data.
  - Expected Coupon/: Beräkning av förväntad kupongränta för RWA.
  - Expected Loss/: Uppskattning av förväntad förlust för RWA.
  - Novel Risk Weights/: Nya beräkningar av riskvikter.


---

### Krav
- Python 3.6: Med standardbibliotek (`os`, `sys`, `subprocess`, `hashlib`, `time`, `yaml`, `concurrent.futures`)
  - `pyyaml`
  - `pandas`
  - `numpy`

 Skriv eller kopiera och klistra in följande i terminalfönstret:
```python
[ -f 
```

Dra sedan filen requirements.txt till terminalfönstret (detta fyller automatiskt i sökvägen). Se till att det finns ett mellanslag efter -f, före [ och efter -r.

```
 ] && pip install -r
```

Dra requirements.txt till terminalen igen. Tryck på return.

### Kompatibilitet med operativsystem
- Denna pipeline utvecklades på macOS, och vissa skript kan vara ofullständigt optimerade för Windows. Skillnader i sökvägshantering (t.ex. mellanslag, backslash kontra snedstreck) eller filsystemets beteende kan kräva justeringar för Windows-användare.

### Så fungerar det
1. `Basel3_Global_Filepath.py`:
   - Identifierar rotkatalogen `Basel3/` dynamiskt baserat på sin egen plats, och;
   - Hittar katalogerna `CODE/`, `Call Reports/`, `Material Events/` och bygger dynamiskt upp underkatalogstrukturer.

2. `Task_manager_Global_yaml_driven5a.py`:  
   - Läser in `pipeline_config_dynamic4a.yaml` och validerar att sektionerna (`scripts`, `dependencies`, `execution`) finns.  
   - Kör steg baserat på `execution`-sektionen:
     - `sequential`: Kör stegen i ordningsföljd, ett i taget.
     - `concurrent_branches`: Startar grenar parallellt med trådar, hanterar rekursivt nästlade grenar eller grupper.
     - `concurrent_groups`: Kör flera steglistor parallellt inom en gren.
   - Kontrollerar `dependencies` för att säkerställa rätt körordning (t.ex. 3.0 måste vara klar innan 3.1 kan starta).
   - Loggar resultat i `Logs_V3/` för varje steg i kedjan.

3. `pipeline_config_dynamic4a.yaml`:  
   - `scripts`: Kartlägger stegid:n (t.ex. "1.0") till Python-skript med sökvägar relativa till `CODE/`.  
   - `dependencies`: Definierar förkrav för varje steg (t.ex. `"3.0": ["3.1", "3.2"]` innebär att 3.0 måste köras före 3.1 och 3.2).  
   - `execution`: Anger arbetsflödet med sekventiella och parallella sektioner, och styr därmed ordning och samtidighet.

### Aktuellt Arbetsflöde
Nedan visas hela `pipeline_config.yaml` i dess nuvarande form – alla steg, beroenden och exekveringsdetaljer är inkluderade.

### Exekveringsflöde
1. Sekventiellt (1.0–3.0):  
   - "1.0": Rensar rå Call Report-data till användbart format (t.ex. skapar kataloger, konverterar textfiler till CSV).  
   - "2.0": Slår samman och rensar data ytterligare till en enhetlig datamängd.  
   - "2.1": Konverterar data till ett rent numeriskt format för analys.  
   - "3.0": Utför vertikal analys på hela Call Report-datasetet och förbereder för uppdelning per schema.

2. Uppdelning per tidsperiod:  
   - Kör stegen 4.0.1–6.4.1 sekventiellt:  
     - "4.0": Beräknar fördelade nyckeltal för RC, RC-B etc.  
     - "4.1": Rensar de fördelade nyckeltalen.  
     - "5.0": Beräknar dynamiska nyckeltal.  
     - "5.1": Rensar de dynamiska nyckeltalen.  
     - "6.1": Rensar data om materiella händelser.  
     - "6.2": Flaggar De Novo-händelser.  
     - "6.3": Flaggar bankfallissemang.  
     - "6.4": Flaggar banksammanslagningar.

3. Filtrering av Peer-grupper:  
   - `peers`: Kör 7.0.0.1–7.0.0.4 parallellt – filtrerar peer-grupper enligt Basel III över proghorisonterna T+1 till T+4.  
   - `filters`: Kör 7.1.0.1–7.1.0.4 parallellt – tillämpar ytterligare filter på Basel III-peer-grupper.

4. JSD-analys:  
   - "8.0.1": Utför binning på Basel III-data (standard: 50 bins – konfigurerbart i skriptet).  
   - "8.1.1": Beräknar JSD-sannolikheter för Basel III.  
   - `t1`: Delas upp i tre samtidiga JSD-körningar med binsstorlekar 20, 30, 50 (8.2.0.1.1–8.2.0.1.3).  
   - `t2`: Kör enskilt JSD-steg "8.2.0.2" för T+2-proghorisonten.  
   - `t3`: Kör enskilt JSD-steg "8.2.0.3" för T+3-proghorisonten.  
   - `t4`: Kör enskilt JSD-steg "8.2.0.4" för T+4-proghorisonten.

### Kommentarer om Platshållare
- `t1`, `t2`, `t3`, `t4` samt binning (20, 30, 50, 100).

### Köra Pipen
1. Installation:
   - Placera alla skript i respektive `STEP XX/`-undermapp under `CODE/`.
   - Kontrollera att `pipeline_config.yaml` ligger i `CODE/`.

2. Kommando:
   - Kör från kommandoraden: `python CODE/pipeline.py`

3. Utdata:
   - Loggar genereras i `CODE/Logs_V3/` (t.ex. `1.0_log.txt`, `8.2.0.1.1_log.txt`).
   - Varje logg innehåller tidsstämplar, start/slut för steget och indatahashar (SHA-256) om hashning är aktiverad.

### Dynamiska Funktioner
- Samtidighet: Använder Pythons `ThreadPoolExecutor` – skalar automatiskt beroende till antal grenar eller grupper (t.ex. 4 scheman, 2 perioder, 3 bins i t1).  
- Flexibilitet: Lägg till nya scheman, tidsperioder eller binsstorlekar genom att redigera `pipeline_config.yaml` – inga ändringar krävs i `pipeline.py`.

### Tips för Användning
- Utöka en gren: Lägg till ett nytt schema (t.ex. `rc_f_schedule`) under `concurrent_branches` med egna steg, beroenden och exekveringsflöde.  
- Felsökning: Kontrollera `Logs_V3/` – varje steg loggar `STARTED`, `COMPLETED` eller `ERROR` med tidsstämpel och detaljer.  
- Hoppa över steg: Om ett stegs indata inte har ändrats (via hash) hoppar pipen över det och loggar `✅ Step X input unchanged`.
