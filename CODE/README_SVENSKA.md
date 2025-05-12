# Basel III-pipeline för centralbanksartikel

Detta projekt automatiserar bearbetningen av Call Reports och materiella händelser till regulatoriska mått enligt Basel III-standarderna, så som de definieras av Bank for International Settlements (BIS). Det är utformat för bankforskning och kör arbetsflöden dynamiskt baserat på en konfigurerbar `pipeline_config.yaml`.

**Syfte:** YAML-baserad task manager för att köra JSD-analys på Call Reports samt riskvägdsanalys (RWA) på CMT (konstruerad statsobligationsränta med konstant löptid från USA:s finansdepartement)-data från FRED (Federal Reserve Economic Data – USA:s officiella databas för makro- och finansdata).

## Översikt

Pipen bearbetar finansiell data genom en serie modulära Python-skript och stöder:
- Sekventiell och parallell körning av steg  
- Beroendehantering mellan uppgifter  
- Hashning av indata för att hoppa över oförändrade steg  
- Dynamisk detektering av in- och utdata  
- Detaljerad loggning för felsökning och revision

Arbetsflödet definieras i `pipeline_config.yaml`, vilket möjliggör flexibilitet för valfritt antal grenar eller bearbetningssteg.

### Katalogstruktur
- `CODE/`: Rotkatalog som innehåller alla skript.
  - `pipeline.py`: Huvudskriptet för pipen – kör arbetsflödet.
  - `pipeline_config.yaml`: Konfigurationsfil som definierar steg, beroenden och exekveringsflöde.
  - `STEP 01/`: `call_reports_mkdir_txt_csvs_global.py`
  - `STEP 02/`:
    - `STEP 02.0/`: `Call_Report_Merged_Cleaned_Global.py`
    - `STEP 02.1/`: `numeric_only6.py`
  - `STEP 03/`: `Call_Reports_retrospective_Vertical3c.py`
  - `STEP 04/`:
    - `STEP 04.0/`: `Call_Reports_Distributed_Ratios2.py`
    - `STEP 04.1/`: `Clean_Distributed_Ratios2.py`
  - `STEP 05/`: Skript för dynamiska nyckeltal (t.ex. `Call_Reports_Dynamic_Ratios2.py`)
  - `STEP 06/`: Bearbetning av materiella händelser (t.ex. `Material_events_cleaned2.py`, `Material_events_de_novo_flag4.py`)
  - `STEP 07/`: Filtrering av peer-grupper (t.ex. `Material_events_peer_group_basel3_t1.py`)
  - `STEP 08/`: JSD-beräkningar (t.ex. `RC_JSD_Basel_T1_Bin20.py`)
  - `Logs_V3/`: Automatgenererad loggmapp för stegutdata och status

## Funktioner

- **Modulär design:** Lägg till eller ändra steg genom att uppdatera YAML-konfigurationen.
- **Samtidighet (Concurrency):** Kör oberoende uppgifter parallellt med `ThreadPoolExecutor`.
  - **`concurrency_branches`**
    - `basel_iii` – kör all analys för Basel III-perioden enligt artikelns specifikation.
    - `post_gfc` – kör all analys för perioden efter finanskrisen enligt artikelns specifikation.
    - `t1` – T+1 skapar en gren för varje `concurrency_branches` med ett T+1-förskjutet analysfönster.
    - `t2` – T+2 skapar en gren för varje `concurrency_branches` med ett T+2-förskjutet analysfönster.
    - `t3` – T+3 skapar en gren för varje `concurrency_branches` med ett T+3-förskjutet analysfönster.
    - `t4` – T+4 skapar en gren för varje `concurrency_branches` med ett T+4-förskjutet analysfönster.
  - **`concurrency_group`** – en specifik samtidighet som endast uppstår inom en `concurrency_branches`-instans:
    - `jsd` – t.ex. JSD-analys tillämpas endast en gång per `concurrent_branches`-instans.
      - `bins20` – binning skapar sannolikhetsmassfunktioner för Jensen-Shannon-divergens mellan peer-grupper (t.ex. 20–50 bins).
      - `bins30`
      - `bins50`
    - `peers`: `mergers`, `failures`, `survivors` och `de novo` flaggor tillämpas för JSD-analys.
    - `filters` – därefter filtrerar vi baserat på `peers` och binning.
  - **`intermediate_steps`** – används för att införa nödvändiga sekventiella steg (t.ex. binning, PMF-skapande) mellan samtidiga grupper.
  - **`sequential`** – vissa steg kräver att föregående steg är klara och kan därför inte köras parallellt.

