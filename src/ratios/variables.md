# Ratio variables

This catalogue lists the 76 ratio columns produced by
[Call_Reports_v4_0.py](../call%20reports/Call_Reports_v4_0.py). The names match
`FEATURE_COLUMNS`; the calculations below follow the two explicit entries
in `create_ratio_entries()` and the separate API methods in
[Call_Report.py](../call%20reports/Call_Report.py).

The caller evaluates the `CallReport_031` and `CallReport_051` implementations
and keeps the row with fewer missing values for each `IDRSSD`. Their field
prefixes and date rules can differ. The method names below retain those
distinctions. Each method receives the selected `date`; that repeated argument
is omitted in the tables.

Division in the tables means `safe_divide`: a missing input produces a missing
result, and a non-missing numerator divided by zero produces zero. The capital
methods apply their own documented date branches described below.

The tables use short names for readability. The executable caller writes
out the full form-specific path every time; it does not use these aliases.

| Table name | 051 entry | 031 entry |
| --- | --- | --- |
| `balance` | `report_051.BalanceSheet` | `report_031.BalanceSheet` |
| `loans` | `report_051.BalanceSheet.LoansAndLeaseFinancingReceivables` | `report_031.BalanceSheet.LoansAndLeaseFinancingReceivables` |
| `securities` | `report_051.Securities` | `report_031.Securities` |
| `government_maturities` | `report_051.Maturities.Government` | `report_031.Maturities.Government` |
| `residential_maturities` | `report_051.Maturities.ResidentialMortgage` | `report_031.Maturities.ResidentialMortgage` |
| `domestic_deposits` | `report_051.DepositLiabilities` | `report_051.DepositLiabilities` |
| `transaction` | `report_051.DepositLiabilities.TransactionDeposits` | `report_051.DepositLiabilities.TransactionDeposits` |
| `nontransaction` | `report_051.DepositLiabilities.NonTransactionDeposits` | `report_051.DepositLiabilities.NonTransactionDeposits` |
| `time_deposits` | `report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits` | `report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits` |
| `less_than_250k` | `report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k` | `report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k` |
| `capital` | `report_051.RegulatoryCapital` | `report_031.RegulatoryCapital` |

The 031 entry's 17 `RCE-*` expressions use the 051 domestic-deposit API.
`RC-2200-Item21` also uses 051 deposits in its numerator and 031 liabilities
in its denominator. These form choices are explicit in the caller.

For securities, `htm` and `afs` select held-to-maturity and available-for-sale;
`ac` and `fv` select amortized cost and fair value.

## Schedule RC-B — Group-Specific Ratio

| Variable | Calculation |
|---------|-------------|
| `RCB-0211-1754` | `securities.USTreasuries("htm", "ac") / securities.Total("htm", "ac")` |
| `RCB-1287-1773` | `securities.USTreasuries("afs", "fv") / securities.Total("afs", "fv")` |
| `RCB-item4-1754` | `securities.MBSTotal("htm", "ac") / securities.Total("htm", "ac")` |
| `RCB-HT50-1754` | `securities.USGovtObligations("htm", "ac") / securities.Total("htm", "ac")` |
| `RCB-HT53-1773` | `securities.USGovtObligations("afs", "fv") / securities.Total("afs", "fv")` |
| `RCB-8496-1754` | `securities.StateSecurities("htm", "ac") / securities.Total("htm", "ac")` |
| `RCB-8499-1773` | `securities.StateSecurities("afs", "fv") / securities.Total("afs", "fv")` |

## RC-B — Mortgage-Backed Securities

### Residential Pass-Through (Item 4a)

