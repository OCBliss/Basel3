"""Create vertical Call Report ratios from the imported domain functions."""

import argparse
import math
from pathlib import Path
import sys

import pandas as pd


CALL_REPORT_DIR = Path(__file__).resolve().parent
SRC_DIR = CALL_REPORT_DIR.parent
for import_path in (CALL_REPORT_DIR, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import Basel3_Global_Filepath as paths  # noqa: E402
from Call_Report import CallReport_031, CallReport_051, safe_divide  # noqa: E402


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


def is_missing(value):
    if value is None:
        return True
    try:
        return math.isnan(value)
    except (TypeError, ValueError):
        return False


def create_ratio_entries(row):
    """Create the 051 and 031 entries by calling imported report functions."""

    report_051 = CallReport_051(row)
    balance_051 = report_051.BalanceSheet
    loans_051 = balance_051.LoansAndLeaseFinancingReceivables
    securities_051 = report_051.Securities
    government_051 = report_051.Maturities.Government
    residential_051 = report_051.Maturities.ResidentialMortgage
    deposits = report_051.DepositLiabilities
    transaction = deposits.TransactionDeposits
    nontransaction = deposits.NonTransactionDeposits
    time_deposits = nontransaction.TimeDeposits
    less_than_250k = time_deposits.LessThan250k
    capital_051 = report_051.RegulatoryCapital

    entry1 = {
        "IDRSSD": report_051.RSSDID(),
        "RCON9999": report_051.ReportingDate(),
        "CERT": report_051.Certificate(),
        "RCB-0211-1754": safe_divide(securities_051.USTreasuries("htm", "ac"), securities_051.Total("htm", "ac")),
        "RCB-1287-1773": safe_divide(securities_051.USTreasuries("afs", "fv"), securities_051.Total("afs", "fv")),
        "RCB-item4-1754": safe_divide(securities_051.MBSTotal("htm", "ac"), securities_051.Total("htm", "ac")),
        "RCB-HT50-1754": safe_divide(securities_051.USGovtObligations("htm", "ac"), securities_051.Total("htm", "ac")),
        "RCB-HT53-1773": safe_divide(securities_051.USGovtObligations("afs", "fv"), securities_051.Total("afs", "fv")),
        "RCB-8496-1754": safe_divide(securities_051.StateSecurities("htm", "ac"), securities_051.Total("htm", "ac")),
        "RCB-8499-1773": safe_divide(securities_051.StateSecurities("afs", "fv"), securities_051.Total("afs", "fv")),
        "RCB-G300-item4a": safe_divide(securities_051.GNMAPassThru("htm", "ac"), securities_051.ResidentialPassThru.Total("htm", "ac")),
        "RCB-G304-Item4a": safe_divide(securities_051.FNMAPassThru("htm", "ac"), securities_051.ResidentialPassThru.Total("htm", "ac")),
        "RCB-G308-Item4a": safe_divide(securities_051.OtherPassThru("htm", "ac"), securities_051.ResidentialPassThru.Total("htm", "ac")),
        "RCB-G303-item4a": safe_divide(securities_051.GNMAPassThru("afs", "fv"), securities_051.ResidentialPassThru.Total("afs", "fv")),
        "RCB-G307-Item4a": safe_divide(securities_051.FNMAPassThru("afs", "fv"), securities_051.ResidentialPassThru.Total("afs", "fv")),
        "RCB-G311-Item4a": safe_divide(securities_051.OtherPassThru("afs", "fv"), securities_051.ResidentialPassThru.Total("afs", "fv")),
        "RCB-G312-item4b": safe_divide(securities_051.OtherResidentialGNMA("htm", "ac"), securities_051.OtherResidentialPassThru("htm", "ac")),
        "RCB-G316-Item4b": safe_divide(securities_051.OtherResidentialFNMA("htm", "ac"), securities_051.OtherResidentialPassThru("htm", "ac")),
        "RCB-G320-Item4b": safe_divide(securities_051.OtherResidentialOther("htm", "ac"), securities_051.OtherResidentialPassThru("htm", "ac")),
        "RCB-G315-item4b": safe_divide(securities_051.OtherResidentialGNMA("afs", "fv"), securities_051.OtherResidentialPassThru("afs", "fv")),
        "RCB-G319-Item4b": safe_divide(securities_051.OtherResidentialFNMA("afs", "fv"), securities_051.OtherResidentialPassThru("afs", "fv")),
        "RCB-G323-Item4b": safe_divide(securities_051.OtherResidentialOther("afs", "fv"), securities_051.OtherResidentialPassThru("afs", "fv")),
        "RCB-Item4c1-Item4c": safe_divide(securities_051.CommericalPassThru("htm", "ac"), securities_051.CommericalPassThru("htm", "ac") + securities_051.OtherCommericalMBS("htm", "ac")),
        "RCB-Item4c2-Item4c": safe_divide(securities_051.OtherCommericalMBS("htm", "ac"), securities_051.CommericalPassThru("htm", "ac") + securities_051.OtherCommericalMBS("htm", "ac")),
        "RCB-0213-0211": safe_divide(securities_051.USTreasuries("htm", "fv"), securities_051.USTreasuries("htm", "ac")),
        "RCB-HT51-HT50": safe_divide(securities_051.USGovtObligations("htm", "fv"), securities_051.USGovtObligations("htm", "ac")),
        "RCB-8497-8496": safe_divide(securities_051.StateSecurities("htm", "fv"), securities_051.StateSecurities("htm", "ac")),
        "RCB-item4a-fv2ac": safe_divide(securities_051.ResidentialPassThru.Total("htm", "fv"), securities_051.ResidentialPassThru.Total("htm", "ac")),
        "RCB-item4b-fv2ac": safe_divide(securities_051.OtherResidentialPassThru("htm", "fv"), securities_051.OtherResidentialPassThru("htm", "ac")),
        "RCB-item4c-fv2ac": safe_divide(securities_051.CommericalPassThru("htm", "fv") + securities_051.OtherCommericalMBS("htm", "fv"), securities_051.CommericalPassThru("htm", "ac") + securities_051.OtherCommericalMBS("htm", "ac")),
        "RCB-A549-itemM2a": safe_divide(government_051.ThreeMonths(), government_051.Total()),
        "RCB-A550-itemM2a": safe_divide(government_051.TwelveMonths(), government_051.Total()),
        "RCB-A551-itemM2a": safe_divide(government_051.ThreeYears(), government_051.Total()),
        "RCB-A552-itemM2a": safe_divide(government_051.FiveYears(), government_051.Total()),
        "RCB-A553-itemM2a": safe_divide(government_051.FifteenYears(), government_051.Total()),
        "RCB-A554-itemM2a": safe_divide(government_051.OverFifteenYears(), government_051.Total()),
        "RCB-A555-itemM2b": safe_divide(residential_051.ThreeMonths(), residential_051.Total()),
        "RCB-A556-itemM2b": safe_divide(residential_051.TwelveMonths(), residential_051.Total()),
        "RCB-A557-itemM2b": safe_divide(residential_051.ThreeYears(), residential_051.Total()),
        "RCB-A558-itemM2b": safe_divide(residential_051.FiveYears(), residential_051.Total()),
        "RCB-A559-itemM2b": safe_divide(residential_051.FifteenYears(), residential_051.Total()),
        "RCB-A560-itemM2b": safe_divide(residential_051.OverFifteenYears(), residential_051.Total()),
        "RC-Item1-Item12": safe_divide(balance_051.CashAndBalancesDue(), balance_051.TotalAssets()),
        "RC-Item2-Item12": safe_divide(balance_051.TotalSecurities(), balance_051.TotalAssets()),
        "RC-Item4-Item12": safe_divide(loans_051.TotalIncludingHeldForSale(), balance_051.TotalAssets()),
        "RC-Item14-Item12": safe_divide(balance_051.FederalFundsPurchased(), balance_051.TotalAssets()),
        "RC-Item10-Item12": safe_divide(balance_051.IntangibleAssets(), balance_051.TotalAssets()),
        "RC-Item4-Item21": safe_divide(loans_051.TotalIncludingHeldForSale(), balance_051.TotalLiabilitiesIncludingAllowance()),
        "RC-Item5-Item21": safe_divide(balance_051.TradingAssets(), balance_051.TotalLiabilitiesIncludingAllowance()),
        "RC-2200-Item21": safe_divide(deposits.ReportedTotal(), balance_051.TotalLiabilitiesIncludingAllowance()),
        "RC-3548-Item21": safe_divide(balance_051.TradingLiabilities(), balance_051.TotalLiabilitiesIncludingAllowance()),
        "RC-3190-Item21": safe_divide(balance_051.OtherBorrowedMoney(), balance_051.TotalLiabilitiesIncludingAllowance()),
        "RC-2930-Item21": safe_divide(balance_051.OtherLiabilities(), balance_051.TotalLiabilitiesIncludingAllowance()),
        "RC-Item10-G105": safe_divide(balance_051.IntangibleAssets(), balance_051.ReportedTotalEquityCapital()),
        "RCE-B549-2215": safe_divide(transaction.Individuals(), transaction.ReportedTotal()),
        "RCE-2202-2215": safe_divide(transaction.USGovt(), transaction.ReportedTotal()),
        "RCE-2203-2215": safe_divide(transaction.StatesAndPolitical(), transaction.ReportedTotal()),
        "RCE-B551-2215": safe_divide(transaction.CommercialBanks(), transaction.ReportedTotal()),
        "RCE-2213-2215": safe_divide(transaction.ForeignBanks(), transaction.ReportedTotal()),
        "RCE-2216-2215": safe_divide(transaction.ForeignGovt(), transaction.ReportedTotal()),
        "RCE-2215-2200": safe_divide(transaction.ReportedTotal(), deposits.ReportedTotal()),
        "RCE-B550-2385": safe_divide(nontransaction.Individuals(), nontransaction.ReportedTotal()),
        "RCE-2385-2200": safe_divide(nontransaction.ReportedTotal(), deposits.ReportedTotal()),
        "RCE-itemM2a-2385": safe_divide(nontransaction.SavingsTotal(), nontransaction.ReportedTotal()),
        "RCE-6648-2385": safe_divide(time_deposits.LessThan100k(), nontransaction.ReportedTotal()),
        "RCE-J473-2385": safe_divide(less_than_250k.ReportedTotal(), nontransaction.ReportedTotal()),
        "RCE-J474-2385": safe_divide(time_deposits.MoreThan250k.ReportedTotal(), nontransaction.ReportedTotal()),
        "RCE-HK07-savings": safe_divide(less_than_250k.EffectiveThreeMonths(), time_deposits.LessThan100k() + less_than_250k.ReportedTotal()),
        "RCE-HK08-savings": safe_divide(less_than_250k.EffectiveTwelveMonths(), time_deposits.LessThan100k() + less_than_250k.ReportedTotal()),
        "RCE-HK09-savings": safe_divide(less_than_250k.EffectiveThreeYears(), time_deposits.LessThan100k() + less_than_250k.ReportedTotal()),
        "RCE-HK10-savings": safe_divide(less_than_250k.EffectiveOverThreeYears(), time_deposits.LessThan100k() + less_than_250k.ReportedTotal()),
        "RCRI-P840-A223": safe_divide(capital_051.TierOneCapital(), capital_051.RiskWeightedAssets()),
        "RCRI-P840-RWA+": safe_divide(capital_051.TierOneCapital(), capital_051.AugmentedRiskWeightedAssets()),
        "RCRI-P859-A223": safe_divide(capital_051.CommonEquityTierOneCapital(), capital_051.RiskWeightedAssets()),
        "RCRI-P859-RWA+": safe_divide(capital_051.CommonEquityTierOneCapital(), capital_051.AugmentedRiskWeightedAssets()),
        "RCRI-ZRWA-A223": capital_051.ZeroRiskToReportedRWA(),
        "RCRI-ZRWA-RWA": capital_051.ZeroRiskToAugmentedRWA(),
        "RCRI-ZRWA-RWA+": capital_051.AdjustedZeroRiskToAugmentedRWA(),
        "RCRI-ZRWA-RWA++": capital_051.RelativeZeroRiskAdjustment(),
    }

    report_031 = CallReport_031(row)
    balance_031 = report_031.BalanceSheet
    loans_031 = balance_031.LoansAndLeaseFinancingReceivables
    securities_031 = report_031.Securities
    government_031 = report_031.Maturities.Government
    residential_031 = report_031.Maturities.ResidentialMortgage
    capital_031 = report_031.RegulatoryCapital

    entry2 = {
        "IDRSSD": report_031.RSSDID(),
        "RCON9999": report_031.ReportingDate(),
        "CERT": report_031.Certificate(),
        "RCB-0211-1754": safe_divide(securities_031.USTreasuries("htm", "ac"), securities_031.Total("htm", "ac")),
        "RCB-1287-1773": safe_divide(securities_031.USTreasuries("afs", "fv"), securities_031.Total("afs", "fv")),
        "RCB-item4-1754": safe_divide(securities_031.MBSTotal("htm", "ac"), securities_031.Total("htm", "ac")),
        "RCB-HT50-1754": safe_divide(securities_031.USGovtObligations("htm", "ac"), securities_031.Total("htm", "ac")),
        "RCB-HT53-1773": safe_divide(securities_031.USGovtObligations("afs", "fv"), securities_031.Total("afs", "fv")),
        "RCB-8496-1754": safe_divide(securities_031.StateSecurities("htm", "ac"), securities_031.Total("htm", "ac")),
        "RCB-8499-1773": safe_divide(securities_031.StateSecurities("afs", "fv"), securities_031.Total("afs", "fv")),
        "RCB-G300-item4a": safe_divide(securities_031.GNMAPassThru("htm", "ac"), securities_031.ResidentialPassThru.Total("htm", "ac")),
        "RCB-G304-Item4a": safe_divide(securities_031.FNMAPassThru("htm", "ac"), securities_031.ResidentialPassThru.Total("htm", "ac")),
        "RCB-G308-Item4a": safe_divide(securities_031.OtherPassThru("htm", "ac"), securities_031.ResidentialPassThru.Total("htm", "ac")),
        "RCB-G303-item4a": safe_divide(securities_031.GNMAPassThru("afs", "fv"), securities_031.ResidentialPassThru.Total("afs", "fv")),
        "RCB-G307-Item4a": safe_divide(securities_031.FNMAPassThru("afs", "fv"), securities_031.ResidentialPassThru.Total("afs", "fv")),
        "RCB-G311-Item4a": safe_divide(securities_031.OtherPassThru("afs", "fv"), securities_031.ResidentialPassThru.Total("afs", "fv")),
        "RCB-G312-item4b": safe_divide(securities_031.OtherResidentialGNMA("htm", "ac"), securities_031.OtherResidentialPassThru("htm", "ac")),
        "RCB-G316-Item4b": safe_divide(securities_031.OtherResidentialFNMA("htm", "ac"), securities_031.OtherResidentialPassThru("htm", "ac")),
        "RCB-G320-Item4b": safe_divide(securities_031.OtherResidentialOther("htm", "ac"), securities_031.OtherResidentialPassThru("htm", "ac")),
        "RCB-G315-item4b": safe_divide(securities_031.OtherResidentialGNMA("afs", "fv"), securities_031.OtherResidentialPassThru("afs", "fv")),
        "RCB-G319-Item4b": safe_divide(securities_031.OtherResidentialFNMA("afs", "fv"), securities_031.OtherResidentialPassThru("afs", "fv")),
        "RCB-G323-Item4b": safe_divide(securities_031.OtherResidentialOther("afs", "fv"), securities_031.OtherResidentialPassThru("afs", "fv")),
        "RCB-Item4c1-Item4c": safe_divide(securities_031.CommericalPassThru("htm", "ac"), securities_031.CommericalPassThru("htm", "ac") + securities_031.OtherCommericalMBS("htm", "ac")),
        "RCB-Item4c2-Item4c": safe_divide(securities_031.OtherCommericalMBS("htm", "ac"), securities_031.CommericalPassThru("htm", "ac") + securities_031.OtherCommericalMBS("htm", "ac")),
        "RCB-0213-0211": safe_divide(securities_031.USTreasuries("htm", "fv"), securities_031.USTreasuries("htm", "ac")),
        "RCB-HT51-HT50": safe_divide(securities_031.USGovtObligations("htm", "fv"), securities_031.USGovtObligations("htm", "ac")),
        "RCB-8497-8496": safe_divide(securities_031.StateSecurities("htm", "fv"), securities_031.StateSecurities("htm", "ac")),
        "RCB-item4a-fv2ac": safe_divide(securities_031.ResidentialPassThru.Total("htm", "fv"), securities_031.ResidentialPassThru.Total("htm", "ac")),
        "RCB-item4b-fv2ac": safe_divide(securities_031.OtherResidentialPassThru("htm", "fv"), securities_031.OtherResidentialPassThru("htm", "ac")),
        "RCB-item4c-fv2ac": safe_divide(securities_031.CommericalPassThru("htm", "fv") + securities_031.OtherCommericalMBS("htm", "fv"), securities_031.CommericalPassThru("htm", "ac") + securities_031.OtherCommericalMBS("htm", "ac")),
        "RCB-A549-itemM2a": safe_divide(government_031.ThreeMonths(), government_031.Total()),
        "RCB-A550-itemM2a": safe_divide(government_031.TwelveMonths(), government_031.Total()),
        "RCB-A551-itemM2a": safe_divide(government_031.ThreeYears(), government_031.Total()),
        "RCB-A552-itemM2a": safe_divide(government_031.FiveYears(), government_031.Total()),
        "RCB-A553-itemM2a": safe_divide(government_031.FifteenYears(), government_031.Total()),
        "RCB-A554-itemM2a": safe_divide(government_031.OverFifteenYears(), government_031.Total()),
        "RCB-A555-itemM2b": safe_divide(residential_031.ThreeMonths(), residential_031.Total()),
        "RCB-A556-itemM2b": safe_divide(residential_031.TwelveMonths(), residential_031.Total()),
        "RCB-A557-itemM2b": safe_divide(residential_031.ThreeYears(), residential_031.Total()),
        "RCB-A558-itemM2b": safe_divide(residential_031.FiveYears(), residential_031.Total()),
        "RCB-A559-itemM2b": safe_divide(residential_031.FifteenYears(), residential_031.Total()),
        "RCB-A560-itemM2b": safe_divide(residential_031.OverFifteenYears(), residential_031.Total()),
        "RC-Item1-Item12": safe_divide(balance_031.CashAndBalancesDue(), balance_031.TotalAssets()),
        "RC-Item2-Item12": safe_divide(balance_031.TotalSecurities(), balance_031.TotalAssets()),
        "RC-Item4-Item12": safe_divide(loans_031.TotalIncludingHeldForSale(), balance_031.TotalAssets()),
        "RC-Item14-Item12": safe_divide(balance_031.FederalFundsPurchased(), balance_031.TotalAssets()),
        "RC-Item10-Item12": safe_divide(balance_031.IntangibleAssets(), balance_031.TotalAssets()),
        "RC-Item4-Item21": safe_divide(loans_031.TotalIncludingHeldForSale(), balance_031.TotalLiabilitiesIncludingAllowance()),
        "RC-Item5-Item21": safe_divide(balance_031.TradingAssets(), balance_031.TotalLiabilitiesIncludingAllowance()),
        "RC-2200-Item21": safe_divide(deposits.ReportedTotal(), balance_031.TotalLiabilitiesIncludingAllowance()),
        "RC-3548-Item21": safe_divide(balance_031.TradingLiabilities(), balance_031.TotalLiabilitiesIncludingAllowance()),
        "RC-3190-Item21": safe_divide(balance_031.OtherBorrowedMoney(), balance_031.TotalLiabilitiesIncludingAllowance()),
        "RC-2930-Item21": safe_divide(balance_031.OtherLiabilities(), balance_031.TotalLiabilitiesIncludingAllowance()),
        "RC-Item10-G105": safe_divide(balance_031.IntangibleAssets(), balance_031.ReportedTotalEquityCapital()),
        "RCE-B549-2215": safe_divide(transaction.Individuals(), transaction.ReportedTotal()),
        "RCE-2202-2215": safe_divide(transaction.USGovt(), transaction.ReportedTotal()),
        "RCE-2203-2215": safe_divide(transaction.StatesAndPolitical(), transaction.ReportedTotal()),
        "RCE-B551-2215": safe_divide(transaction.CommercialBanks(), transaction.ReportedTotal()),
        "RCE-2213-2215": safe_divide(transaction.ForeignBanks(), transaction.ReportedTotal()),
        "RCE-2216-2215": safe_divide(transaction.ForeignGovt(), transaction.ReportedTotal()),
        "RCE-2215-2200": safe_divide(transaction.ReportedTotal(), deposits.ReportedTotal()),
        "RCE-B550-2385": safe_divide(nontransaction.Individuals(), nontransaction.ReportedTotal()),
        "RCE-2385-2200": safe_divide(nontransaction.ReportedTotal(), deposits.ReportedTotal()),
        "RCE-itemM2a-2385": safe_divide(nontransaction.SavingsTotal(), nontransaction.ReportedTotal()),
        "RCE-6648-2385": safe_divide(time_deposits.LessThan100k(), nontransaction.ReportedTotal()),
        "RCE-J473-2385": safe_divide(less_than_250k.ReportedTotal(), nontransaction.ReportedTotal()),
        "RCE-J474-2385": safe_divide(time_deposits.MoreThan250k.ReportedTotal(), nontransaction.ReportedTotal()),
        "RCE-HK07-savings": safe_divide(less_than_250k.EffectiveThreeMonths(), time_deposits.LessThan100k() + less_than_250k.ReportedTotal()),
        "RCE-HK08-savings": safe_divide(less_than_250k.EffectiveTwelveMonths(), time_deposits.LessThan100k() + less_than_250k.ReportedTotal()),
        "RCE-HK09-savings": safe_divide(less_than_250k.EffectiveThreeYears(), time_deposits.LessThan100k() + less_than_250k.ReportedTotal()),
        "RCE-HK10-savings": safe_divide(less_than_250k.EffectiveOverThreeYears(), time_deposits.LessThan100k() + less_than_250k.ReportedTotal()),
        "RCRI-P840-A223": safe_divide(capital_031.TierOneCapital(), capital_031.RiskWeightedAssets()),
        "RCRI-P840-RWA+": safe_divide(capital_031.TierOneCapital(), capital_031.AugmentedRiskWeightedAssets()),
        "RCRI-P859-A223": safe_divide(capital_031.CommonEquityTierOneCapital(), capital_031.RiskWeightedAssets()),
        "RCRI-P859-RWA+": safe_divide(capital_031.CommonEquityTierOneCapital(), capital_031.AugmentedRiskWeightedAssets()),
        "RCRI-ZRWA-A223": capital_031.ZeroRiskToReportedRWA(),
        "RCRI-ZRWA-RWA": capital_031.ZeroRiskToAugmentedRWA(),
        "RCRI-ZRWA-RWA+": capital_031.AdjustedZeroRiskToAugmentedRWA(),
        "RCRI-ZRWA-RWA++": capital_031.RelativeZeroRiskAdjustment(),
    }

    if tuple(entry1) != FEATURE_COLUMNS or tuple(entry2) != FEATURE_COLUMNS:
        raise AssertionError("Call Report output schema changed")
    return entry1, entry2


def select_report_entry(row):
    entry1, entry2 = create_ratio_entries(row)
    candidates = [
        entry for entry in (entry1, entry2)
        if not is_missing(entry["RCB-HT53-1773"])
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda entry: sum(is_missing(v) for v in entry.values()))


def process_dataframe(frame):
    columns = tuple(frame.columns)
    records = []
    for values in frame.itertuples(index=False, name=None):
        row = dict(zip(columns, values))
        selected = select_report_entry(row)
        if selected is not None:
            records.append(selected)
    result = pd.DataFrame.from_records(records, columns=FEATURE_COLUMNS)
    if result.empty:
        return result
    result["_missing_values"] = result.isna().sum(axis=1)
    result = result.sort_values(["IDRSSD", "_missing_values"], kind="mergesort")
    return result.drop_duplicates("IDRSSD", keep="first").drop(columns="_missing_values")


def process_file(input_path, output_path):
    input_path = Path(input_path)
    output_path = Path(output_path)
    result = process_dataframe(pd.read_csv(input_path, low_memory=False))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    result.to_csv(temporary_path, index=False)
    temporary_path.replace(output_path)
    return output_path


def build_interleaved_reports(input_dir, output_dir):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    written = []
    for input_path in sorted(input_dir.glob("*.csv")):
        output_path = process_file(input_path, output_dir / input_path.name)
        written.append(output_path)
        print("Wrote {}".format(output_path))
    return written


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path(paths.CLEANED_DIR))
    parser.add_argument("--output-dir", type=Path, default=Path(paths.INTERLEAVED_DIR))
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    written = build_interleaved_reports(args.input_dir, args.output_dir)
    print("Processed {} Call Report files".format(len(written)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
