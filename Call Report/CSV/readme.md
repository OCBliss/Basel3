This is the master folder for converted csv files from the txt files in https://github.com/OCBliss/Basel3/tree/main/Call%20Report/TXT.

Schedules folder contains the original call report schedules as formatted by the FFIEC's Central Data Repository, excepting the removal of the first row with the MDRM code descriptions, leaving the MDRM codes as headers. 
It also appends the FDIC Certificate Number to all schedules using the IDRSSD as key because the Material Events data from https://github.com/OCBliss/Basel3/tree/main/Material%20Events which is downloaded from BankFind Suite at https://banks.data.fdic.gov/bankfind-suite/oscr

Cleaned folder contain a merged version of the original call report schedules from the FFIEC's Central Data Repository. It uses Schedule ENT as the key.

Interleaved folder contains the csvs with vertical analysis performed upon Cleaned folder.
