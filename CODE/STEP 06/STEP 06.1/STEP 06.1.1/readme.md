# Step 06.1.1 – Cleaned File Deletion Based on Signature Patterns

## Purpose

This script enforces deletion rules across material event datasets from BankFind Suite API by removing any **cleaned CSV files** whose **filename or content** matches flagged identifiers (e.g., `"BankFind Suite"`).

 ## Reason

 Different material events have different variable naming conventions in the API
 - Mergers have OUT_CERT and ACQ_CERT for the institution being acquired and the acquirer, but not CERT
 - Failures have ACQ_CERT for the institution being absorbed through PA, etc.
 - De Novo have CERT but since none are failing or being acquired, a rule uses ACQ_CERT -> CERT and then deduplicates columns

---

## Key Functionality

- **Auto-locates** `Basel3_Global_Filepath.py` to dynamically determine the `ROOT_DIR`
- **Defines** recursive folder search over:
  - `Material Events/DE NOVO/Cleaned`
  - `Material Events/Failures/Cleaned`
  - `Material Events/Mergers/Cleaned`
- **Deletes files** whose:
  - **Filename** contains *BankFind Suite* (case-insensitive)
  - **Content** contains *BankFind Suite* (case-insensitive)

---

## Pattern Targeted

```text
"BankFind Suite"

## Next Step

Proceed to **Step 06.2**:
- Merge Failure and Merger events to assign terminal event outcomes