- **Effektivitet:** Hoppar över steg där indata är oförändrade via SHA-256-hashning.
- **Loggning:** Skapar detaljerade loggar i `Logs_V3/` för varje steg.
  - ** Detta möjliggör att hela analysen kan återstartas mitt i ett körflöde om fel uppstår – och förhindrar onödig CPU-användning (se `run_task`).
- **Felfångst:** Faller ut på ett kontrollerat sätt med exit-koder och loggar för felsökning.

## Framtida Anpassning – Exempel

- **Scheman** kan delas upp och köras à la carte för att minska beräkningstiden, genom att specificera varje schema som en `concurrency_branches`.

`pipeline_config.yaml`
```yaml
# pipeline_config.yaml

# Se till att ``dependencies`` matchar ``execution``

execution:
  sequential: ["1.0", "2.0", "2.1"]
  concurrent_branches: # uppdelning per schema
    rc_schedule:
      sequential: ["3.0.1", "4.0.1", "4.1.1", "5.0.1", "5.1.1"] # RC-analys
      concurrent_branches: # uppdelning per finansiell/regulatorisk epok (GFC, post-GFC, Basel III)
        basel_iii: # Basel III-epok
          sequential: ["6.1.1", "6.2.1", "6.3.1", "6.4.1"] # flaggning av materiella händelser
          concurrent_groups: # används eftersom peer-grupper kan flaggas parallellt
            peers: ["7.0.0.1", "7.0.0.2", "7.0.0.3", "7.0.0.4"] # peer-gruppsskapande
            filters: ["7.1.0.1", "7.1.0.2", "7.1.0.3", "7.1.0.4"] # filtrering enligt peer-grupp
          intermediate_steps: ["8.0.1.1", "8.1.1.1"] # sekventiella steg mellan ``concurrency_groups`` – binning och PMF-skapande
          concurrent_branches:
            t1: # mapp `BASEL T+1` – kör JSD-analys för peer-gruppsflaggning med T+1 (ett kvartal) framförhållning
              concurrent_groups: # samtidiga PMF-/binning-körningar för olika binsstorlekar
                jsd: # faktisk JSD-jämförelse under Basel III
                  bins20: ["8.2.1.1.1"]
                  bins30: ["8.2.1.1.2"]
                  bins50: ["8.2.1.1.3"]
            t2:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.1.2.1"]
                  bins30: ["8.2.1.2.2"]
                  bins50: ["8.2.1.2.3"]
            t3:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.1.3.1"]
                  bins30: ["8.2.1.3.2"]
                  bins50: ["8.2.1.3.3"]
            t4:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.1.4.1"]
                  bins30: ["8.2.1.4.2"]
                  bins50: ["8.2.1.4.3"]
        post_gfc: # du kan kommentera ut epoker, t1–t4 eller hela scheman för snabbare och effektivare körning
          sequential: ["6.1.2", "6.2.2", "6.3.2", "6.4.2"]
          concurrent_groups:
            peers: ["7.0.1.1", "7.0.1.2", "7.0.1.3", "7.0.1.4"]
            filters: ["7.1.1.1", "7.1.1.2", "7.1.1.3", "7.1.1.4"]
          intermediate_steps: ["8.0.2.1", "8.1.2.1"]
          concurrent_branches:
            t1:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.2.1.1"]
                  bins30: ["8.2.2.1.2"]
                  bins50: ["8.2.2.1.3"]
            t2:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.2.2.1"]
                  bins30: ["8.2.2.2.2"]
                  bins50: ["8.2.2.2.3"]
            t3:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.2.3.1"]
                  bins30: ["8.2.2.3.2"]
                  bins50: ["8.2.2.3.3"]
            t4:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.2.4.1"]
                  bins30: ["8.2.2.4.2"]
                  bins50: ["8.2.2.4.3"]
    rcb_schedule:
      sequential: ["3.0.2"] # RC-B-analys
```

## Förutsättningar

- Python 3.6+
- Obligatoriska Python-paket:
  - `pyyaml` (för tolkning av YAML-filer)
  - `pandas`
  - `numpy`
  - `importlib.utils`
  - `re`
- Katalogstruktur:
  - Projektet måste ligga i en `CODE/`-katalog (identifieras automatiskt).
  - `pipeline_config.yaml` måste finnas i rotmappen `CODE/`.

Installera beroenden:
```bash
pip install pyyaml