| Variable | Calculation |
|---------|-------------|
| `RCB-G300-item4a` | `securities.GNMAPassThru("htm", "ac") / securities.ResidentialPassThru.Total("htm", "ac")` |
| `RCB-G304-Item4a` | `securities.FNMAPassThru("htm", "ac") / securities.ResidentialPassThru.Total("htm", "ac")` |
| `RCB-G308-Item4a` | `securities.OtherPassThru("htm", "ac") / securities.ResidentialPassThru.Total("htm", "ac")` |
| `RCB-G303-item4a` | `securities.GNMAPassThru("afs", "fv") / securities.ResidentialPassThru.Total("afs", "fv")` |
| `RCB-G307-Item4a` | `securities.FNMAPassThru("afs", "fv") / securities.ResidentialPassThru.Total("afs", "fv")` |
| `RCB-G311-Item4a` | `securities.OtherPassThru("afs", "fv") / securities.ResidentialPassThru.Total("afs", "fv")` |

### Other Residential MBS (Item 4b)

| Variable | Calculation |
|---------|-------------|
| `RCB-G312-item4b` | `securities.OtherResidentialGNMA("htm", "ac") / securities.OtherResidentialPassThru("htm", "ac")` |
| `RCB-G316-Item4b` | `securities.OtherResidentialFNMA("htm", "ac") / securities.OtherResidentialPassThru("htm", "ac")` |
| `RCB-G320-Item4b` | `securities.OtherResidentialOther("htm", "ac") / securities.OtherResidentialPassThru("htm", "ac")` |
| `RCB-G315-item4b` | `securities.OtherResidentialGNMA("afs", "fv") / securities.OtherResidentialPassThru("afs", "fv")` |
| `RCB-G319-Item4b` | `securities.OtherResidentialFNMA("afs", "fv") / securities.OtherResidentialPassThru("afs", "fv")` |
| `RCB-G323-Item4b` | `securities.OtherResidentialOther("afs", "fv") / securities.OtherResidentialPassThru("afs", "fv")` |

### Commercial MBS (Item 4c)

| Variable | Calculation |
|---------|-------------|
| `RCB-Item4c1-Item4c` | `securities.CommericalPassThru("htm", "ac") / (securities.CommericalPassThru("htm", "ac") + securities.OtherCommericalMBS("htm", "ac"))` |
| `RCB-Item4c2-Item4c` | `securities.OtherCommericalMBS("htm", "ac") / (securities.CommericalPassThru("htm", "ac") + securities.OtherCommericalMBS("htm", "ac"))` |

## RC-B — Valuation-Specific Ratios

| Variable | Calculation |
|---------|-------------|
| `RCB-0213-0211` | `securities.USTreasuries("htm", "fv") / securities.USTreasuries("htm", "ac")` |
| `RCB-HT51-HT50` | `securities.USGovtObligations("htm", "fv") / securities.USGovtObligations("htm", "ac")` |
| `RCB-8497-8496` | `securities.StateSecurities("htm", "fv") / securities.StateSecurities("htm", "ac")` |
| `RCB-item4a-fv2ac` | `securities.ResidentialPassThru.Total("htm", "fv") / securities.ResidentialPassThru.Total("htm", "ac")` |
| `RCB-item4b-fv2ac` | `securities.OtherResidentialPassThru("htm", "fv") / securities.OtherResidentialPassThru("htm", "ac")` |
| `RCB-item4c-fv2ac` | `(securities.CommericalPassThru("htm", "fv") + securities.OtherCommericalMBS("htm", "fv")) / (securities.CommericalPassThru("htm", "ac") + securities.OtherCommericalMBS("htm", "ac"))` |

## RC-B — Memoranda (Securities) — Maturity Analysis

### Item M.2.a (Treasury/Gov/States Maturity Buckets)

| Variable | Calculation |
|---------|-------------|
| `RCB-A549-itemM2a` | `government_maturities.ThreeMonths() / government_maturities.Total()` |
| `RCB-A550-itemM2a` | `government_maturities.TwelveMonths() / government_maturities.Total()` |
| `RCB-A551-itemM2a` | `government_maturities.ThreeYears() / government_maturities.Total()` |
| `RCB-A552-itemM2a` | `government_maturities.FiveYears() / government_maturities.Total()` |
| `RCB-A553-itemM2a` | `government_maturities.FifteenYears() / government_maturities.Total()` |
| `RCB-A554-itemM2a` | `government_maturities.OverFifteenYears() / government_maturities.Total()` |

