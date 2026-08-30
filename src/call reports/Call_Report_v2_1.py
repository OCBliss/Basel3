"""Build the contemporaneous Call Report ratio layer.

The financial primitives live in :mod:`Call_Report`.  This module translates
the retrospective v5 calculation into those functions and handles the tabular
pipeline boundary.
"""

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
from Call_Report import (  # noqa: E402
    CallReport_031,
    CallReport_051,
    safe_divide,
)


IDENTIFIER_COLUMNS = ("IDRSSD", "RCON9999", "CERT")
SECURITIES_COLUMNS = (
    "RCB-0211-1754",
    "RCB-1287-1773",
    "RCB-item4-1754",
    "RCB-HT50-1754",
    "RCB-HT53-1773",
    "RCB-8496-1754",
    "RCB-8499-1773",
    "RCB-G300-item4a",
    "RCB-G304-Item4a",
    "RCB-G308-Item4a",
    "RCB-G303-item4a",
    "RCB-G307-Item4a",
    "RCB-G311-Item4a",
    "RCB-G312-item4b",
    "RCB-G316-Item4b",
    "RCB-G320-Item4b",
    "RCB-G315-item4b",
    "RCB-G319-Item4b",
    "RCB-G323-Item4b",
    "RCB-Item4c1-Item4c",
    "RCB-Item4c2-Item4c",
    "RCB-0213-0211",
    "RCB-HT51-HT50",
    "RCB-8497-8496",
    "RCB-item4a-fv2ac",
    "RCB-item4b-fv2ac",
    "RCB-item4c-fv2ac",
)
MEMORANDA_COLUMNS = tuple(
    "RCB-A{}-item{}".format(code, group)
    for group, codes in (("M2a", range(549, 555)), ("M2b", range(555, 561)))
    for code in codes
)
BALANCE_SHEET_COLUMNS = (
    "RC-Item1-Item12",
    "RC-Item2-Item12",
    "RC-Item4-Item12",
    "RC-Item14-Item12",
    "RC-Item10-Item12",
    "RC-Item4-Item21",
    "RC-Item5-Item21",
    "RC-2200-Item21",
    "RC-3548-Item21",
    "RC-3190-Item21",
    "RC-2930-Item21",
    "RC-Item10-G105",
)
DEPOSIT_COLUMNS = (
    "RCE-B549-2215",
    "RCE-2202-2215",
    "RCE-2203-2215",
    "RCE-B551-2215",
    "RCE-2213-2215",
    "RCE-2216-2215",
    "RCE-2215-2200",
    "RCE-B550-2385",
    "RCE-2385-2200",
    "RCE-itemM2a-2385",
    "RCE-6648-2385",
    "RCE-J473-2385",
    "RCE-J474-2385",
    "RCE-HK07-savings",
    "RCE-HK08-savings",
    "RCE-HK09-savings",
    "RCE-HK10-savings",
)
CAPITAL_COLUMNS = (
    "RCRI-P840-A223",
    "RCRI-P840-RWA+",
    "RCRI-P859-A223",
    "RCRI-P859-RWA+",
    "RCRI-ZRWA-A223",
    "RCRI-ZRWA-RWA",
    "RCRI-ZRWA-RWA+",
    "RCRI-ZRWA-RWA++",
)
FEATURE_COLUMNS = (
    IDENTIFIER_COLUMNS
    + SECURITIES_COLUMNS
    + MEMORANDA_COLUMNS
    + BALANCE_SHEET_COLUMNS
    + DEPOSIT_COLUMNS
    + CAPITAL_COLUMNS
)


class TupleRow:
    """Named constant-time access to a tuple produced by pandas."""

    __slots__ = ("values", "positions")

    def __init__(self, values, positions):
        self.values = values
        self.positions = positions

    def __getitem__(self, column):
        return self.values[self.positions[column]]


def is_missing(value):
    if value is None:
        return True
    try:
        return math.isnan(value)
    except (TypeError, ValueError):
        return False


def _balance_sheet_values(report):
    balance_sheet = report.BalanceSheet
    loans = balance_sheet.LoansAndLeaseFinancingReceivables
    total_loans = loans.LoansAndLeasesHeldForSale() + loans.Total()
    total_liabilities = balance_sheet.TotalLiabilities() + (
        loans.AllowanceForCreditLossesOnLoansAndLeases()
    )
    return {
        "cash": balance_sheet.CashAndBalancesDue(),
        "securities": balance_sheet.TotalSecurities(),
        "loans": total_loans,
        "trading_assets": balance_sheet.TradingAssets(),
        "intangible_assets": balance_sheet.IntangibleAssets(),
        "total_assets": balance_sheet.TotalAssets(),
        "federal_funds": balance_sheet.FederalFundsPurchased(),
        "total_liabilities": total_liabilities,
    }


