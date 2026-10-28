"""Build explicit 051 and 031 ratio entries through the Call Report API."""

import argparse
from pathlib import Path

import pandas as pd

from callreports import CallReport_031, CallReport_051, QuarterCache, safe_divide

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

FEATURE_COLUMNS = (
    "IDRSSD", "RCON9999", "CERT",
    "RCB-0211-1754", "RCB-1287-1773", "RCB-item4-1754",
    "RCB-HT50-1754", "RCB-HT53-1773", "RCB-8496-1754",
    "RCB-8499-1773", "RCB-G300-item4a", "RCB-G304-Item4a",
    "RCB-G308-Item4a", "RCB-G303-item4a", "RCB-G307-Item4a",
    "RCB-G311-Item4a", "RCB-G312-item4b", "RCB-G316-Item4b",
    "RCB-G320-Item4b", "RCB-G315-item4b", "RCB-G319-Item4b",
    "RCB-G323-Item4b", "RCB-Item4c1-Item4c", "RCB-Item4c2-Item4c",
    "RCB-0213-0211", "RCB-HT51-HT50", "RCB-8497-8496",
    "RCB-item4a-fv2ac", "RCB-item4b-fv2ac", "RCB-item4c-fv2ac",
    "RCB-A549-itemM2a", "RCB-A550-itemM2a", "RCB-A551-itemM2a",
    "RCB-A552-itemM2a", "RCB-A553-itemM2a", "RCB-A554-itemM2a",
    "RCB-A555-itemM2b", "RCB-A556-itemM2b", "RCB-A557-itemM2b",
    "RCB-A558-itemM2b", "RCB-A559-itemM2b", "RCB-A560-itemM2b",
    "RC-Item1-Item12", "RC-Item2-Item12", "RC-Item4-Item12",
    "RC-Item14-Item12", "RC-Item10-Item12", "RC-Item4-Item21",
    "RC-Item5-Item21", "RC-2200-Item21", "RC-3548-Item21",
    "RC-3190-Item21", "RC-2930-Item21", "RC-Item10-G105",
    "RCE-B549-2215", "RCE-2202-2215", "RCE-2203-2215",
    "RCE-B551-2215", "RCE-2213-2215", "RCE-2216-2215",
    "RCE-2215-2200", "RCE-B550-2385", "RCE-2385-2200",
    "RCE-itemM2a-2385", "RCE-6648-2385", "RCE-J473-2385",
    "RCE-J474-2385", "RCE-HK07-savings", "RCE-HK08-savings",
    "RCE-HK09-savings", "RCE-HK10-savings", "RCRI-P840-A223",
    "RCRI-P840-RWA+", "RCRI-P859-A223", "RCRI-P859-RWA+",
    "RCRI-ZRWA-A223", "RCRI-ZRWA-RWA", "RCRI-ZRWA-RWA+",
    "RCRI-ZRWA-RWA++",
)

