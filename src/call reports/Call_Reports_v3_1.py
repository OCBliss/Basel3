"""Build Call Report v3 ratios for a selected relative quarter."""

import argparse
from pathlib import Path
import sys

import pandas as pd


call_dir = Path(__file__).resolve().parent
src_dir = call_dir.parent
for import_path in (call_dir, src_dir):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import Basel3_Global_Filepath as paths  # noqa: E402
from Call_Report import (  # noqa: E402
    CallReport_031,
    CallReport_051,
    QuarterCache,
    safe_divide,
)


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
    return bool(pd.isna(value))


def build_entry(report, date="P0"):
    """Build one ratio row entirely from one Call Report form."""

    balance = report.BalanceSheet
    loans = balance.LoansAndLeaseFinancingReceivables
    securities = report.Securities
    government_maturities = report.Maturities.Government
    residential_maturities = report.Maturities.ResidentialMortgage
    domestic_deposits = report.DepositLiabilities
    transaction = domestic_deposits.TransactionDeposits
    nontransaction = domestic_deposits.NonTransactionDeposits
    time_deposits = nontransaction.TimeDeposits
    less_than_250k = time_deposits.LessThan250k
    capital = report.RegulatoryCapital

    entry = {
        "IDRSSD": report.RSSDID(date=date),
        "RCON9999": report.ReportingDate(date=date),
        "CERT": report.Certificate(date=date),
        "RCB-0211-1754": safe_divide(securities.USTreasuries("htm", "ac", date=date), securities.Total("htm", "ac", date=date)),
        "RCB-1287-1773": safe_divide(securities.USTreasuries("afs", "fv", date=date), securities.Total("afs", "fv", date=date)),
        "RCB-item4-1754": safe_divide(securities.MBSTotal("htm", "ac", date=date), securities.Total("htm", "ac", date=date)),
        "RCB-HT50-1754": safe_divide(securities.USGovtObligations("htm", "ac", date=date), securities.Total("htm", "ac", date=date)),
        "RCB-HT53-1773": safe_divide(securities.USGovtObligations("afs", "fv", date=date), securities.Total("afs", "fv", date=date)),
        "RCB-8496-1754": safe_divide(securities.StateSecurities("htm", "ac", date=date), securities.Total("htm", "ac", date=date)),
        "RCB-8499-1773": safe_divide(securities.StateSecurities("afs", "fv", date=date), securities.Total("afs", "fv", date=date)),
        "RCB-G300-item4a": safe_divide(securities.GNMAPassThru("htm", "ac", date=date), securities.ResidentialPassThru.Total("htm", "ac", date=date)),
        "RCB-G304-Item4a": safe_divide(securities.FNMAPassThru("htm", "ac", date=date), securities.ResidentialPassThru.Total("htm", "ac", date=date)),
        "RCB-G308-Item4a": safe_divide(securities.OtherPassThru("htm", "ac", date=date), securities.ResidentialPassThru.Total("htm", "ac", date=date)),
        "RCB-G303-item4a": safe_divide(securities.GNMAPassThru("afs", "fv", date=date), securities.ResidentialPassThru.Total("afs", "fv", date=date)),
        "RCB-G307-Item4a": safe_divide(securities.FNMAPassThru("afs", "fv", date=date), securities.ResidentialPassThru.Total("afs", "fv", date=date)),
        "RCB-G311-Item4a": safe_divide(securities.OtherPassThru("afs", "fv", date=date), securities.ResidentialPassThru.Total("afs", "fv", date=date)),
        "RCB-G312-item4b": safe_divide(securities.OtherResidentialGNMA("htm", "ac", date=date), securities.OtherResidentialPassThru("htm", "ac", date=date)),
        "RCB-G316-Item4b": safe_divide(securities.OtherResidentialFNMA("htm", "ac", date=date), securities.OtherResidentialPassThru("htm", "ac", date=date)),
        "RCB-G320-Item4b": safe_divide(securities.OtherResidentialOther("htm", "ac", date=date), securities.OtherResidentialPassThru("htm", "ac", date=date)),
        "RCB-G315-item4b": safe_divide(securities.OtherResidentialGNMA("afs", "fv", date=date), securities.OtherResidentialPassThru("afs", "fv", date=date)),
        "RCB-G319-Item4b": safe_divide(securities.OtherResidentialFNMA("afs", "fv", date=date), securities.OtherResidentialPassThru("afs", "fv", date=date)),
        "RCB-G323-Item4b": safe_divide(securities.OtherResidentialOther("afs", "fv", date=date), securities.OtherResidentialPassThru("afs", "fv", date=date)),
        "RCB-Item4c1-Item4c": safe_divide(securities.CommericalPassThru("htm", "ac", date=date), securities.CommericalPassThru("htm", "ac", date=date) + securities.OtherCommericalMBS("htm", "ac", date=date)),
        "RCB-Item4c2-Item4c": safe_divide(securities.OtherCommericalMBS("htm", "ac", date=date), securities.CommericalPassThru("htm", "ac", date=date) + securities.OtherCommericalMBS("htm", "ac", date=date)),
        "RCB-0213-0211": safe_divide(securities.USTreasuries("htm", "fv", date=date), securities.USTreasuries("htm", "ac", date=date)),
        "RCB-HT51-HT50": safe_divide(securities.USGovtObligations("htm", "fv", date=date), securities.USGovtObligations("htm", "ac", date=date)),
        "RCB-8497-8496": safe_divide(securities.StateSecurities("htm", "fv", date=date), securities.StateSecurities("htm", "ac", date=date)),
        "RCB-item4a-fv2ac": safe_divide(securities.ResidentialPassThru.Total("htm", "fv", date=date), securities.ResidentialPassThru.Total("htm", "ac", date=date)),
        "RCB-item4b-fv2ac": safe_divide(securities.OtherResidentialPassThru("htm", "fv", date=date), securities.OtherResidentialPassThru("htm", "ac", date=date)),
        "RCB-item4c-fv2ac": safe_divide(securities.CommericalPassThru("htm", "fv", date=date) + securities.OtherCommericalMBS("htm", "fv", date=date), securities.CommericalPassThru("htm", "ac", date=date) + securities.OtherCommericalMBS("htm", "ac", date=date)),
        "RCB-A549-itemM2a": safe_divide(government_maturities.ThreeMonths(date=date), government_maturities.Total(date=date)),
        "RCB-A550-itemM2a": safe_divide(government_maturities.TwelveMonths(date=date), government_maturities.Total(date=date)),
        "RCB-A551-itemM2a": safe_divide(government_maturities.ThreeYears(date=date), government_maturities.Total(date=date)),
        "RCB-A552-itemM2a": safe_divide(government_maturities.FiveYears(date=date), government_maturities.Total(date=date)),
        "RCB-A553-itemM2a": safe_divide(government_maturities.FifteenYears(date=date), government_maturities.Total(date=date)),
        "RCB-A554-itemM2a": safe_divide(government_maturities.OverFifteenYears(date=date), government_maturities.Total(date=date)),
        "RCB-A555-itemM2b": safe_divide(residential_maturities.ThreeMonths(date=date), residential_maturities.Total(date=date)),
        "RCB-A556-itemM2b": safe_divide(residential_maturities.TwelveMonths(date=date), residential_maturities.Total(date=date)),
        "RCB-A557-itemM2b": safe_divide(residential_maturities.ThreeYears(date=date), residential_maturities.Total(date=date)),
        "RCB-A558-itemM2b": safe_divide(residential_maturities.FiveYears(date=date), residential_maturities.Total(date=date)),
        "RCB-A559-itemM2b": safe_divide(residential_maturities.FifteenYears(date=date), residential_maturities.Total(date=date)),
        "RCB-A560-itemM2b": safe_divide(residential_maturities.OverFifteenYears(date=date), residential_maturities.Total(date=date)),
        "RC-Item1-Item12": safe_divide(balance.CashAndBalancesDue(date=date), balance.TotalAssets(date=date)),
        "RC-Item2-Item12": safe_divide(balance.TotalSecurities(date=date), balance.TotalAssets(date=date)),
        "RC-Item4-Item12": safe_divide(loans.TotalIncludingHeldForSale(date=date), balance.TotalAssets(date=date)),
        "RC-Item14-Item12": safe_divide(balance.FederalFundsPurchased(date=date), balance.TotalAssets(date=date)),
        "RC-Item10-Item12": safe_divide(balance.IntangibleAssets(date=date), balance.TotalAssets(date=date)),
        "RC-Item4-Item21": safe_divide(loans.TotalIncludingHeldForSale(date=date), balance.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-Item5-Item21": safe_divide(balance.TradingAssets(date=date), balance.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-2200-Item21": safe_divide(domestic_deposits.ReportedTotal(date=date), balance.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-3548-Item21": safe_divide(balance.TradingLiabilities(date=date), balance.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-3190-Item21": safe_divide(balance.OtherBorrowedMoney(date=date), balance.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-2930-Item21": safe_divide(balance.OtherLiabilities(date=date), balance.TotalLiabilitiesIncludingAllowance(date=date)),
        "RC-Item10-G105": safe_divide(balance.IntangibleAssets(date=date), balance.ReportedTotalEquityCapital(date=date)),
        "RCE-B549-2215": safe_divide(transaction.Individuals(date=date), transaction.ReportedTotal(date=date)),
        "RCE-2202-2215": safe_divide(transaction.USGovt(date=date), transaction.ReportedTotal(date=date)),
        "RCE-2203-2215": safe_divide(transaction.StatesAndPolitical(date=date), transaction.ReportedTotal(date=date)),
        "RCE-B551-2215": safe_divide(transaction.CommercialBanks(date=date), transaction.ReportedTotal(date=date)),
        "RCE-2213-2215": safe_divide(transaction.ForeignBanks(date=date), transaction.ReportedTotal(date=date)),
        "RCE-2216-2215": safe_divide(transaction.ForeignGovt(date=date), transaction.ReportedTotal(date=date)),
        "RCE-2215-2200": safe_divide(transaction.ReportedTotal(date=date), domestic_deposits.ReportedTotal(date=date)),
        "RCE-B550-2385": safe_divide(nontransaction.Individuals(date=date), nontransaction.ReportedTotal(date=date)),
        "RCE-2385-2200": safe_divide(nontransaction.ReportedTotal(date=date), domestic_deposits.ReportedTotal(date=date)),
        "RCE-itemM2a-2385": safe_divide(nontransaction.SavingsTotal(date=date), nontransaction.ReportedTotal(date=date)),
        "RCE-6648-2385": safe_divide(time_deposits.LessThan100k(date=date), nontransaction.ReportedTotal(date=date)),
        "RCE-J473-2385": safe_divide(less_than_250k.ReportedTotal(date=date), nontransaction.ReportedTotal(date=date)),
        "RCE-J474-2385": safe_divide(time_deposits.MoreThan250k.ReportedTotal(date=date), nontransaction.ReportedTotal(date=date)),
        "RCE-HK07-savings": safe_divide(less_than_250k.EffectiveThreeMonths(date=date), time_deposits.LessThan100k(date=date) + less_than_250k.ReportedTotal(date=date)),
        "RCE-HK08-savings": safe_divide(less_than_250k.EffectiveTwelveMonths(date=date), time_deposits.LessThan100k(date=date) + less_than_250k.ReportedTotal(date=date)),
        "RCE-HK09-savings": safe_divide(less_than_250k.EffectiveThreeYears(date=date), time_deposits.LessThan100k(date=date) + less_than_250k.ReportedTotal(date=date)),
        "RCE-HK10-savings": safe_divide(less_than_250k.EffectiveOverThreeYears(date=date), time_deposits.LessThan100k(date=date) + less_than_250k.ReportedTotal(date=date)),
        "RCRI-P840-A223": safe_divide(capital.TierOneCapital(date=date), capital.RiskWeightedAssets(date=date)),
        "RCRI-P840-RWA+": safe_divide(capital.TierOneCapital(date=date), capital.AugmentedRiskWeightedAssets(date=date)),
        "RCRI-P859-A223": safe_divide(capital.CommonEquityTierOneCapital(date=date), capital.RiskWeightedAssets(date=date)),
        "RCRI-P859-RWA+": safe_divide(capital.CommonEquityTierOneCapital(date=date), capital.AugmentedRiskWeightedAssets(date=date)),
        "RCRI-ZRWA-A223": capital.ZeroRiskToReportedRWA(date=date),
        "RCRI-ZRWA-RWA": capital.ZeroRiskToAugmentedRWA(date=date),
        "RCRI-ZRWA-RWA+": capital.AdjustedZeroRiskToAugmentedRWA(date=date),
        "RCRI-ZRWA-RWA++": capital.RelativeZeroRiskAdjustment(date=date),
    }

    if tuple(entry) != FEATURE_COLUMNS:
        raise AssertionError("Call Report output schema changed")
    return entry


def create_ratio_entries(row, history=None, date="P0"):
    report_051 = CallReport_051(row, history=history)
    report_031 = CallReport_031(row, history=history)

    return (
        build_entry(report_051, date=date),
        build_entry(report_031, date=date),
    )


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
    parser.add_argument("--input-dir", type=Path, default=Path(paths.CLEANED_DIR))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(paths.INTERLEAVED_DIR),
    )
    parser.add_argument("--quarter-map", type=Path)
    parser.add_argument("--date", default="P0")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    written = build_interleaved_reports(
        args.input_dir,
        args.output_dir,
        date=args.date,
        map_file=args.quarter_map,
    )
    print("Processed {} Call Report files".format(len(written)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