def _securities_values(report):
    securities = report.Securities
    return {
        "treasury_htm_ac": securities.USTreasuries("htm", "ac"),
        "treasury_htm_fv": securities.USTreasuries("htm", "fv"),
        "treasury_afs_fv": securities.USTreasuries("afs", "fv"),
        "government_htm_ac": securities.USGovtObligations("htm", "ac"),
        "government_htm_fv": securities.USGovtObligations("htm", "fv"),
        "government_afs_fv": securities.USGovtObligations("afs", "fv"),
        "state_htm_ac": securities.StateSecurities("htm", "ac"),
        "state_htm_fv": securities.StateSecurities("htm", "fv"),
        "state_afs_fv": securities.StateSecurities("afs", "fv"),
        "item4a_htm_ac": securities.ResidentialPassThru.Total("htm", "ac"),
        "item4a_htm_fv": securities.ResidentialPassThru.Total("htm", "fv"),
        "item4a_afs_fv": securities.ResidentialPassThru.Total("afs", "fv"),
        "g300": securities.GNMAPassThru("htm", "ac"),
        "g304": securities.FNMAPassThru("htm", "ac"),
        "g308": securities.OtherPassThru("htm", "ac"),
        "g303": securities.GNMAPassThru("afs", "fv"),
        "g307": securities.FNMAPassThru("afs", "fv"),
        "g311": securities.OtherPassThru("afs", "fv"),
        "item4b_htm_ac": securities.OtherResidentialPassThru("htm", "ac"),
        "item4b_htm_fv": securities.OtherResidentialPassThru("htm", "fv"),
        "item4b_afs_fv": securities.OtherResidentialPassThru("afs", "fv"),
        "g312": securities.OtherResidentialGNMA("htm", "ac"),
        "g316": securities.OtherResidentialFNMA("htm", "ac"),
        "g320": securities.OtherResidentialOther("htm", "ac"),
        "g315": securities.OtherResidentialGNMA("afs", "fv"),
        "g319": securities.OtherResidentialFNMA("afs", "fv"),
        "g323": securities.OtherResidentialOther("afs", "fv"),
        "item4c1_htm_ac": securities.CommericalPassThru("htm", "ac"),
        "item4c1_htm_fv": securities.CommericalPassThru("htm", "fv"),
        "item4c2_htm_ac": securities.OtherCommericalMBS("htm", "ac"),
        "item4c2_htm_fv": securities.OtherCommericalMBS("htm", "fv"),
        "mbs_htm_ac": securities.MBSTotal("htm", "ac"),
        "htm_total": securities.Total("htm", "ac"),
        "afs_total": securities.Total("afs", "fv"),
    }


def _deposit_values(domestic_report):
    deposits = domestic_report.DepositLiabilities
    transaction = deposits.TransactionDeposits
    nontransaction = deposits.NonTransactionDeposits
    time_deposits = nontransaction.TimeDeposits
    under_250k = time_deposits.LessThan250k
    over_250k = time_deposits.MoreThan250k

    if domestic_report.ReportingDate() >= 20170331:
        maturity_values = (
            under_250k.ThreeMonths(),
            under_250k.TwelveMonths(),
            under_250k.ThreeYears(),
            under_250k.OverThreeYears(),
        )
    else:
        maturity_values = tuple(
            domestic_report.Value("RCONA{}".format(code))
            for code in range(579, 583)
        )

    return {
        "transaction_individuals": transaction.Individuals(),
        "transaction_us_government": transaction.USGovt(),
        "transaction_states": transaction.StatesAndPolitical(),
        "transaction_commercial_banks": transaction.CommercialBanks(),
        "transaction_foreign_banks": transaction.ForeignBanks(),
        "transaction_foreign_government": transaction.ForeignGovt(),
        "transaction_total": domestic_report.Value("RCON2215"),
        "nontransaction_individuals": nontransaction.Individuals(),
        "nontransaction_total": domestic_report.Value("RCON2385"),
        "total_deposits": domestic_report.Value("RCON2200"),
        "savings": nontransaction.SavingsMMDA() + nontransaction.SavingsOther(),
        "under_100k": time_deposits.LessThan100k(),
        "under_250k": domestic_report.Value("RCONJ473"),
        "over_250k": over_250k.Total(),
        "under_250k_maturities": maturity_values,
    }