def create_ratio_entries(row, history=None, date="P0"):
    """Calculate the complete 051 entry and complete 031 entry separately."""
    # The downloaded 2013 files omit these six capital columns. Supply missing
    # observations to the API without changing the input row or form choices.
    if pd.to_numeric(row["RCON9999"], errors="coerce") < 20140331:
        row = dict(row)
        row.setdefault("RCOAA223", float("nan"))
        row.setdefault("RCOAP840", float("nan"))
        row.setdefault("RCOAP859", float("nan"))
        row.setdefault("RCFAA223", float("nan"))
        row.setdefault("RCFAP840", float("nan"))
        row.setdefault("RCFAP859", float("nan"))

    report_051 = CallReport_051(row, history=history)
    report_031 = CallReport_031(row, history=history)

    entry_051 = {
        "IDRSSD": report_051.RSSDID(date=date),
        "RCON9999": report_051.ReportingDate(date=date),
        "CERT": report_051.Certificate(date=date),
        "RCB-0211-1754": safe_divide(report_051.Securities.USTreasuries("htm", "ac", date=date), report_051.Securities.Total("htm", "ac", date=date)),
        "RCB-1287-1773": safe_divide(report_051.Securities.USTreasuries("afs", "fv", date=date), report_051.Securities.Total("afs", "fv", date=date)),
        "RCB-item4-1754": safe_divide(report_051.Securities.MBSTotal("htm", "ac", date=date), report_051.Securities.Total("htm", "ac", date=date)),
        "RCB-HT50-1754": safe_divide(report_051.Securities.USGovtObligations("htm", "ac", date=date), report_051.Securities.Total("htm", "ac", date=date)),
        "RCB-HT53-1773": safe_divide(report_051.Securities.USGovtObligations("afs", "fv", date=date), report_051.Securities.Total("afs", "fv", date=date)),
        "RCB-8496-1754": safe_divide(report_051.Securities.StateSecurities("htm", "ac", date=date), report_051.Securities.Total("htm", "ac", date=date)),
        "RCB-8499-1773": safe_divide(report_051.Securities.StateSecurities("afs", "fv", date=date), report_051.Securities.Total("afs", "fv", date=date)),
        "RCB-G300-item4a": safe_divide(report_051.Securities.GNMAPassThru("htm", "ac", date=date), report_051.Securities.ResidentialPassThru.Total("htm", "ac", date=date)),
        "RCB-G304-Item4a": safe_divide(report_051.Securities.FNMAPassThru("htm", "ac", date=date), report_051.Securities.ResidentialPassThru.Total("htm", "ac", date=date)),
        "RCB-G308-Item4a": safe_divide(report_051.Securities.OtherPassThru("htm", "ac", date=date), report_051.Securities.ResidentialPassThru.Total("htm", "ac", date=date)),
        "RCB-G303-item4a": safe_divide(report_051.Securities.GNMAPassThru("afs", "fv", date=date), report_051.Securities.ResidentialPassThru.Total("afs", "fv", date=date)),
        "RCB-G307-Item4a": safe_divide(report_051.Securities.FNMAPassThru("afs", "fv", date=date), report_051.Securities.ResidentialPassThru.Total("afs", "fv", date=date)),
        "RCB-G311-Item4a": safe_divide(report_051.Securities.OtherPassThru("afs", "fv", date=date), report_051.Securities.ResidentialPassThru.Total("afs", "fv", date=date)),
        "RCB-G312-item4b": safe_divide(report_051.Securities.OtherResidentialGNMA("htm", "ac", date=date), report_051.Securities.OtherResidentialPassThru("htm", "ac", date=date)),
        "RCB-G316-Item4b": safe_divide(report_051.Securities.OtherResidentialFNMA("htm", "ac", date=date), report_051.Securities.OtherResidentialPassThru("htm", "ac", date=date)),
        "RCB-G320-Item4b": safe_divide(report_051.Securities.OtherResidentialOther("htm", "ac", date=date), report_051.Securities.OtherResidentialPassThru("htm", "ac", date=date)),
        "RCB-G315-item4b": safe_divide(report_051.Securities.OtherResidentialGNMA("afs", "fv", date=date), report_051.Securities.OtherResidentialPassThru("afs", "fv", date=date)),
        "RCB-G319-Item4b": safe_divide(report_051.Securities.OtherResidentialFNMA("afs", "fv", date=date), report_051.Securities.OtherResidentialPassThru("afs", "fv", date=date)),
        "RCB-G323-Item4b": safe_divide(report_051.Securities.OtherResidentialOther("afs", "fv", date=date), report_051.Securities.OtherResidentialPassThru("afs", "fv", date=date)),
        "RCB-Item4c1-Item4c": safe_divide(report_051.Securities.CommericalPassThru("htm", "ac", date=date), report_051.Securities.CommericalPassThru("htm", "ac", date=date) + report_051.Securities.OtherCommericalMBS("htm", "ac", date=date)),
        "RCB-Item4c2-Item4c": safe_divide(report_051.Securities.OtherCommericalMBS("htm", "ac", date=date), report_051.Securities.CommericalPassThru("htm", "ac", date=date) + report_051.Securities.OtherCommericalMBS("htm", "ac", date=date)),
        "RCB-0213-0211": safe_divide(report_051.Securities.USTreasuries("htm", "fv", date=date), report_051.Securities.USTreasuries("htm", "ac", date=date)),
        "RCB-HT51-HT50": safe_divide(report_051.Securities.USGovtObligations("htm", "fv", date=date), report_051.Securities.USGovtObligations("htm", "ac", date=date)),
        "RCB-8497-8496": safe_divide(report_051.Securities.StateSecurities("htm", "fv", date=date), report_051.Securities.StateSecurities("htm", "ac", date=date)),
        "RCB-item4a-fv2ac": safe_divide(report_051.Securities.ResidentialPassThru.Total("htm", "fv", date=date), report_051.Securities.ResidentialPassThru.Total("htm", "ac", date=date)),
        "RCB-item4b-fv2ac": safe_divide(report_051.Securities.OtherResidentialPassThru("htm", "fv", date=date), report_051.Securities.OtherResidentialPassThru("htm", "ac", date=date)),
        "RCB-item4c-fv2ac": safe_divide(report_051.Securities.CommericalPassThru("htm", "fv", date=date) + report_051.Securities.OtherCommericalMBS("htm", "fv", date=date), report_051.Securities.CommericalPassThru("htm", "ac", date=date) + report_051.Securities.OtherCommericalMBS("htm", "ac", date=date)),
        "RCB-A549-itemM2a": safe_divide(report_051.Maturities.Government.ThreeMonths(date=date), report_051.Maturities.Government.Total(date=date)),
        "RCB-A550-itemM2a": safe_divide(report_051.Maturities.Government.TwelveMonths(date=date), report_051.Maturities.Government.Total(date=date)),
        "RCB-A551-itemM2a": safe_divide(report_051.Maturities.Government.ThreeYears(date=date), report_051.Maturities.Government.Total(date=date)),
        "RCB-A552-itemM2a": safe_divide(report_051.Maturities.Government.FiveYears(date=date), report_051.Maturities.Government.Total(date=date)),
        "RCB-A553-itemM2a": safe_divide(report_051.Maturities.Government.FifteenYears(date=date), report_051.Maturities.Government.Total(date=date)),
        "RCB-A554-itemM2a": safe_divide(report_051.Maturities.Government.OverFifteenYears(date=date), report_051.Maturities.Government.Total(date=date)),
        "RCB-A555-itemM2b": safe_divide(report_051.Maturities.ResidentialMortgage.ThreeMonths(date=date), report_051.Maturities.ResidentialMortgage.Total(date=date)),
        "RCB-A556-itemM2b": safe_divide(report_051.Maturities.ResidentialMortgage.TwelveMonths(date=date), report_051.Maturities.ResidentialMortgage.Total(date=date)),
        "RCB-A557-itemM2b": safe_divide(report_051.Maturities.ResidentialMortgage.ThreeYears(date=date), report_051.Maturities.ResidentialMortgage.Total(date=date)),
        "RCB-A558-itemM2b": safe_divide(report_051.Maturities.ResidentialMortgage.FiveYears(date=date), report_051.Maturities.ResidentialMortgage.Total(date=date)),
        "RCB-A559-itemM2b": safe_divide(report_051.Maturities.ResidentialMortgage.FifteenYears(date=date), report_051.Maturities.ResidentialMortgage.Total(date=date)),
        "RCB-A560-itemM2b": safe_divide(report_051.Maturities.ResidentialMortgage.OverFifteenYears(date=date), report_051.Maturities.ResidentialMortgage.Total(date=date)),
        "RC-Item1-Item12": safe_divide(report_051.BalanceSheet.CashAndBalancesDue(date=date), report_051.BalanceSheet.TotalAssets(date=date)),
        "RC-Item2-Item12": safe_divide(report_051.BalanceSheet.TotalSecurities(date=date), report_051.BalanceSheet.TotalAssets(date=date)),
        "RC-Item4-Item12": safe_divide(report_051.BalanceSheet.LoansAndLeaseFinancingReceivables.TotalIncludingHeldForSale(date=date), report_051.BalanceSheet.TotalAssets(date=date)),
        "RC-Item14-Item12": safe_divide(report_051.BalanceSheet.FederalFundsPurchased(date=date), report_051.BalanceSheet.TotalAssets(date=date)),
        "RC-Item10-Item12": safe_divide(report_051.BalanceSheet.IntangibleAssets(date=date), report_051.BalanceSheet.TotalAssets(date=date)),
        "RC-Item4-Item21": safe_divide(report_051.BalanceSheet.LoansAndLeaseFinancingReceivables.TotalIncludingHeldForSale(date=date), report_051.BalanceSheet.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-Item5-Item21": safe_divide(report_051.BalanceSheet.TradingAssets(date=date), report_051.BalanceSheet.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-2200-Item21": safe_divide(report_051.DepositLiabilities.ReportedTotal(date=date), report_051.BalanceSheet.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-3548-Item21": safe_divide(report_051.BalanceSheet.TradingLiabilities(date=date), report_051.BalanceSheet.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-3190-Item21": safe_divide(report_051.BalanceSheet.OtherBorrowedMoney(date=date), report_051.BalanceSheet.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-2930-Item21": safe_divide(report_051.BalanceSheet.OtherLiabilities(date=date), report_051.BalanceSheet.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-Item10-G105": safe_divide(report_051.BalanceSheet.IntangibleAssets(date=date), report_051.BalanceSheet.ReportedTotalEquityCapital(date=date)),
        "RCE-B549-2215": safe_divide(report_051.DepositLiabilities.TransactionDeposits.Individuals(date=date), report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date)),
        "RCE-2202-2215": safe_divide(report_051.DepositLiabilities.TransactionDeposits.USGovt(date=date), report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date)),
        "RCE-2203-2215": safe_divide(report_051.DepositLiabilities.TransactionDeposits.StatesAndPolitical(date=date), report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date)),
        "RCE-B551-2215": safe_divide(report_051.DepositLiabilities.TransactionDeposits.CommercialBanks(date=date), report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date)),
        "RCE-2213-2215": safe_divide(report_051.DepositLiabilities.TransactionDeposits.ForeignBanks(date=date), report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date)),
        "RCE-2216-2215": safe_divide(report_051.DepositLiabilities.TransactionDeposits.ForeignGovt(date=date), report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date)),
        "RCE-2215-2200": safe_divide(report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date), report_051.DepositLiabilities.ReportedTotal(date=date)),
        "RCE-B550-2385": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.Individuals(date=date), report_051.DepositLiabilities.NonTransactionDeposits.ReportedTotal(date=date)),
        "RCE-2385-2200": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.ReportedTotal(date=date), report_051.DepositLiabilities.ReportedTotal(date=date)),
        "RCE-itemM2a-2385": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.SavingsTotal(date=date), report_051.DepositLiabilities.NonTransactionDeposits.ReportedTotal(date=date)),
        "RCE-6648-2385": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan100k(date=date), report_051.DepositLiabilities.NonTransactionDeposits.ReportedTotal(date=date)),
        "RCE-J473-2385": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.ReportedTotal(date=date), report_051.DepositLiabilities.NonTransactionDeposits.ReportedTotal(date=date)),
        "RCE-J474-2385": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.MoreThan250k.ReportedTotal(date=date), report_051.DepositLiabilities.NonTransactionDeposits.ReportedTotal(date=date)),
        "RCE-HK07-savings": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.EffectiveThreeMonths(date=date), report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan100k(date=date) + report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.ReportedTotal(date=date)),
        "RCE-HK08-savings": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.EffectiveTwelveMonths(date=date), report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan100k(date=date) + report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.ReportedTotal(date=date)),
        "RCE-HK09-savings": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.EffectiveThreeYears(date=date), report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan100k(date=date) + report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.ReportedTotal(date=date)),
        "RCE-HK10-savings": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.EffectiveOverThreeYears(date=date), report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan100k(date=date) + report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.ReportedTotal(date=date)),
        "RCRI-P840-A223": safe_divide(report_051.RegulatoryCapital.TierOneCapital(date=date), report_051.RegulatoryCapital.RiskWeightedAssets(date=date)),
        "RCRI-P840-RWA+": safe_divide(report_051.RegulatoryCapital.TierOneCapital(date=date), report_051.RegulatoryCapital.AugmentedRiskWeightedAssets(date=date)),
        "RCRI-P859-A223": safe_divide(report_051.RegulatoryCapital.CommonEquityTierOneCapital(date=date), report_051.RegulatoryCapital.RiskWeightedAssets(date=date)),
        "RCRI-P859-RWA+": safe_divide(report_051.RegulatoryCapital.CommonEquityTierOneCapital(date=date), report_051.RegulatoryCapital.AugmentedRiskWeightedAssets(date=date)),
        "RCRI-ZRWA-A223": report_051.RegulatoryCapital.ZeroRiskToReportedRWA(date=date),
        "RCRI-ZRWA-RWA": report_051.RegulatoryCapital.ZeroRiskToAugmentedRWA(date=date),
        "RCRI-ZRWA-RWA+": report_051.RegulatoryCapital.AdjustedZeroRiskToAugmentedRWA(date=date),
        "RCRI-ZRWA-RWA++": report_051.RegulatoryCapital.RelativeZeroRiskAdjustment(date=date),
    }

    # Domestic RC-E deposits are deliberately called through report_051.
    entry_031 = {
        "IDRSSD": report_031.RSSDID(date=date),
        "RCON9999": report_031.ReportingDate(date=date),
        "CERT": report_031.Certificate(date=date),
        "RCB-0211-1754": safe_divide(report_031.Securities.USTreasuries("htm", "ac", date=date), report_031.Securities.Total("htm", "ac", date=date)),
        "RCB-1287-1773": safe_divide(report_031.Securities.USTreasuries("afs", "fv", date=date), report_031.Securities.Total("afs", "fv", date=date)),
        "RCB-item4-1754": safe_divide(report_031.Securities.MBSTotal("htm", "ac", date=date), report_031.Securities.Total("htm", "ac", date=date)),
        "RCB-HT50-1754": safe_divide(report_031.Securities.USGovtObligations("htm", "ac", date=date), report_031.Securities.Total("htm", "ac", date=date)),
        "RCB-HT53-1773": safe_divide(report_031.Securities.USGovtObligations("afs", "fv", date=date), report_031.Securities.Total("afs", "fv", date=date)),
        "RCB-8496-1754": safe_divide(report_031.Securities.StateSecurities("htm", "ac", date=date), report_031.Securities.Total("htm", "ac", date=date)),
        "RCB-8499-1773": safe_divide(report_031.Securities.StateSecurities("afs", "fv", date=date), report_031.Securities.Total("afs", "fv", date=date)),
        "RCB-G300-item4a": safe_divide(report_031.Securities.GNMAPassThru("htm", "ac", date=date), report_031.Securities.ResidentialPassThru.Total("htm", "ac", date=date)),
        "RCB-G304-Item4a": safe_divide(report_031.Securities.FNMAPassThru("htm", "ac", date=date), report_031.Securities.ResidentialPassThru.Total("htm", "ac", date=date)),
        "RCB-G308-Item4a": safe_divide(report_031.Securities.OtherPassThru("htm", "ac", date=date), report_031.Securities.ResidentialPassThru.Total("htm", "ac", date=date)),
        "RCB-G303-item4a": safe_divide(report_031.Securities.GNMAPassThru("afs", "fv", date=date), report_031.Securities.ResidentialPassThru.Total("afs", "fv", date=date)),
        "RCB-G307-Item4a": safe_divide(report_031.Securities.FNMAPassThru("afs", "fv", date=date), report_031.Securities.ResidentialPassThru.Total("afs", "fv", date=date)),
        "RCB-G311-Item4a": safe_divide(report_031.Securities.OtherPassThru("afs", "fv", date=date), report_031.Securities.ResidentialPassThru.Total("afs", "fv", date=date)),
        "RCB-G312-item4b": safe_divide(report_031.Securities.OtherResidentialGNMA("htm", "ac", date=date), report_031.Securities.OtherResidentialPassThru("htm", "ac", date=date)),
        "RCB-G316-Item4b": safe_divide(report_031.Securities.OtherResidentialFNMA("htm", "ac", date=date), report_031.Securities.OtherResidentialPassThru("htm", "ac", date=date)),
        "RCB-G320-Item4b": safe_divide(report_031.Securities.OtherResidentialOther("htm", "ac", date=date), report_031.Securities.OtherResidentialPassThru("htm", "ac", date=date)),
        "RCB-G315-item4b": safe_divide(report_031.Securities.OtherResidentialGNMA("afs", "fv", date=date), report_031.Securities.OtherResidentialPassThru("afs", "fv", date=date)),
        "RCB-G319-Item4b": safe_divide(report_031.Securities.OtherResidentialFNMA("afs", "fv", date=date), report_031.Securities.OtherResidentialPassThru("afs", "fv", date=date)),
        "RCB-G323-Item4b": safe_divide(report_031.Securities.OtherResidentialOther("afs", "fv", date=date), report_031.Securities.OtherResidentialPassThru("afs", "fv", date=date)),
        "RCB-Item4c1-Item4c": safe_divide(report_031.Securities.CommericalPassThru("htm", "ac", date=date), report_031.Securities.CommericalPassThru("htm", "ac", date=date) + report_031.Securities.OtherCommericalMBS("htm", "ac", date=date)),
        "RCB-Item4c2-Item4c": safe_divide(report_031.Securities.OtherCommericalMBS("htm", "ac", date=date), report_031.Securities.CommericalPassThru("htm", "ac", date=date) + report_031.Securities.OtherCommericalMBS("htm", "ac", date=date)),
        "RCB-0213-0211": safe_divide(report_031.Securities.USTreasuries("htm", "fv", date=date), report_031.Securities.USTreasuries("htm", "ac", date=date)),
        "RCB-HT51-HT50": safe_divide(report_031.Securities.USGovtObligations("htm", "fv", date=date), report_031.Securities.USGovtObligations("htm", "ac", date=date)),
        "RCB-8497-8496": safe_divide(report_031.Securities.StateSecurities("htm", "fv", date=date), report_031.Securities.StateSecurities("htm", "ac", date=date)),
        "RCB-item4a-fv2ac": safe_divide(report_031.Securities.ResidentialPassThru.Total("htm", "fv", date=date), report_031.Securities.ResidentialPassThru.Total("htm", "ac", date=date)),
        "RCB-item4b-fv2ac": safe_divide(report_031.Securities.OtherResidentialPassThru("htm", "fv", date=date), report_031.Securities.OtherResidentialPassThru("htm", "ac", date=date)),
        "RCB-item4c-fv2ac": safe_divide(report_031.Securities.CommericalPassThru("htm", "fv", date=date) + report_031.Securities.OtherCommericalMBS("htm", "fv", date=date), report_031.Securities.CommericalPassThru("htm", "ac", date=date) + report_031.Securities.OtherCommericalMBS("htm", "ac", date=date)),
        "RCB-A549-itemM2a": safe_divide(report_031.Maturities.Government.ThreeMonths(date=date), report_031.Maturities.Government.Total(date=date)),
        "RCB-A550-itemM2a": safe_divide(report_031.Maturities.Government.TwelveMonths(date=date), report_031.Maturities.Government.Total(date=date)),
        "RCB-A551-itemM2a": safe_divide(report_031.Maturities.Government.ThreeYears(date=date), report_031.Maturities.Government.Total(date=date)),
        "RCB-A552-itemM2a": safe_divide(report_031.Maturities.Government.FiveYears(date=date), report_031.Maturities.Government.Total(date=date)),
        "RCB-A553-itemM2a": safe_divide(report_031.Maturities.Government.FifteenYears(date=date), report_031.Maturities.Government.Total(date=date)),
        "RCB-A554-itemM2a": safe_divide(report_031.Maturities.Government.OverFifteenYears(date=date), report_031.Maturities.Government.Total(date=date)),
        "RCB-A555-itemM2b": safe_divide(report_031.Maturities.ResidentialMortgage.ThreeMonths(date=date), report_031.Maturities.ResidentialMortgage.Total(date=date)),
        "RCB-A556-itemM2b": safe_divide(report_031.Maturities.ResidentialMortgage.TwelveMonths(date=date), report_031.Maturities.ResidentialMortgage.Total(date=date)),
        "RCB-A557-itemM2b": safe_divide(report_031.Maturities.ResidentialMortgage.ThreeYears(date=date), report_031.Maturities.ResidentialMortgage.Total(date=date)),
        "RCB-A558-itemM2b": safe_divide(report_031.Maturities.ResidentialMortgage.FiveYears(date=date), report_031.Maturities.ResidentialMortgage.Total(date=date)),
        "RCB-A559-itemM2b": safe_divide(report_031.Maturities.ResidentialMortgage.FifteenYears(date=date), report_031.Maturities.ResidentialMortgage.Total(date=date)),
        "RCB-A560-itemM2b": safe_divide(report_031.Maturities.ResidentialMortgage.OverFifteenYears(date=date), report_031.Maturities.ResidentialMortgage.Total(date=date)),
        "RC-Item1-Item12": safe_divide(report_031.BalanceSheet.CashAndBalancesDue(date=date), report_031.BalanceSheet.TotalAssets(date=date)),
        "RC-Item2-Item12": safe_divide(report_031.BalanceSheet.TotalSecurities(date=date), report_031.BalanceSheet.TotalAssets(date=date)),
        "RC-Item4-Item12": safe_divide(report_031.BalanceSheet.LoansAndLeaseFinancingReceivables.TotalIncludingHeldForSale(date=date), report_031.BalanceSheet.TotalAssets(date=date)),
        "RC-Item14-Item12": safe_divide(report_031.BalanceSheet.FederalFundsPurchased(date=date), report_031.BalanceSheet.TotalAssets(date=date)),
        "RC-Item10-Item12": safe_divide(report_031.BalanceSheet.IntangibleAssets(date=date), report_031.BalanceSheet.TotalAssets(date=date)),
        "RC-Item4-Item21": safe_divide(report_031.BalanceSheet.LoansAndLeaseFinancingReceivables.TotalIncludingHeldForSale(date=date), report_031.BalanceSheet.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-Item5-Item21": safe_divide(report_031.BalanceSheet.TradingAssets(date=date), report_031.BalanceSheet.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-2200-Item21": safe_divide(report_051.DepositLiabilities.ReportedTotal(date=date), report_031.BalanceSheet.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-3548-Item21": safe_divide(report_031.BalanceSheet.TradingLiabilities(date=date), report_031.BalanceSheet.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-3190-Item21": safe_divide(report_031.BalanceSheet.OtherBorrowedMoney(date=date), report_031.BalanceSheet.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-2930-Item21": safe_divide(report_031.BalanceSheet.OtherLiabilities(date=date), report_031.BalanceSheet.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-Item10-G105": safe_divide(report_031.BalanceSheet.IntangibleAssets(date=date), report_031.BalanceSheet.ReportedTotalEquityCapital(date=date)),
        "RCE-B549-2215": safe_divide(report_051.DepositLiabilities.TransactionDeposits.Individuals(date=date), report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date)),
        "RCE-2202-2215": safe_divide(report_051.DepositLiabilities.TransactionDeposits.USGovt(date=date), report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date)),
        "RCE-2203-2215": safe_divide(report_051.DepositLiabilities.TransactionDeposits.StatesAndPolitical(date=date), report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date)),
        "RCE-B551-2215": safe_divide(report_051.DepositLiabilities.TransactionDeposits.CommercialBanks(date=date), report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date)),
        "RCE-2213-2215": safe_divide(report_051.DepositLiabilities.TransactionDeposits.ForeignBanks(date=date), report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date)),
        "RCE-2216-2215": safe_divide(report_051.DepositLiabilities.TransactionDeposits.ForeignGovt(date=date), report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date)),
        "RCE-2215-2200": safe_divide(report_051.DepositLiabilities.TransactionDeposits.ReportedTotal(date=date), report_051.DepositLiabilities.ReportedTotal(date=date)),
        "RCE-B550-2385": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.Individuals(date=date), report_051.DepositLiabilities.NonTransactionDeposits.ReportedTotal(date=date)),
        "RCE-2385-2200": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.ReportedTotal(date=date), report_051.DepositLiabilities.ReportedTotal(date=date)),
        "RCE-itemM2a-2385": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.SavingsTotal(date=date), report_051.DepositLiabilities.NonTransactionDeposits.ReportedTotal(date=date)),
        "RCE-6648-2385": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan100k(date=date), report_051.DepositLiabilities.NonTransactionDeposits.ReportedTotal(date=date)),
        "RCE-J473-2385": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.ReportedTotal(date=date), report_051.DepositLiabilities.NonTransactionDeposits.ReportedTotal(date=date)),
        "RCE-J474-2385": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.MoreThan250k.ReportedTotal(date=date), report_051.DepositLiabilities.NonTransactionDeposits.ReportedTotal(date=date)),
        "RCE-HK07-savings": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.EffectiveThreeMonths(date=date), report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan100k(date=date) + report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.ReportedTotal(date=date)),
        "RCE-HK08-savings": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.EffectiveTwelveMonths(date=date), report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan100k(date=date) + report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.ReportedTotal(date=date)),
        "RCE-HK09-savings": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.EffectiveThreeYears(date=date), report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan100k(date=date) + report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.ReportedTotal(date=date)),
        "RCE-HK10-savings": safe_divide(report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.EffectiveOverThreeYears(date=date), report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan100k(date=date) + report_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k.ReportedTotal(date=date)),
        "RCRI-P840-A223": safe_divide(report_031.RegulatoryCapital.TierOneCapital(date=date), report_031.RegulatoryCapital.RiskWeightedAssets(date=date)),
        "RCRI-P840-RWA+": safe_divide(report_031.RegulatoryCapital.TierOneCapital(date=date), report_031.RegulatoryCapital.AugmentedRiskWeightedAssets(date=date)),
        "RCRI-P859-A223": safe_divide(report_031.RegulatoryCapital.CommonEquityTierOneCapital(date=date), report_031.RegulatoryCapital.RiskWeightedAssets(date=date)),
        "RCRI-P859-RWA+": safe_divide(report_031.RegulatoryCapital.CommonEquityTierOneCapital(date=date), report_031.RegulatoryCapital.AugmentedRiskWeightedAssets(date=date)),
        "RCRI-ZRWA-A223": report_031.RegulatoryCapital.ZeroRiskToReportedRWA(date=date),
        "RCRI-ZRWA-RWA": report_031.RegulatoryCapital.ZeroRiskToAugmentedRWA(date=date),
        "RCRI-ZRWA-RWA+": report_031.RegulatoryCapital.AdjustedZeroRiskToAugmentedRWA(date=date),
        "RCRI-ZRWA-RWA++": report_031.RegulatoryCapital.RelativeZeroRiskAdjustment(date=date),
    }

    if tuple(entry_051) != FEATURE_COLUMNS:
        raise AssertionError("051 Call Report output schema changed")
    if tuple(entry_031) != FEATURE_COLUMNS:
        raise AssertionError("031 Call Report output schema changed")
    return entry_051, entry_031