### RC-B — Item M.2.b (Closed-End 1-4 RMBS Maturity Buckets)

| Variable | Calculation |
|---------|-------------|
| `RCB-A555-itemM2b` | `residential_maturities.ThreeMonths() / residential_maturities.Total()` |
| `RCB-A556-itemM2b` | `residential_maturities.TwelveMonths() / residential_maturities.Total()` |
| `RCB-A557-itemM2b` | `residential_maturities.ThreeYears() / residential_maturities.Total()` |
| `RCB-A558-itemM2b` | `residential_maturities.FiveYears() / residential_maturities.Total()` |
| `RCB-A559-itemM2b` | `residential_maturities.FifteenYears() / residential_maturities.Total()` |
| `RCB-A560-itemM2b` | `residential_maturities.OverFifteenYears() / residential_maturities.Total()` |

## Schedule RC — Domain-Specific Ratios

| Variable | Calculation |
|---------|-------------|
| `RC-Item1-Item12` | `balance.CashAndBalancesDue() / balance.TotalAssets()` |
| `RC-Item2-Item12` | `balance.TotalSecurities() / balance.TotalAssets()` |
| `RC-Item4-Item12` | `loans.TotalIncludingHeldForSale() / balance.TotalAssets()` |
| `RC-Item14-Item12` | `balance.FederalFundsPurchased() / balance.TotalAssets()` |
| `RC-Item10-Item12` | `balance.IntangibleAssets() / balance.TotalAssets()` |

## Total Liabilities

| Variable | Calculation |
|---------|-------------|
| `RC-Item4-Item21` | `loans.TotalIncludingHeldForSale() / balance.TotalLiabilitiesIncludingAllowance()` |
| `RC-Item5-Item21` | `balance.TradingAssets() / balance.TotalLiabilitiesIncludingAllowance()` |
| `RC-2200-Item21` | `domestic_deposits.ReportedTotal() / balance.TotalLiabilitiesIncludingAllowance()` |
| `RC-3548-Item21` | `balance.TradingLiabilities() / balance.TotalLiabilitiesIncludingAllowance()` |
| `RC-3190-Item21` | `balance.OtherBorrowedMoney() / balance.TotalLiabilitiesIncludingAllowance()` |
| `RC-2930-Item21` | `balance.OtherLiabilities() / balance.TotalLiabilitiesIncludingAllowance()` |

## Total Equity

| Variable | Calculation |
|---------|-------------|
| `RC-Item10-G105` | `balance.IntangibleAssets() / balance.ReportedTotalEquityCapital()` |

## Schedule RC-E — Deposit Ratios

### Transaction Accounts

| Variable | Calculation |
|---------|-------------|
| `RCE-B549-2215` | `transaction.Individuals() / transaction.ReportedTotal()` |
| `RCE-2202-2215` | `transaction.USGovt() / transaction.ReportedTotal()` |
| `RCE-2203-2215` | `transaction.StatesAndPolitical() / transaction.ReportedTotal()` |
| `RCE-B551-2215` | `transaction.CommercialBanks() / transaction.ReportedTotal()` |
| `RCE-2213-2215` | `transaction.ForeignBanks() / transaction.ReportedTotal()` |
| `RCE-2216-2215` | `transaction.ForeignGovt() / transaction.ReportedTotal()` |
| `RCE-2215-2200` | `transaction.ReportedTotal() / domestic_deposits.ReportedTotal()` |

### Non-Transaction Accounts

