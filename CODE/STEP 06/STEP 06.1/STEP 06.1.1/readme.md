# Step 06.1.1 – Cleaned File Deletion Based on Signature Patterns

## Purpose

This script enforces deletion rules across material event datasets from BankFind Suite API by removing any **cleaned CSV files** whose **filename or content** matches flagged identifiers (e.g., `"BankFind Suite"`).

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

