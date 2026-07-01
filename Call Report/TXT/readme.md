# TXT Subfolder

## Description
Start here!
This folder should contain the original unzipped `Call Report - Single Period` folders in txt format formatted by the FFIEC's Central Data Repository (CDR). The schedules have not yet been processed to remove unnecessary rows and append essential identifiers for compatibility with other datasets.

## Source
- Raw TXT data files from the FFIEC CDR located here:  
  (https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx)

## **TXT/**
   - **Description:** Raw data files downloaded from the FFIEC CDR (Central Data Repository).
   - **Contents:**  
     - Subfolders for each financial quarter, named by the quarter’s end date (e.g., `FFIEC CDR Call Bulk All Schedules YYYYMMDD/`).
     - Files in native text format as provided by FFIEC.
   - **Usage:**  
     - Input for data preprocessing and conversion into CSV format (found in the CSV folder).
     - Provides an unaltered source for reproducibility.