| Variable | Calculation |
|---------|-------------|
| `RCE-B550-2385` | `nontransaction.Individuals() / nontransaction.ReportedTotal()` |
| `RCE-2385-2200` | `nontransaction.ReportedTotal() / domestic_deposits.ReportedTotal()` |
| `RCE-itemM2a-2385` | `nontransaction.SavingsTotal() / nontransaction.ReportedTotal()` |
| `RCE-6648-2385` | `time_deposits.LessThan100k() / nontransaction.ReportedTotal()` |
| `RCE-J473-2385` | `less_than_250k.ReportedTotal() / nontransaction.ReportedTotal()` |
| `RCE-J474-2385` | `time_deposits.MoreThan250k.ReportedTotal() / nontransaction.ReportedTotal()` |

### Time Deposits < $250k (2017Q1 rule switch included)

| Variable | Calculation |
|---------|-------------|
| `RCE-HK07-savings` | `less_than_250k.EffectiveThreeMonths() / (time_deposits.LessThan100k() + less_than_250k.ReportedTotal())` |
| `RCE-HK08-savings` | `less_than_250k.EffectiveTwelveMonths() / (time_deposits.LessThan100k() + less_than_250k.ReportedTotal())` |
| `RCE-HK09-savings` | `less_than_250k.EffectiveThreeYears() / (time_deposits.LessThan100k() + less_than_250k.ReportedTotal())` |
| `RCE-HK10-savings` | `less_than_250k.EffectiveOverThreeYears() / (time_deposits.LessThan100k() + less_than_250k.ReportedTotal())` |

The four `Effective...` time-deposit methods use `HK07`–`HK10` from
2017-03-31 onward and `A579`–`A582` before that date. Their denominator remains
`LessThan100k() + LessThan250k.ReportedTotal()` as shown above.

## Schedule RC-R Part I — Risk-Weighted Assets

| Variable | Calculation |
|---------|-------------|
| `RCRI-P840-A223` | `capital.TierOneCapital() / capital.RiskWeightedAssets()` |
| `RCRI-P840-RWA+` | `capital.TierOneCapital() / capital.AugmentedRiskWeightedAssets()` |
| `RCRI-P859-A223` | `capital.CommonEquityTierOneCapital() / capital.RiskWeightedAssets()` |
| `RCRI-P859-RWA+` | `capital.CommonEquityTierOneCapital() / capital.AugmentedRiskWeightedAssets()` |
| `RCRI-ZRWA-A223` | `capital.ZeroRiskToReportedRWA()` |
| `RCRI-ZRWA-RWA` | `capital.ZeroRiskToAugmentedRWA()` |
| `RCRI-ZRWA-RWA+` | `capital.AdjustedZeroRiskToAugmentedRWA()` |
| `RCRI-ZRWA-RWA++` | `capital.RelativeZeroRiskAdjustment()` |

For the zero-risk ratios:

- `ZeroRiskToReportedRWA()` divides `ZeroRiskWeightedAssets()` by reported
  `RiskWeightedAssets()`.
- `ZeroRiskToAugmentedRWA()` uses reported RWA before 2015-03-31 and
  `AugmentedRiskWeightedAssets()` from that date onward.
- `AdjustedZeroRiskToAugmentedRWA()` uses that same denominator. Before
  2015-03-31 its numerator is the unadjusted zero-risk amount; from that date
  onward it subtracts `ZeroRiskWeightExposureRatio() * RiskWeightAdjustment()`.
- `RelativeZeroRiskAdjustment()` returns zero when
  `ZeroRiskToAugmentedRWA()` is zero; otherwise it returns
  `1 - safe_divide(AdjustedZeroRiskToAugmentedRWA(), ZeroRiskToAugmentedRWA())`.

`Dynamic_Ratios.py` retains each current ratio as `<variable>_q0` and adds its
changes from `P1Q`, `P2Q` and `P3Q`. See the [dynamic-ratio description](readme.md)
for those suffixes, inputs and output paths.
