# Model and Call Report PDFs

[Recursive IRR Model.pdf](Recursive%20IRR%20Model.pdf) contains the repository's interest-rate model document. The related RWA work is in [src/RWA](../src/RWA/) and remains separate from the configured Call Report and material-event pipeline.

`Call Reports/` contains eight saved FFIEC reports: one for SVB and one for M&T Bank in each quarter of 2022. They provide the original report layouts for manual reference and comparison with the schedule data.

| Quarter | SVB | M&T Bank |
| --- | --- | --- |
| 2022Q1 | [March 31](Call%20Reports/2022Q1/SVB_Call_Cert_20220331.PDF) | [March 31](Call%20Reports/2022Q1/M%26T%20Bank_Call_Cert588_20220331.PDF) |
| 2022Q2 | [June 30](Call%20Reports/2022Q2/SVB_Call_Cert_20220630.PDF) | [June 30](Call%20Reports/2022Q2/M%26T%20Bank_Call_Cert588_20220630.PDF) |
| 2022Q3 | [September 30](Call%20Reports/2022Q3/SVB_Call_Cert_20220930.PDF) | [September 30](Call%20Reports/2022Q3/M%26T%20Bank_Call_Cert588_20220930.PDF) |
| 2022Q4 | [December 31](Call%20Reports/2022Q4/SVB_Call_Cert_20221231.PDF) | [December 31](Call%20Reports/2022Q4/M%26T%20Bank_Call_Cert588_20221231.PDF) |

The pipeline reads the tab-delimited Call Report files downloaded into [data/TXT](../data/TXT/). It does not extract data from these PDFs. Download and processing instructions are in the [data guide](../data/readme.md).
