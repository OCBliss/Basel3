"""Create vertical Call Report ratios from the imported domain functions."""

import argparse
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

REPORT_ELIGIBILITY_RATIO = "RCB-HT53-1773"


def is_missing(value):
    return bool(pd.isna(value))


def build_entry(report, domestic_deposits):
    """Build one ratio row from one report and the domestic RC-E schedule."""

    balance = report.BalanceSheet
    loans = balance.LoansAndLeaseFinancingReceivables
    securities = report.Securities
    government_maturities = report.Maturities.Government
    residential_maturities = report.Maturities.ResidentialMortgage
    transaction = domestic_deposits.TransactionDeposits
    nontransaction = domestic_deposits.NonTransactionDeposits
    time_deposits = nontransaction.TimeDeposits
    less_than_250k = time_deposits.LessThan250k
    capital = report.RegulatoryCapital

    entry = {
        "IDRSSD": report.RSSDID(),
        "RCON9999": report.ReportingDate(),
        "CERT": report.Certificate(),
        "RCB-0211-1754": safe_divide(securities.USTreasuries("htm", "ac"), securities.Total("htm", "ac")),
        "RCB-1287-1773": safe_divide(securities.USTreasuries("afs", "fv"), securities.Total("afs", "fv")),
        "RCB-item4-1754": safe_divide(securities.MBSTotal("htm", "ac"), securities.Total("htm", "ac")),
        "RCB-HT50-1754": safe_divide(securities.USGovtObligations("htm", "ac"), securities.Total("htm", "ac")),
        "RCB-HT53-1773": safe_divide(securities.USGovtObligations("afs", "fv"), securities.Total("afs", "fv")),
        "RCB-8496-1754": safe_divide(securities.StateSecurities("htm", "ac"), securities.Total("htm", "ac")),
        "RCB-8499-1773": safe_divide(securities.StateSecurities("afs", "fv"), securities.Total("afs", "fv")),
        "RCB-G300-item4a": safe_divide(securities.GNMAPassThru("htm", "ac"), securities.ResidentialPassThru.Total("htm", "ac")),
        "RCB-G304-Item4a": safe_divide(securities.FNMAPassThru("htm", "ac"), securities.ResidentialPassThru.Total("htm", "ac")),
        "RCB-G308-Item4a": safe_divide(securities.OtherPassThru("htm", "ac"), securities.ResidentialPassThru.Total("htm", "ac")),
        "RCB-G303-item4a": safe_divide(securities.GNMAPassThru("afs", "fv"), securities.ResidentialPassThru.Total("afs", "fv")),
        "RCB-G307-Item4a": safe_divide(securities.FNMAPassThru("afs", "fv"), securities.ResidentialPassThru.Total("afs", "fv")),
        "RCB-G311-Item4a": safe_divide(securities.OtherPassThru("afs", "fv"), securities.ResidentialPassThru.Total("afs", "fv")),
        "RCB-G312-item4b": safe_divide(securities.OtherResidentialGNMA("htm", "ac"), securities.OtherResidentialPassThru("htm", "ac")),
        "RCB-G316-Item4b": safe_divide(securities.OtherResidentialFNMA("htm", "ac"), securities.OtherResidentialPassThru("htm", "ac")),
        "RCB-G320-Item4b": safe_divide(securities.OtherResidentialOther("htm", "ac"), securities.OtherResidentialPassThru("htm", "ac")),
        "RCB-G315-item4b": safe_divide(securities.OtherResidentialGNMA("afs", "fv"), securities.OtherResidentialPassThru("afs", "fv")),
        "RCB-G319-Item4b": safe_divide(securities.OtherResidentialFNMA("afs", "fv"), securities.OtherResidentialPassThru("afs", "fv")),
        "RCB-G323-Item4b": safe_divide(securities.OtherResidentialOther("afs", "fv"), securities.OtherResidentialPassThru("afs", "fv")),
        "RCB-Item4c1-Item4c": safe_divide(securities.CommericalPassThru("htm", "ac"), securities.CommericalPassThru("htm", "ac") + securities.OtherCommericalMBS("htm", "ac")),
        "RCB-Item4c2-Item4c": safe_divide(securities.OtherCommericalMBS("htm", "ac"), securities.CommericalPassThru("htm", "ac") + securities.OtherCommericalMBS("htm", "ac")),
        "RCB-0213-0211": safe_divide(securities.USTreasuries("htm", "fv"), securities.USTreasuries("htm", "ac")),
        "RCB-HT51-HT50": safe_divide(securities.USGovtObligations("htm", "fv"), securities.USGovtObligations("htm", "ac")),
        "RCB-8497-8496": safe_divide(securities.StateSecurities("htm", "fv"), securities.StateSecurities("htm", "ac")),
        "RCB-item4a-fv2ac": safe_divide(securities.ResidentialPassThru.Total("htm", "fv"), securities.ResidentialPassThru.Total("htm", "ac")),
        "RCB-item4b-fv2ac": safe_divide(securities.OtherResidentialPassThru("htm", "fv"), securities.OtherResidentialPassThru("htm", "ac")),
        "RCB-item4c-fv2ac": safe_divide(securities.CommericalPassThru("htm", "fv") + securities.OtherCommericalMBS("htm", "fv"), securities.CommericalPassThru("htm", "ac") + securities.OtherCommericalMBS("htm", "ac")),
        "RCB-A549-itemM2a": safe_divide(government_maturities.ThreeMonths(), government_maturities.Total()),
        "RCB-A550-itemM2a": safe_divide(government_maturities.TwelveMonths(), government_maturities.Total()),
        "RCB-A551-itemM2a": safe_divide(government_maturities.ThreeYears(), government_maturities.Total()),
        "RCB-A552-itemM2a": safe_divide(government_maturities.FiveYears(), government_maturities.Total()),
        "RCB-A553-itemM2a": safe_divide(government_maturities.FifteenYears(), government_maturities.Total()),
        "RCB-A554-itemM2a": safe_divide(government_maturities.OverFifteenYears(), government_maturities.Total()),
        "RCB-A555-itemM2b": safe_divide(residential_maturities.ThreeMonths(), residential_maturities.Total()),
        "RCB-A556-itemM2b": safe_divide(residential_maturities.TwelveMonths(), residential_maturities.Total()),
        "RCB-A557-itemM2b": safe_divide(residential_maturities.ThreeYears(), residential_maturities.Total()),
        "RCB-A558-itemM2b": safe_divide(residential_maturities.FiveYears(), residential_maturities.Total()),
        "RCB-A559-itemM2b": safe_divide(residential_maturities.FifteenYears(), residential_maturities.Total()),
        "RCB-A560-itemM2b": safe_divide(residential_maturities.OverFifteenYears(), residential_maturities.Total()),
        "RC-Item1-Item12": safe_divide(balance.CashAndBalancesDue(), balance.TotalAssets()),
        "RC-Item2-Item12": safe_divide(balance.TotalSecurities(), balance.TotalAssets()),
        "RC-Item4-Item12": safe_divide(loans.TotalIncludingHeldForSale(), balance.TotalAssets()),
        "RC-Item14-Item12": safe_divide(balance.FederalFundsPurchased(), balance.TotalAssets()),
        "RC-Item10-Item12": safe_divide(balance.IntangibleAssets(), balance.TotalAssets()),
        "RC-Item4-Item21": safe_divide(loans.TotalIncludingHeldForSale(), balance.TotalLiabilitiesIncludingAllowance()),
        "RC-Item5-Item21": safe_divide(balance.TradingAssets(), balance.TotalLiabilitiesIncludingAllowance()),
        "RC-2200-Item21": safe_divide(domestic_deposits.ReportedTotal(), balance.TotalLiabilitiesIncludingAllowance()),
        "RC-3548-Item21": safe_divide(balance.TradingLiabilities(), balance.TotalLiabilitiesIncludingAllowance()),
        "RC-3190-Item21": safe_divide(balance.OtherBorrowedMoney(), balance.TotalLiabilitiesIncludingAllowance()),
        "RC-2930-Item21": safe_divide(balance.OtherLiabilities(), balance.TotalLiabilitiesIncludingAllowance()),
        "RC-Item10-G105": safe_divide(balance.IntangibleAssets(), balance.ReportedTotalEquityCapital()),
        "RCE-B549-2215": safe_divide(transaction.Individuals(), transaction.ReportedTotal()),
        "RCE-2202-2215": safe_divide(transaction.USGovt(), transaction.ReportedTotal()),
        "RCE-2203-2215": safe_divide(transaction.StatesAndPolitical(), transaction.ReportedTotal()),
        "RCE-B551-2215": safe_divide(transaction.CommercialBanks(), transaction.ReportedTotal()),
        "RCE-2213-2215": safe_divide(transaction.ForeignBanks(), transaction.ReportedTotal()),
        "RCE-2216-2215": safe_divide(transaction.ForeignGovt(), transaction.ReportedTotal()),
        "RCE-2215-2200": safe_divide(transaction.ReportedTotal(), domestic_deposits.ReportedTotal()),
        "RCE-B550-2385": safe_divide(nontransaction.Individuals(), nontransaction.ReportedTotal()),
        "RCE-2385-2200": safe_divide(nontransaction.ReportedTotal(), domestic_deposits.ReportedTotal()),
        "RCE-itemM2a-2385": safe_divide(nontransaction.SavingsTotal(), nontransaction.ReportedTotal()),
        "RCE-6648-2385": safe_divide(time_deposits.LessThan100k(), nontransaction.ReportedTotal()),
        "RCE-J473-2385": safe_divide(less_than_250k.ReportedTotal(), nontransaction.ReportedTotal()),
        "RCE-J474-2385": safe_divide(time_deposits.MoreThan250k.ReportedTotal(), nontransaction.ReportedTotal()),
        "RCE-HK07-savings": safe_divide(less_than_250k.EffectiveThreeMonths(), time_deposits.LessThan100k() + less_than_250k.ReportedTotal()),
        "RCE-HK08-savings": safe_divide(less_than_250k.EffectiveTwelveMonths(), time_deposits.LessThan100k() + less_than_250k.ReportedTotal()),
        "RCE-HK09-savings": safe_divide(less_than_250k.EffectiveThreeYears(), time_deposits.LessThan100k() + less_than_250k.ReportedTotal()),
        "RCE-HK10-savings": safe_divide(less_than_250k.EffectiveOverThreeYears(), time_deposits.LessThan100k() + less_than_250k.ReportedTotal()),
        "RCRI-P840-A223": safe_divide(capital.TierOneCapital(), capital.RiskWeightedAssets()),
        "RCRI-P840-RWA+": safe_divide(capital.TierOneCapital(), capital.AugmentedRiskWeightedAssets()),
        "RCRI-P859-A223": safe_divide(capital.CommonEquityTierOneCapital(), capital.RiskWeightedAssets()),
        "RCRI-P859-RWA+": safe_divide(capital.CommonEquityTierOneCapital(), capital.AugmentedRiskWeightedAssets()),
        "RCRI-ZRWA-A223": capital.ZeroRiskToReportedRWA(),
        "RCRI-ZRWA-RWA": capital.ZeroRiskToAugmentedRWA(),
        "RCRI-ZRWA-RWA+": capital.AdjustedZeroRiskToAugmentedRWA(),
        "RCRI-ZRWA-RWA++": capital.RelativeZeroRiskAdjustment(),
    }

    if tuple(entry) != FEATURE_COLUMNS:
        raise AssertionError("Call Report output schema changed")
    return entry


def create_ratio_entries(row):
    """Build the domestic and consolidated entries for one source row."""

    domestic_report = CallReport_051(row)
    consolidated_report = CallReport_031(row)
    domestic_deposits = domestic_report.DepositLiabilities
    return (
        build_entry(domestic_report, domestic_deposits),
        build_entry(consolidated_report, domestic_deposits),
    )


def select_report_entry(row):
    domestic_entry, consolidated_entry = create_ratio_entries(row)

    domestic_is_usable = not is_missing(domestic_entry[REPORT_ELIGIBILITY_RATIO])
    consolidated_is_usable = not is_missing(
        consolidated_entry[REPORT_ELIGIBILITY_RATIO]
    )

    if not domestic_is_usable and not consolidated_is_usable:
        return None
    if not domestic_is_usable:
        return consolidated_entry
    if not consolidated_is_usable:
        return domestic_entry

    domestic_blanks = sum(is_missing(value) for value in domestic_entry.values())
    consolidated_blanks = sum(
        is_missing(value) for value in consolidated_entry.values()
    )
    if consolidated_blanks < domestic_blanks:
        return consolidated_entry
    return domestic_entry


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