def build_report_features(report, domestic_report, deposit_values=None):
    """Translate every v5 calculation through the Call_Report function layer."""

    balance = _balance_sheet_values(report)
    securities = _securities_values(report)
    deposits = deposit_values or _deposit_values(domestic_report)
    capital = report.RegulatoryCapital
    government_maturities = report.Maturities.Government.Values()
    mortgage_maturities = report.Maturities.ResidentialMortgage.Values()

    item4c_htm_ac = securities["item4c1_htm_ac"] + securities["item4c2_htm_ac"]
    item4c_htm_fv = securities["item4c1_htm_fv"] + securities["item4c2_htm_fv"]

    result = {
        "IDRSSD": report.RSSDID(),
        "RCON9999": report.ReportingDate(),
        "CERT": report.Certificate(),
        "RCB-0211-1754": safe_divide(securities["treasury_htm_ac"], securities["htm_total"]),
        "RCB-1287-1773": safe_divide(securities["treasury_afs_fv"], securities["afs_total"]),
        "RCB-item4-1754": safe_divide(securities["mbs_htm_ac"], securities["htm_total"]),
        "RCB-HT50-1754": safe_divide(securities["government_htm_ac"], securities["htm_total"]),
        "RCB-HT53-1773": safe_divide(securities["government_afs_fv"], securities["afs_total"]),
        "RCB-8496-1754": safe_divide(securities["state_htm_ac"], securities["htm_total"]),
        "RCB-8499-1773": safe_divide(securities["state_afs_fv"], securities["afs_total"]),
        "RCB-G300-item4a": safe_divide(securities["g300"], securities["item4a_htm_ac"]),
        "RCB-G304-Item4a": safe_divide(securities["g304"], securities["item4a_htm_ac"]),
        "RCB-G308-Item4a": safe_divide(securities["g308"], securities["item4a_htm_ac"]),
        "RCB-G303-item4a": safe_divide(securities["g303"], securities["item4a_afs_fv"]),
        "RCB-G307-Item4a": safe_divide(securities["g307"], securities["item4a_afs_fv"]),
        "RCB-G311-Item4a": safe_divide(securities["g311"], securities["item4a_afs_fv"]),
        "RCB-G312-item4b": safe_divide(securities["g312"], securities["item4b_htm_ac"]),
        "RCB-G316-Item4b": safe_divide(securities["g316"], securities["item4b_htm_ac"]),
        "RCB-G320-Item4b": safe_divide(securities["g320"], securities["item4b_htm_ac"]),
        "RCB-G315-item4b": safe_divide(securities["g315"], securities["item4b_afs_fv"]),
        "RCB-G319-Item4b": safe_divide(securities["g319"], securities["item4b_afs_fv"]),
        "RCB-G323-Item4b": safe_divide(securities["g323"], securities["item4b_afs_fv"]),
        "RCB-Item4c1-Item4c": safe_divide(securities["item4c1_htm_ac"], item4c_htm_ac),
        "RCB-Item4c2-Item4c": safe_divide(securities["item4c2_htm_ac"], item4c_htm_ac),
        "RCB-0213-0211": safe_divide(securities["treasury_htm_fv"], securities["treasury_htm_ac"]),
        "RCB-HT51-HT50": safe_divide(securities["government_htm_fv"], securities["government_htm_ac"]),
        "RCB-8497-8496": safe_divide(securities["state_htm_fv"], securities["state_htm_ac"]),
        "RCB-item4a-fv2ac": safe_divide(securities["item4a_htm_fv"], securities["item4a_htm_ac"]),
        "RCB-item4b-fv2ac": safe_divide(securities["item4b_htm_fv"], securities["item4b_htm_ac"]),
        "RCB-item4c-fv2ac": safe_divide(item4c_htm_fv, item4c_htm_ac),
    }

    for group, values in (("M2a", government_maturities), ("M2b", mortgage_maturities)):
        denominator = sum(values)
        first_code = 549 if group == "M2a" else 555
        for offset, value in enumerate(values):
            result["RCB-A{}-item{}".format(first_code + offset, group)] = safe_divide(
                value, denominator
            )

    total_assets = balance["total_assets"]
    total_liabilities = balance["total_liabilities"]
    total_equity = report.Value(
        ("RCON" if isinstance(report, CallReport_031) else "RCFD") + "G105"
    )
    result.update(
        {
            "RC-Item1-Item12": safe_divide(balance["cash"], total_assets),
            "RC-Item2-Item12": safe_divide(balance["securities"], total_assets),
            "RC-Item4-Item12": safe_divide(balance["loans"], total_assets),
            "RC-Item14-Item12": safe_divide(balance["federal_funds"], total_assets),
            "RC-Item10-Item12": safe_divide(balance["intangible_assets"], total_assets),
            "RC-Item4-Item21": safe_divide(balance["loans"], total_liabilities),
            "RC-Item5-Item21": safe_divide(balance["trading_assets"], total_liabilities),
            "RC-2200-Item21": safe_divide(deposits["total_deposits"], total_liabilities),
            "RC-3548-Item21": safe_divide(report.BalanceSheet.TradingLiabilities(), total_liabilities),
            "RC-3190-Item21": safe_divide(
                report.Value(("RCON" if isinstance(report, CallReport_031) else "RCFD") + "3190"),
                total_liabilities,
            ),
            "RC-2930-Item21": safe_divide(report.BalanceSheet.OtherLiabilities(), total_liabilities),
            "RC-Item10-G105": safe_divide(balance["intangible_assets"], total_equity),
            "RCE-B549-2215": safe_divide(deposits["transaction_individuals"], deposits["transaction_total"]),
            "RCE-2202-2215": safe_divide(deposits["transaction_us_government"], deposits["transaction_total"]),
            "RCE-2203-2215": safe_divide(deposits["transaction_states"], deposits["transaction_total"]),
            "RCE-B551-2215": safe_divide(deposits["transaction_commercial_banks"], deposits["transaction_total"]),
            "RCE-2213-2215": safe_divide(deposits["transaction_foreign_banks"], deposits["transaction_total"]),
            "RCE-2216-2215": safe_divide(deposits["transaction_foreign_government"], deposits["transaction_total"]),
            "RCE-2215-2200": safe_divide(deposits["transaction_total"], deposits["total_deposits"]),
            "RCE-B550-2385": safe_divide(deposits["nontransaction_individuals"], deposits["nontransaction_total"]),
            "RCE-2385-2200": safe_divide(deposits["nontransaction_total"], deposits["total_deposits"]),
            "RCE-itemM2a-2385": safe_divide(deposits["savings"], deposits["nontransaction_total"]),
            "RCE-6648-2385": safe_divide(deposits["under_100k"], deposits["nontransaction_total"]),
            "RCE-J473-2385": safe_divide(deposits["under_250k"], deposits["nontransaction_total"]),
            "RCE-J474-2385": safe_divide(deposits["over_250k"], deposits["nontransaction_total"]),
        }
    )

    maturity_denominator = deposits["under_100k"] + deposits["under_250k"]
    for code, value in zip(
        ("HK07", "HK08", "HK09", "HK10"), deposits["under_250k_maturities"]
    ):
        result["RCE-{}-savings".format(code)] = safe_divide(
            value, maturity_denominator
        )

    result.update(
        {
            "RCRI-P840-A223": safe_divide(capital.TierOneCapital(), capital.RiskWeightedAssets()),
            "RCRI-P840-RWA+": safe_divide(capital.TierOneCapital(), capital.AugmentedRiskWeightedAssets()),
            "RCRI-P859-A223": safe_divide(capital.CommonEquityTierOneCapital(), capital.RiskWeightedAssets()),
            "RCRI-P859-RWA+": safe_divide(capital.CommonEquityTierOneCapital(), capital.AugmentedRiskWeightedAssets()),
            "RCRI-ZRWA-A223": capital.ZeroRiskToReportedRWA(),
            "RCRI-ZRWA-RWA": capital.ZeroRiskToAugmentedRWA(),
            "RCRI-ZRWA-RWA+": capital.AdjustedZeroRiskToAugmentedRWA(),
            "RCRI-ZRWA-RWA++": capital.RelativeZeroRiskAdjustment(),
        }
    )

    if tuple(result) != FEATURE_COLUMNS:
        raise AssertionError("Call Report output schema changed")
    return result


