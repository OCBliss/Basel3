This is the master folder for converted csv files from the txt files in https://github.com/OCBliss/Basel3/tree/main/Call%20Report/TXT.
Raw folder contains the original call report schedules as formatted by the FFIEC's Central Data Repository, excepting the removal of the first row with the MDRM code descriptions, leaving the MDRM codes as headers.
Cleaned folder contain a merged version of the original call report schedules from the FFIEC's Central Data Repository. It uses Schedule ENT as the key.
Interleaved folder contains the csvs with vertical analysis performed upon Cleaned folder.
