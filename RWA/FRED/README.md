## 📘 Methodological Appendix: Description of Treasury Nominal and Inflation-Indexed Constant Maturity Series

📄 README på Svenska → [README_SVENSKA.md](https://github.com/OCBliss/Basel3/blob/main/RWA/FRED/README_SVENSKA.md)

Yields on nominal U.S. Treasury securities with **constant maturity** (**CMT**) are interpolated by the U.S. Treasury from the daily yield curve of non-inflation-indexed Treasury securities. This curve, which relates a bond’s yield to its remaining time to maturity, is based on closing bid yields for actively traded securities in the over-the-counter (OTC) market. These market yields are derived from compilations of price quotations obtained by the **Federal Reserve Bank of New York**.

Constructed constant maturity yields are read from the curve at fixed maturities—currently:  
**1, 3, and 6 months**, and **1, 2, 3, 5, 7, 10, 20, and 30 years**.  
This method enables the calculation of, for example, a 10-year benchmark rate even if no outstanding security exactly matches that maturity.

Similarly, yields on inflation-indexed securities at **constant maturity** are interpolated from the daily yield curve for **Treasury Inflation-Protected Securities (TIPS)** in the OTC market. These yields are also read at fixed maturities:  
**5, 7, 10, 20, and 30 years**.

> 📎 **Source:**  
> Board of Governors of the Federal Reserve System  
> [*H.15 Selected Interest Rates – Description of the Treasury Nominal and Inflation-Indexed Constant Maturity Series*](https://www.federalreserve.gov/releases/h15/)  
> Accessed: May 12, 2025