def missing_feature_count(features):
    return sum(is_missing(value) for value in features.values())


def select_report_features(row):
    domestic_report = CallReport_031(row)
    reports = (domestic_report, CallReport_051(row))
    eligible_reports = []
    for report in reports:
        discriminator = safe_divide(
            report.Securities.USGovtObligations("afs", "fv"),
            report.Securities.Total("afs", "fv"),
        )
        if not is_missing(discriminator):
            eligible_reports.append(report)

    if not eligible_reports:
        return None
    deposits = _deposit_values(domestic_report)
    candidates = [
        build_report_features(report, domestic_report, deposits)
        for report in eligible_reports
    ]
    return min(candidates, key=missing_feature_count)


def process_dataframe(frame):
    positions = {column: index for index, column in enumerate(frame.columns)}
    records = []
    for values in frame.itertuples(index=False, name=None):
        selected = select_report_features(TupleRow(values, positions))
        if selected is not None:
            records.append(selected)

    result = pd.DataFrame.from_records(records, columns=FEATURE_COLUMNS)
    if result.empty:
        return result

    result["_missing_values"] = result.isna().sum(axis=1)
    result = result.sort_values(
        ["IDRSSD", "_missing_values"], kind="mergesort"
    ).drop_duplicates("IDRSSD", keep="first")
    return result.drop(columns="_missing_values")


def process_file(input_path, output_path):
    input_path = Path(input_path)
    output_path = Path(output_path)
    frame = pd.read_csv(input_path, low_memory=False)
    result = process_dataframe(frame)
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