def is_missing(value):
    return bool(pd.isna(value))

def process_dataframe(frame, history=None, date="P0"):
    columns = tuple(frame.columns)
    records = []
    for values in frame.itertuples(index=False, name=None):
        row = dict(zip(columns, values))
        entry_051, entry_031 = create_ratio_entries(
            row,
            history=history,
            date=date,
        )
        records.extend((entry_051, entry_031))

    result = pd.DataFrame.from_records(records, columns=FEATURE_COLUMNS)
    if result.empty:
        return result

    ratio_columns = FEATURE_COLUMNS[3:]
    result["_available_values"] = result.loc[:, ratio_columns].notna().sum(axis=1)
    result = result.loc[result["_available_values"] > 0].copy()
    if result.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    result["_missing_values"] = result.isna().sum(axis=1)
    result = result.sort_values(["IDRSSD", "_missing_values"], kind="mergesort")
    return result.drop_duplicates("IDRSSD", keep="first").drop(
        columns=["_available_values", "_missing_values"]
    )

def process_file(input_path, output_path, history=None, date="P0"):
    input_path = Path(input_path)
    output_path = Path(output_path)
    frame = pd.read_csv(input_path, low_memory=False)
    result = process_dataframe(frame, history=history, date=date)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    result.to_csv(temporary_path, index=False)
    temporary_path.replace(output_path)
    return output_path

def build_interleaved_reports(
    input_dir,
    output_dir,
    history=None,
    date="P0",
    map_file=None,
):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    if history is None:
        history = QuarterCache(map_file=map_file, data_dir=input_dir)

    written = []
    for input_path in sorted(input_dir.glob("*.csv")):
        output_path = process_file(
            input_path,
            output_dir / input_path.name,
            history=history,
            date=date,
        )
        written.append(output_path)
        print("Wrote {}".format(output_path))
    return written

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path,
                        default=PROJECT_ROOT / "data" / "CSV" / "Cleaned")
    parser.add_argument("--output-dir", type=Path,
                        default=PROJECT_ROOT / "data" / "CSV" / "Interleaved")
    parser.add_argument("--quarter-map", type=Path,
                        default=PROJECT_ROOT / "data" / "CSV" / "quarter_flag.csv")
    parser.add_argument("--date", choices=("P0", "P1Q", "P2Q", "P3Q", "P1Y"),
                        default="P0")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    written = build_interleaved_reports(
        args.input_dir, args.output_dir,
        date=args.date, map_file=args.quarter_map,
    )
    print("Processed {} Call Report files".format(len(written)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
