"""Domain functions for FFIEC Call Report schedules.

The classes in this module operate on one already-loaded report row.  They do
not read files, create directories, or run pipeline stages when imported.
"""

import math


def safe_divide(numerator, denominator):
    """Return zero for a true zero denominator and otherwise preserve NaNs."""

    if denominator == 0:
        return 0.0
    return numerator / denominator


class MaturityBuckets:
    """Six Schedule RC-B memorandum maturity buckets."""

    def __init__(self, row, prefix, first_code):
        self.row = row
        self.prefix = prefix
        self.first_code = first_code

    def _value(self, offset):
        return self.row[f"{self.prefix}{self.first_code + offset}"]

    def ThreeMonths(self, name=False):
        return self._value(0)

    def TwelveMonths(self, name=False):
        return self._value(1)

    def ThreeYears(self, name=False):
        return self._value(2)

    def FiveYears(self, name=False):
        return self._value(3)

    def FifteenYears(self, name=False):
        return self._value(4)

    def OverFifteenYears(self, name=False):
        return self._value(5)

    def Values(self):
        return (
            self.ThreeMonths(),
            self.TwelveMonths(),
            self.ThreeYears(),
            self.FiveYears(),
            self.FifteenYears(),
            self.OverFifteenYears(),
        )

    def Total(self, name=False):
        return sum(self.Values())


class SecuritiesMaturities:
    """Schedule RC-B memorandum items M.2.a and M.2.b."""

    def __init__(self, row, prefix):
        self.Government = MaturityBuckets(row, prefix, 549)
        self.ResidentialMortgage = MaturityBuckets(row, prefix, 555)

    def Values(self):
        return self.Government.Values() + self.ResidentialMortgage.Values()


class RegulatoryCapital:
    """Schedule RC-R capital and zero-risk-weight calculations."""

    def __init__(self, row, report_prefix, capital_prefix, maturities):
        self.row = row
        self.report_prefix = report_prefix
        self.capital_prefix = capital_prefix
        self.maturities = maturities

    def _report(self, code):
        return self.row[f"{self.report_prefix}{code}"]

    def _capital(self, code):
        return self.row[f"{self.capital_prefix}{code}"]

    def RiskWeightedAssets(self):
        return self._capital("A223")

    def TierOneCapital(self):
        return self._capital("P840")

    def CommonEquityTierOneCapital(self):
        return self._capital("P859")

    def AugmentedRiskWeightedAssets(self):
        values = self.maturities.Values()
        return self.RiskWeightedAssets() + (
            0.15 * values[5]
            + 0.10 * values[4]
            + 0.08 * values[3]
            + 0.15 * values[11]
            + 0.10 * values[10]
            + 0.08 * values[9]
        )

    def ZeroRiskWeightedAssets(self):
        if self.row["RCON9999"] >= 20150331:
            return self.row["RCOND987"]
        return self._report("B696")

    def ZeroRiskWeightExposureRatio(self):
        domestic_securities = self.row["RCON1754"] + self.row["RCON1773"]
        if self.row["RCON9999"] >= 20150331:
            denominator = domestic_securities
            if denominator == 0 and self.report_prefix == "RCFD":
                denominator = self._report("1754") + self._report("1773")
            return safe_divide(
                self.row["RCOND962"] + self.row["RCOND967"], denominator
            )
        return safe_divide(
            self.row["RCONB603"] + self.row["RCONB608"], domestic_securities
        )

    def RiskWeightAdjustment(self):
        values = self.maturities.Values()
        return values[5] + values[4] + values[11] + values[10]

    def AdjustedZeroRiskWeightedAssets(self):
        if self.row["RCON9999"] < 20150331:
            return self.ZeroRiskWeightedAssets()
        return self.ZeroRiskWeightedAssets() - (
            self.ZeroRiskWeightExposureRatio() * self.RiskWeightAdjustment()
        )

    def ZeroRiskToReportedRWA(self):
        return safe_divide(self.ZeroRiskWeightedAssets(), self.RiskWeightedAssets())

    def ZeroRiskToAugmentedRWA(self):
        denominator = (
            self.AugmentedRiskWeightedAssets()
            if self.row["RCON9999"] >= 20150331
            else self.RiskWeightedAssets()
        )
        return safe_divide(self.ZeroRiskWeightedAssets(), denominator)

    def AdjustedZeroRiskToAugmentedRWA(self):
        denominator = (
            self.AugmentedRiskWeightedAssets()
            if self.row["RCON9999"] >= 20150331
            else self.RiskWeightedAssets()
        )
        return safe_divide(self.AdjustedZeroRiskWeightedAssets(), denominator)

    def RelativeZeroRiskAdjustment(self):
        baseline = self.ZeroRiskToAugmentedRWA()
        if baseline == 0:
            return 0.0
        return 1.0 - safe_divide(self.AdjustedZeroRiskToAugmentedRWA(), baseline)

class CallReport_051:
    def __init__(self, row):
        self.root = self
        self.row = row
        self.Maturities = SecuritiesMaturities(row, "RCONA")
        self.RegulatoryCapital = RegulatoryCapital(
            row, "RCON", "RCOA", self.Maturities
        )
        self.BalanceSheet = self.BalanceSheet(self)
        self.Securities = self.Securities(self)
        self.DepositLiabilities = self.DepositLiabilities(self)
        self.LoansAndLeases = self.LoansAndLeases(self)

    def _zero(self, v):
        if v is None:
            return 0
        if isinstance(v, float) and math.isnan(v):
            return 0
        if v == '':
            return 0
        return v

    def _div(self, num, den):
        num = self._zero(num)
        den = self._zero(den)

        if den == 0:
            return 0
        return num / den

    def RSSDID(self):
        return self.row['IDRSSD']

    def ReportingDate(self):
        return self.row['RCON9999']

    def Certificate(self):
        return self.row['FDIC Certificate Number']

    def Value(self, column):
        return self.row[column]

    class BalanceSheet:
        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.DepositDomesticOffices = self.DepositDomesticOffices(self)
            self.LoansAndLeaseFinancingReceivables = self.LoansAndLeaseFinancingReceivables(self)

        def CashAndBalancesDue(self):
            return self.row['RCON0081'] + self.row['RCON0071']

        def TotalSecurities(self):
            if self.root.ReportingDate() >= 20190331:
                return self.row['RCONJJ34'] + self.row['RCON1773'] + self.row['RCONJA22']
            else:
                return self.row['RCON1754'] + self.row['RCON1773']

        def HTMSecurities(self):
            if self.root.ReportingDate() >= 20190331:
                return self.row['RCONJJ34']
            else:
                return self.row['RCON1754']

        def AFSSecurities(self):
            return self.row['RCON1773']

        class LoansAndLeaseFinancingReceivables:
            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

                self.name = "Loans and Leases held for Investment, Net of Allowance (Schedule RC)"
                self.flags = {}
                self.messages = {}

            def Total(self, validate=False):
                total = self.row['RCONB529']
                if not validate:
                    return total
                comp = (
                    self.LoansAndLeasesHeldForSale()
                    + self.LoansAndLeasesHeldForInvestment()
                    - self.AllowanceForCreditLossesOnLoansAndLeases()
                )
                difference = total - comp

                self.flags["Total"] = False
                self.messages["Total"] = None
                self.name = "Loans and Leases held for Investment, Net of Allowance (Schedule RC)"

                if total != comp:
                    self.flags["Total"] = True
                    self.messages["Total"] = (
                        f"{total} does not equal {comp} by {difference} "
                        f"in {self.name} for IDRSSD {self.root.RSSDID()} "
                        f"on {self.root.ReportingDate()}"
                    )
                    print(self.messages["Total"])
                return total

            def LoansAndLeasesHeldForSale(self):
                return self.row['RCON5369']

            def LoansAndLeasesHeldForInvestment(self):
                return self.row['RCONB528']

            def AllowanceForCreditLossesOnLoansAndLeases(self):
                return self.row['RCON3123']

            def TotalIncludingHeldForSale(self):
                return self.LoansAndLeasesHeldForSale() + self.Total()

        def TradingAssets(self):
            return self.row['RCON3545']

        def OtherRealEstateOwned(self):
            return self.row['RCON2150']

        def IntangibleAssets(self):
            if self.root.ReportingDate() >= 20180630:
                return self.row['RCON2143']
            else:
                return self.row['RCON3163'] + self.row['RCON0426']

        def TotalAssets(self):
            if self.root.ReportingDate() >= 20180331:
                return self.row['RCON2170'] - self.row['RCONJA22'] + self.row['RCON3123']
            else:
                return self.row['RCON2170'] + self.row['RCON3123']

        def FederalFundsPurchased(self):
            return self.row['RCONB993'] + self.row['RCONB995']

        def FederalFundsSold(self):
            return self.row['RCONB987'] + self.row['RCONB989']

        class DepositDomesticOffices:
            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def NonInterestBearing(self):
                return self.row['RCON66631']

            def InterestBearing(self):
                return self.row['RCON66636']

            def Total(self, name=False):
                return self.NonInterestBearing() + self.InterestBearing()

        def TradingLiabilities(self):
            return self.row['RCON3548']

        def OtherLiabilities(self):
            return self.row['RCON2930']

        def OtherBorrowedMoney(self):
            return self.row['RCON3190']

        def TotalLiabilities(self):
            return self.row['RCON2948']

        def TotalLiabilitiesIncludingAllowance(self):
            return self.TotalLiabilities() + (
                self.LoansAndLeaseFinancingReceivables.AllowanceForCreditLossesOnLoansAndLeases()
            )

        def ReportedTotalEquityCapital(self):
            return self.row['RCONG105']

        def TotalEquityCapital(self):
            if self.root.ReportingDate() >= 20180331:
                return self.row['RCONG105'] - self.row['RCONJA22']
            else:
                return self.row['RCONG105']

    class Securities:
        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.ResidentialPassThru = self.ResidentialPassThru(self)

        def USTreasuries(self, accounting, valuation):
            if accounting == "htm":
                if valuation == "ac":
                    return self.row['RCON0211']
                elif valuation == "fv":
                    return self.row['RCON0213']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCON1286']
                elif valuation == "fv":
                    return self.row['RCON1287']

        def USGovtObligations(self, accounting, valuation):
            if self.root.ReportingDate() > 20180331:
                if accounting == "htm":
                    if valuation == "ac":
                        return self.row['RCONHT50']
                    elif valuation == "fv":
                        return self.row['RCONHT51']
                elif accounting == "afs":
                    if valuation == "ac":
                        return self.row['RCONHT52']
                    elif valuation == "fv":
                        return self.row['RCONHT53']
            else:
                if accounting == "htm":
                    if valuation == "ac":
                        return self.row['RCON1289'] + self.row['RCON1294']
                    elif valuation == "fv":
                        return self.row['RCON1290'] + self.row['RCON1295']
                elif accounting == "afs":
                    if valuation == "ac":
                        return self.row['RCON1291'] + self.row['RCON1297']
                    elif valuation == "fv":
                        return self.row['RCON1293'] + self.row['RCON1298']

        def StateSecurities(self, accounting, valuation):
            if accounting == "htm":
                if valuation == "ac":
                    return self.row['RCON8496']
                elif valuation == "fv":
                    return self.row['RCON8497']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCON8498']
                elif valuation == "fv":
                    return self.row['RCON8499']

        class ResidentialPassThru:
            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def Total(self, accounting, valuation):
                if accounting == "htm":
                    if valuation == "ac":
                        return (self.parent.GNMAPassThru(accounting="htm", valuation="ac") +
                                self.parent.FNMAPassThru(accounting="htm", valuation="ac") +
                                self.parent.OtherPassThru(accounting="htm", valuation="ac"))
                    elif valuation == "fv":
                        return (self.parent.GNMAPassThru(accounting="htm", valuation="fv") +
                                self.parent.FNMAPassThru(accounting="htm", valuation="fv") +
                                self.parent.OtherPassThru(accounting="htm", valuation="fv"))
                elif accounting == "afs":
                    if valuation == "ac":
                        return (self.parent.GNMAPassThru(accounting="afs", valuation="ac") +
                                self.parent.FNMAPassThru(accounting="afs", valuation="ac") +
                                self.parent.OtherPassThru(accounting="afs", valuation="ac"))
                    elif valuation == "fv":
                        return (self.parent.GNMAPassThru(accounting="afs", valuation="fv") +
                                self.parent.FNMAPassThru(accounting="afs", valuation="fv") +
                                self.parent.OtherPassThru(accounting="afs", valuation="fv"))

            def ThreeMonths(self, name=False):
                return self.row['RCONA555']

            def TwelveMonths(self, name=False):
                return self.row['RCONA556']

            def ThreeYears(self, name=False):
                return self.row['RCONA557']

            def FiveYears(self, name=False):
                return self.row['RCONA558']

            def FifteenYears(self, name=False):
                return self.row['RCONA559']

            def OverFifteenYears(self, name=False):
                return self.row['RCONA560']

        def OtherResidentialPassThru(self, accounting, valuation):
            return (
                self.OtherResidentialGNMA(accounting, valuation)
                + self.OtherResidentialFNMA(accounting, valuation)
                + self.OtherResidentialOther(accounting, valuation)
            )

        def OtherResidentialGNMA(self, accounting, valuation):
            if accounting == "htm":
                if valuation == "ac":
                    return self.row['RCONG312']
                elif valuation == "fv":
                    return self.row['RCONG313']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCONG314']
                elif valuation == "fv":
                    return self.row['RCONG315']

        def OtherResidentialFNMA(self, accounting, valuation):
            suffix = {("htm", "ac"): "G316", ("htm", "fv"): "G317",
                      ("afs", "ac"): "G318", ("afs", "fv"): "G319"}
            return self.row["RCON" + suffix[(accounting, valuation)]]

        def OtherResidentialOther(self, accounting, valuation):
            suffix = {("htm", "ac"): "G320", ("htm", "fv"): "G321",
                      ("afs", "ac"): "G322", ("afs", "fv"): "G323"}
            return self.row["RCON" + suffix[(accounting, valuation)]]

        def CommericalPassThru(self, accounting, valuation):
            if self.root.ReportingDate() > 20110331:
                if accounting == "htm":
                    if valuation == "ac":
                        return self.row['RCONK142'] + self.row['RCONK146']
                    elif valuation == "fv":
                        return self.row['RCONK143'] + self.row['RCONK147']
                elif accounting == "afs":
                    if valuation == "ac":
                        return self.row['RCONK144'] + self.row['RCONK148']
                    elif valuation == "fv":
                        return self.row['RCONK145'] + self.row['RCONK149']
            else:
                if accounting == "htm":
                    if valuation == "ac":
                        return self.row['RCONG324']
                    elif valuation == "fv":
                        return self.row['RCONG325']
                elif accounting == "afs":
                    if valuation == "ac":
                        return self.row['RCONG326']
                    elif valuation == "fv":
                        return self.row['RCONG327']

        def OtherCommericalMBS(self, accounting, valuation):
            if self.root.ReportingDate() > 20110331:
                if accounting == "htm":
                    if valuation == "ac":
                        return self.row['RCONK150'] + self.row['RCONK154']
                    elif valuation == "fv":
                        return self.row['RCONK151'] + self.row['RCONK155']
                elif accounting == "afs":
                    if valuation == "ac":
                        return self.row['RCONK152'] + self.row['RCONK156']
                    elif valuation == "fv":
                        return self.row['RCONK153'] + self.row['RCONK157']
            else:
                if accounting == "htm":
                    if valuation == "ac":
                        return self.row['RCONG328']
                    elif valuation == "fv":
                        return self.row['RCONG329']
                elif accounting == "afs":
                    if valuation == "ac":
                        return self.row['RCONG330']
                    elif valuation == "fv":
                        return self.row['RCONG331']

        def GNMAPassThru(self, accounting, valuation):
            if accounting == "htm":
                if valuation == "ac":
                    return self.row['RCONG300']
                elif valuation == "fv":
                    return self.row['RCONG301']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCONG302']
                elif valuation == "fv":
                    return self.row['RCONG303']

        def FNMAPassThru(self, accounting, valuation):
            if accounting == "htm":
                if valuation == "ac":
                    return self.row['RCONG304']
                elif valuation == "fv":
                    return self.row['RCONG305']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCONG306']
                elif valuation == "fv":
                    return self.row['RCONG307']

        def OtherPassThru(self, accounting, valuation):
            if accounting == "htm":
                if valuation == "ac":
                    return self.row['RCONG308']
                elif valuation == "fv":
                    return self.row['RCONG309']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCONG310']
                elif valuation == "fv":
                    return self.row['RCONG311']

        def MBSTotal(self, accounting, valuation, name=False):
            if accounting == "htm":
                if valuation == "ac":
                    self.name = "Total Mortgage-backed Securities Held-to-Maturity at Amortized Cost (Schedule RC-B)"
                    if name:
                        return self.name
                    return (
                        self.ResidentialPassThru.Total(accounting="htm", valuation="ac") +
                        self.OtherResidentialPassThru(accounting="htm", valuation="ac") +
                        self.CommericalPassThru(accounting="htm", valuation="ac") +
                        self.OtherCommericalMBS(accounting="htm", valuation="ac")
                    )

                elif valuation == "fv":
                    if name:
                        return None
                    return (
                        self.ResidentialPassThru.Total(accounting="htm", valuation="fv") +
                        self.OtherResidentialPassThru(accounting="htm", valuation="fv") +
                        self.CommericalPassThru(accounting="htm", valuation="fv") +
                        self.OtherCommericalMBS(accounting="htm", valuation="fv")
                    )

            elif accounting == "afs":
                if valuation == "ac":
                    if name:
                        return None
                    return (
                        self.ResidentialPassThru.Total(accounting="afs", valuation="ac") +
                        self.OtherResidentialPassThru(accounting="afs", valuation="ac") +
                        self.CommericalPassThru(accounting="afs", valuation="ac") +
                        self.OtherCommericalMBS(accounting="afs", valuation="ac")
                    )

                elif valuation == "fv":
                    self.name = "Total Mortgage-backed Securities Available-for-Sale at Fair Value (Schedule RC-B)"
                    if name:
                        return self.name
                    return (
                        self.ResidentialPassThru.Total(accounting="afs", valuation="fv") +
                        self.OtherResidentialPassThru(accounting="afs", valuation="fv") +
                        self.CommericalPassThru(accounting="afs", valuation="fv") +
                        self.OtherCommericalMBS(accounting="afs", valuation="fv")
                    )

        def ABS(self, accounting, valuation, name=False):
            if accounting == "htm":
                if valuation == "ac":
                    self.name = "Asset-backed Securities Held-to-Maturity at Amortized Cost (Schedule RC-B)"
                    if name:
                        return self.name
                    return self.row['RCONC026']
                elif valuation == "fv":
                    return self.row['RCONC988']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCONC989']
                elif valuation == "fv":
                    self.name = "Asset-backed Securities Available-for-Sale at Fair Value (Schedule RC-B)"
                    if name:
                        return self.name
                    return self.row['RCONC027']

        def OtherDebtSecurities(self, accounting, valuation, name=False):
            if accounting == "htm":
                if valuation == "ac":
                    self.name = "Other Debt Securities Held-to-Maturity at Amortized Cost from (Schedule RC-B)"
                    if name:
                        return self.name
                    return self.row['RCON1737'] + self.row['RCON1742']
                elif valuation == "fv":
                    return self.row['RCON1738'] + self.row['RCON1743']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCON1739'] + self.row['RCON1744']
                elif valuation == "fv":
                    self.name = "Other Debt Securities Available-for-Sale at Fair Value from (Schedule RC-B)"
                    if name:
                        return self.name
                    return self.row['RCON1741'] + self.row['RCON1746']

        def Total(self, accounting, valuation, name=False):
            if accounting == "htm":
                if valuation == "ac":
                    total = self.row['RCON1754']
                    self.name = "Total Held-to-Maturity Securities at Amortized Cost"
                    if name:
                        return self.name
                    return total

                    u1 = self.USGovt(accounting="htm",valuation="ac")
                    u2 = self.USTreasuries(accounting="htm",valuation="ac")
                    s = self.StatesAndPolitical(accounting="htm",valuation="ac")
                    m = self.MBSTotal(accounting="htm",valuation="ac")
                    a = self.ABS(accounting="htm",valuation="ac")
                    o = self.OtherDebtSecurities(accounting="htm",valuation="ac")


                    comp = u1 + u2 + s + m + a + o
                    difference = total - comp

                    self.flags["Total"] = False
                    self.messages["Total"] = None
                    self.name = "Total Transaction Deposits"

                    if total != comp:
                        self.flags["TotalSecuritiesHTM"] = True
                        self.messages["TotalSecuritiesHTM"] = (
                            f"{self.name}: {total} does not equal {comp} by {difference} "
                            f"in {self.name}: "
                            f"{self.USGovt(name=True)}={u1}, "
                            f"{self.USTreasuries(name=True)}={u2}, "
                            f"{self.StatesAndPolitical(name=True)}={s}, "
                            f"{self.MBSTotal(name=True)}={m}, "
                            f"{self.ABS(name=True)}={a}, "
                            f"{self.OtherDebtSecurities(name=True)}={o} "
                            f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                        )
                        print(self.messages["TotalSecuritiesHTM"])
                    return total
                elif valuation == "fv":
                    self.name = "Total Held-to-Maturity Securities at Fair Value"
                    if name:
                        return self.name
                    return self.row['RCON1771']
            elif accounting == "afs":
                if valuation == "ac":
                    self.name = "Total Available-for-Sale Securities at Amortized Cost"
                    if name:
                        return self.name
                    return self.row['RCON1772']
                elif valuation == "fv":
                    total = self.row['RCON1773']
                    self.name = "Total Available-for-Sale Securities at Amortized Cost"
                    if name:
                        return self.name
                    return total

                    u1 = self.USGovt(accounting="afs",valuation="fv")
                    u2 = self.USTreasuries(accounting="afs",valuation="fv")
                    s = self.StatesAndPolitical(accounting="afs",valuation="fv")
                    m = self.MBSTotal(accounting="afs",valuation="fv")
                    a = self.ABS(accounting="afs",valuation="fv")
                    o = self.OtherDebtSecurities(accounting="afs",valuation="fv")


                    comp = u1 + u2 + s + m + a + o
                    difference = total - comp

                    self.flags["Total"] = False
                    self.messages["Total"] = None
                    self.name = "Total Transaction Deposits"

                    if total != comp:
                        self.flags["TotalSecuritiesAFS"] = True
                        self.messages["TotalSecuritiesAFS"] = (
                            f"{self.name}: {total} does not equal {comp} by {difference} "
                            f"in {self.name}: "
                            f"{self.USGovt(name=True)}={u1}, "
                            f"{self.USTreasuries(name=True)}={u2}, "
                            f"{self.StatesAndPolitical(name=True)}={s}, "
                            f"{self.MBSTotal(name=True)}={m}, "
                            f"{self.ABS(name=True)}={a}, "
                            f"{self.OtherDebtSecurities(name=True)}={o} "
                            f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                        )
                        print(self.messages["TotalSecuritiesAFS"])
                    return total

    class LoansAndLeases:
        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.ClosedEndFirstLiens = self.ClosedEndFirstLiens(self)
            self.ExcludingClosedEnd = self.ExcludingClosedEnd(self)

            self.name = "Loans and Leases (Schedule RC-C Part I)"
            self.flags = {}
            self.messages = {}

        def Total(self, name=False):
            total = self.row['RCON2122']
            self.name = "Total loans and leases held for investment and held for sale (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def FamilyResidentialConstruction(self, name=False):
            total = self.row['RCONF158']
            self.name = "Loans secured by real estate for 1-4 family residential construction (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def OtherConstruction(self, name=False):
            total = self.row['RCONF159']
            self.name = "Loans secured by real estate for other construction and all land development (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def Farmland(self, name=False):
            total = self.row['RCON1420']
            self.name = "Loans secured by farmland (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def OpenEndSecuredFamily(self, name=False):
            total = self.row['RCON1797']
            self.name = "Loans secured by real estate for revolving, open-end loans secured by 1-4 family residential properties (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        class ExcludingClosedEnd:
            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

                self.name = "All loans and leases excluding closed-end First Liens (Schedule RC-C Part I)"
                self.flags = {}
                self.messages = {}

            def Total(self, name=False):
                total = (self.ThreeMonths()
                    + self.TwelveMonths()
                    + self.ThreeYears()
                    + self.FiveYears()
                    + self.FifteenYears()
                    + self.OverFifteenYears()
                )
                self.name = "Loans secured by real estate for closed-end family residential secured by first liens (Schedule RC-C Part I)"
                if name:
                    return self.name
                return total

            def ThreeMonths(self, name=False):
                self.name = "Closed-end first liens with maturity and repricing data three months or less"
                if name:
                    return self.name
                return self.row['RCONA564']

            def TwelveMonths(self, name=False):
                self.name = "Closed-end first liens with maturity and repricing data over three months through 12 months"
                if name:
                    return self.name
                return self.row['RCONA565']

            def ThreeYears(self, name=False):
                self.name = "Closed-end first liens with maturity and repricing data over one year through three years"
                if name:
                    return self.name
                return self.row['RCONA566']

            def FiveYears(self, name=False):
                self.name = "Closed-end first liens with maturity and repricing data over three years through five years"
                if name:
                    return self.name
                return self.row['RCONA567']

            def FifteenYears(self, name=False):
                self.name = "Closed-end first liens with maturity and repricing data over five years through fifteen years"
                if name:
                    return self.name
                return self.row['RCONA568']

            def OverFifteenYears(self, name=False):
                self.name = "Closed-end first liens with maturity and repricing data over fifteen years"
                if name:
                    return self.name
                return self.row['RCONA569']

        class ClosedEndFirstLiens:
            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

                self.name = "Closed-End First Liens (Schedule RC-C Part I)"
                self.flags = {}
                self.messages = {}

            def Total(self, name=False):
                total = self.row['RCON5367']
                self.name = "Loans secured by real estate for closed-end family residential secured by first liens (Schedule RC-C Part I)"
                if name:
                    return self.name
                return total

            def ThreeMonths(self, name=False):
                self.name = "Closed-end first liens with maturity and repricing data three months or less"
                if name:
                    return self.name
                return self.row['RCONA564']

            def TwelveMonths(self, name=False):
                self.name = "Closed-end first liens with maturity and repricing data over three months through 12 months"
                if name:
                    return self.name
                return self.row['RCONA565']

            def ThreeYears(self, name=False):
                self.name = "Closed-end first liens with maturity and repricing data over one year through three years"
                if name:
                    return self.name
                return self.row['RCONA566']

            def FiveYears(self, name=False):
                self.name = "Closed-end first liens with maturity and repricing data over three years through five years"
                if name:
                    return self.name
                return self.row['RCONA567']

            def FifteenYears(self, name=False):
                self.name = "Closed-end first liens with maturity and repricing data over five years through fifteen years"
                if name:
                    return self.name
                return self.row['RCONA568']

            def OverFifteenYears(self, name=False):
                self.name = "Closed-end first liens with maturity and repricing data over fifteen years"
                if name:
                    return self.name
                return self.row['RCONA569']

        def ClosedEndJuniorLiens(self, name=False):
            total = self.row['RCON5368']
            self.name = "Loans secured by real estate for closed-end family residential secured by junior liens (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def SecuredMultifamily(self, name=False):
            total = self.row['RCON1460']
            self.name = "Loans secured by real estate for multifamily (5 or more) residential properties (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def SecuredNonfarmOwner(self, name=False):
            total = self.row['RCONF160']
            self.name = "Loans secured by real estate for nonfarm nonresidential properties, owner-occupied (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def SecuredNonfarmOther(self, name=False):
            total = self.row['RCONF161']
            self.name = "Loans secured by real estate for nonfarm nonresidential properties, other (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def DepositoryInstitutions(self, name=False):
            total = self.row['RCON1288']
            self.name = "Loans to depository institutions and acceptances of other banks (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def FinanceAgricultural(self, name=False):
            total = self.row['RCON1590']
            self.name = "Loans to finance agricultural production and other loans to farmers (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def CommercialAndIndustrial(self, name=False):
            total = self.row['RCON1766']
            self.name = "Commercial and industrial loans (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def CreditCards(self, name=False):
            total = self.row['RCONB538']
            self.name = "Loans to individuals for credit cards (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def RevolvingCredit(self, name=False):
            total = self.row['RCONB539']
            self.name = "Loans to individuals for revolving credit plans (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def AutomobileLoans(self, name=False):
            total = self.row['RCONK137']
            self.name = "Loans to individuals for automobile loans (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def ConsumerLoans(self, name=False):
            total = self.row['RCONB538']
            self.name = "Other individual consumer laons (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def StatesAndPolitical(self, name=False):
            total = self.row['RCON2107']
            self.name = "Obligations of state and political subdivisions (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def NonDepository(self, name=False):
            total = self.row['RCONJ454']
            self.name = "Loans to nondepository financial institutions (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def NonDepositoryOther(self, name=False):
            total = self.row['RCONJ464']
            self.name = "Loans to nondepository financial institutions and other loans (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

        def UnearnedIncome(self, name=False):
            total = self.row['RCON2123']
            self.name = "Loans to nondepository financial institutions (Schedule RC-C Part I)"
            if name:
                return self.name
            return total

    class DepositLiabilities:
        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.TransactionDeposits = self.TransactionDeposits(self)
            self.NonTransactionDeposits = self.NonTransactionDeposits(self)

            self.name = "Domestic Deposits"
            self.flags = {}
            self.messages = {}

        def ReportedTotal(self):
            return self.row['RCON2200']

        def DomesticDeposits(self, name=False):
            DomesticDeposits = self.root.BalanceSheet.DepositDomesticOffices.Total()
            self.name = "Total Domestic Deposits"
            if name:
                return self.name

            comp = (
                self.TransactionDeposits.Total()
                + self.NonTransactionDeposits.Total()
            )
            difference = DomesticDeposits - comp

            self.flags["DomesticDeposits"] = False
            self.messages["DomesticDeposits"] = None

            if (self.TransactionDeposits.flags.get("Total", False) or
                self.NonTransactionDeposits.flags.get("Total", False)):

                causes = []

                if self.TransactionDeposits.flags.get("Total", False):
                    causes.append(self.TransactionDeposits.messages.get("Total"))

                if self.NonTransactionDeposits.flags.get("Total", False):
                    causes.append(self.NonTransactionDeposits.messages.get("Total"))

                self.flags["DomesticDeposits"] = True
                self.messages["DomesticDeposits"] = (
                    f"{DomesticDeposits} does not equal {comp} by {difference} "
                    f"in {self.name} for IDRSSD {self.root.RSSDID()} "
                    f"on {self.root.ReportingDate()} "
                    f"check {' | '.join(causes)}"
                )
                print(self.messages["DomesticDeposits"])

            elif DomesticDeposits != comp:
                self.flags["DomesticDeposits"] = True
                self.messages["DomesticDeposits"] = (
                    f"{DomesticDeposits} does not equal {comp} by {difference} "
                    f"in {self.name} for IDRSSD {self.root.RSSDID()} "
                    f"on {self.root.ReportingDate()} "
                )
                print(self.messages["DomesticDeposits"])

            return DomesticDeposits

        def Individuals(self, name=False):
            self.name = "Individual Domestic Deposits"
            if name:
                return self.name
            return self.TransactionDeposits.Individuals() + self.NonTransactionDeposits.Individuals()

        def USGovt(self, name=False):
            self.name = "U.S. Government Domestic Deposits"
            if name:
                return self.name
            return self.TransactionDeposits.USGovt() + self.NonTransactionDeposits.USGovt()

        def StatesAndPolitical(self, name=False):
            self.name = "States and Political Subdivisions Domestic Deposits"
            if name:
                return self.name
            return self.TransactionDeposits.StatesAndPolitical() + self.NonTransactionDeposits.StatesAndPolitical()

        def CommercialBanks(self, name=False):
            self.name = "Commercial Banks Domestic Deposits"
            if name:
                return self.name
            return self.TransactionDeposits.CommercialBanks() + self.NonTransactionDeposits.CommercialBanks()

        def ForeignBanks(self, name=False):
            self.name = "Banks in Foreign Countires Domestic Deposits"
            if name:
                return self.name
            return self.TransactionDeposits.ForeignBanks() + self.NonTransactionDeposits.ForeignBanks()

        def ForeignGovt(self, name=False):
            self.name = "Foreign government Domestic Deposits"
            if name:
                return self.name
            return self.TransactionDeposits.ForeignGovt() + self.NonTransactionDeposits.ForeignGovt()

        class TransactionDeposits:
            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

                self.name = "Transaction Deposits Total"
                self.flags = {}
                self.messages = {}

            def Individuals(self, name=False):
                self.name = "Individual Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCONB549']

            def USGovt(self, name=False):
                self.name = "U.S. Government Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCON2202']

            def StatesAndPolitical(self, name=False):
                self.name = "States and Political Subdivisions Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCON2203']

            def CommercialBanks(self, name=False):
                self.name = "Commercial Banks Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCONB551']

            def ForeignBanks(self, name=False):
                self.name = "Banks in Foriegn Countries Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCON2213']

            def ForeignGovt(self, name=False):
                self.name = "Foreign Government Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCON2216']

            def ReportedTotal(self):
                return self.row['RCON2215']

            def Total(self, name=False):
                i = self.Individuals()
                u = self.USGovt()
                s = self.StatesAndPolitical()
                c = self.CommercialBanks()
                f = self.ForeignBanks()
                g = self.ForeignGovt()
                total = self.row['RCON2215']
                if name:
                    return self.name

                comp = i + u + s + c + f + g
                difference = total - comp

                self.flags["Total"] = False
                self.messages["Total"] = None
                self.name = "Total Transaction Deposits"


                if total != comp:
                    self.flags["Total"] = True
                    self.messages["Total"] = (
                        f"{self.name}: {total} does not equal {comp} by {difference} "
                        f"in {self.name}: "
                        f"{self.Individuals(name=True)}={i}, "
                        f"{self.USGovt(name=True)}={u}, "
                        f"{self.StatesAndPolitical(name=True)}={s}, "
                        f"{self.CommercialBanks(name=True)}={c}, "
                        f"{self.ForeignBanks(name=True)}={f}, "
                        f"{self.ForeignGovt(name=True)}={g} "
                        f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                    )
                    print(self.messages["Total"])
                return total

        class NonTransactionDeposits:
            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.TimeDeposits = self.TimeDeposits(self)

                self.name = "Non-Transaction Deposits Total"
                self.flags = {}
                self.messages = {}

            def Individuals(self, name=False):
                self.name = "Individual Non-Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCONB550']

            def ReportedTotal(self):
                return self.row['RCON2385']

            def USGovt(self, name=False):
                self.name = "U.S. Government Non-Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCON2520']

            def StatesAndPolitical(self, name=False):
                self.name = "States and Political Subdivisions Non-Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCON2530']

            def CommercialBanks(self, name=False):
                self.name = "Commercial Banks Non-Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCONB552']

            def ForeignBanks(self, name=False):
                self.name = "Banks in Foriegn Countries Non-Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCON2236']

            def ForeignGovt(self, name=False):
                self.name = "Foreign Government Non-Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCON2237']

            def Total(self, name=False):
                total = self.row['RCON2385']
                if name:
                    return self.name

                i1 = self.Individuals()
                u1 = self.USGovt()
                s1 = self.StatesAndPolitical()
                c1 = self.CommercialBanks()
                f1 = self.ForeignBanks()
                g1 = self.ForeignGovt()

                i2 = self.TimeDeposits.LessThan100k()
                u2 = self.TimeDeposits.LessThan250k.Total()
                s2 = self.TimeDeposits.MoreThan250k.Total()
                c2 = self.SavingsMMDA()
                f2 = self.SavingsOther()

                comp1 = i1 + u1 + s1 + c1 + f1 + g1
                comp2 = i2 + u2 + s2 + c2 + f2
                difference1 = total - comp1
                difference2 = total - comp2

                self.flags["Total"] = False
                self.flags["Memoranda2"] = False
                self.messages["Total"] = None
                self.messages["Memoranda2"] = None
                self.name = "Total Non-Transaction Deposits"

                if total != comp1:
                    self.flags["Total"] = True
                    self.messages["Total"] = (
                        f"{self.Total(name=True)}: {total} does not equal {comp1} by {difference1} "
                        f"in {self.Total(name=True)}: "
                        f"{self.Individuals(name=True)}={i1}, "
                        f"{self.USGovt(name=True)}={u1}, "
                        f"{self.StatesAndPolitical(name=True)}={s1}, "
                        f"{self.CommercialBanks(name=True)}={c1}, "
                        f"{self.ForeignBanks(name=True)}={f1}, "
                        f"{self.ForeignGovt(name=True)}={g1} "
                        f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                    )
                    print(self.messages["Total"])
                if total != comp2:
                    self.flags["Memoranda2"] = True
                    self.messages["Memoranda2"] = (
                        f"{self.name}: {total} does not equal {comp2} by {difference2} "
                        f"in {self.name}: "
                        f"{self.TimeDeposits.LessThan100k(name=True)}={i2}, "
                        f"{self.TimeDeposits.LessThan250k.Total(name=True)}={u2}, "
                        f"{self.TimeDeposits.MoreThan250k.Total(name=True)}={s2}, "
                        f"{self.SavingsMMDA(name=True)}={c2}, "
                        f"{self.SavingsOther(name=True)}={f2}, "
                        f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                    )
                    print(self.messages["Memoranda2"])
                return total

            class TimeDeposits:
                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.LessThan250k = self.LessThan250k(self)
                    self.MoreThan250k = self.MoreThan250k(self)

                    self.name = "Non-Transaction Deposits Total"
                    self.flags = {}
                    self.messages = {}

                def LessThan100k(self, name=False):
                    self.name = "Total Time Deposits of less than $100,000"
                    if name:
                        return self.name
                    return self.row['RCON6648']

                def MoreThan100kLessThan250k(self, name=False):
                    self.name = "Total Time Deposits of $100,000 through $250,000"
                    if name:
                        return self.name
                    return self.row['RCON6648']

                class LessThan250k:
                    def __init__(self, parent):
                        self.parent = parent
                        self.root = parent.root
                        self.row = self.root.row

                        self.flags = {}
                        self.messages = {}

                    def ReportedTotal(self):
                        return self.row['RCONJ473']

                    def EffectiveThreeMonths(self):
                        if self.root.ReportingDate() >= 20170331:
                            return self.ThreeMonths()
                        return self.row['RCONA579']

                    def EffectiveTwelveMonths(self):
                        if self.root.ReportingDate() >= 20170331:
                            return self.TwelveMonths()
                        return self.row['RCONA580']

                    def EffectiveThreeYears(self):
                        if self.root.ReportingDate() >= 20170331:
                            return self.ThreeYears()
                        return self.row['RCONA581']

                    def EffectiveOverThreeYears(self):
                        if self.root.ReportingDate() >= 20170331:
                            return self.OverThreeYears()
                        return self.row['RCONA582']

                    def Total(self, name=False):
                        self.name = "Total Time Deposits of less than $250,000"
                        if name:
                            return self.name
                        total = self.row['RCONJ473']

                        i1 = self.ThreeMonths()
                        u1 = self.TwelveMonths()
                        s1 = self.ThreeYears()
                        c1 = self.OverThreeYears()

                        i2 = self.TimeDeposits.LessThan100k()
                        u2 = self.TimeDeposits.MoreThan100kLessThan250k()

                        comp1 = i1 + u1 + s1 + c1
                        comp2 = i1 + i2
                        difference1 = total - comp1
                        difference2 = total - comp2

                        self.flags["Total"] = False
                        self.flags["Maturity"] = False
                        self.messages["Total"] = None
                        self.messages["Maturity"] = None
                        self.name = "Total Non-Transaction Deposits of Less Than $250,000"

                        if total != comp1:
                            self.flags["Maturity"] = True
                            self.messages["Maturity"] = (
                                f"{self.Total(name=True)}: {total} does not equal {comp1} by {difference1} "
                                f"in {self.Total(name=True)}: "
                                f"{self.ThreeMonths(name=True)}={i1}, "
                                f"{self.TwelveMonths(name=True)}={u1}, "
                                f"{self.ThreeYears(name=True)}={s1}, "
                                f"{self.OverThreeYears(name=True)}={c1}, "
                                f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                            )
                            print(self.messages["Maturity"])
                        if total != comp2:
                            self.flags["Total"] = True
                            self.messages["Total"] = (
                                f"{self.Total(name=True)}: {total} does not equal {comp1} by {difference2} "
                                f"in {self.Total(name=True)}: "
                                f"{self.TimeDeposits.LessThan100k(name=True)}={i2}, "
                                f"{self.TimeDeposits.MoreThan100kLessThan250k(name=True)}={u2}, "
                                f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                            )
                            print(self.messages["Total"])
                        return total

                    def ThreeMonths(self, name=False):
                        self.name = "Total Time Deposits of less than $250,000 with maturity and repricing data three months or less"
                        if name:
                            return self.name
                        return self.row['RCONHK07']

                    def TwelveMonths(self, name=False):
                        self.name = "Total Time Deposits of less than $250,000 with maturity and repricing data over three months through 12 months"
                        if name:
                            return self.name
                        return self.row['RCONHK08']

                    def ThreeYears(self, name=False):
                        self.name = "Total Time Deposits of less than $250,000 with maturity and repricing data over one year through three years"
                        if name:
                            return self.name
                        return self.row['RCONHK09']

                    def OverThreeYears(self, name=False):
                        self.name = "Total Time Deposits of less than $250,000 with maturity and repricing data over three years"
                        if name:
                            return self.name
                        return self.row['RCONHK10']

                class MoreThan250k:
                    def __init__(self, parent):
                        self.parent = parent
                        self.root = parent.root
                        self.row = self.root.row

                        self.flags = {}
                        self.messages = {}

                    def ReportedTotal(self):
                        return self.row['RCONJ474']


                    def Total(self, name=False):
                        self.name = "Total Time Deposits of more than $250,000"
                        if name:
                            return self.name
                        return self.row['RCONJ474']

                    def ThreeMonths(self, name=False):
                        self.name = "Total Time Deposits of more than $250,000 with maturity and repricing data three months or less"
                        if name:
                            return self.name
                        return self.row['RCONHK12']

                    def TwelveMonths(self, name=False):
                        self.name = "Total Time Deposits of more than $250,000 with maturity and repricing data over three months through 12 months"
                        if name:
                            return self.name
                        return self.row['RCONHK13']

                    def ThreeYears(self, name=False):
                        self.name = "Total Time Deposits of more than $250,000 with maturity and repricing data over one year through three years"
                        if name:
                            return self.name
                        return self.row['RCONHK14']

                    def OverThreeYears(self, name=False):
                        self.name = "Total Time Deposits of more than $250,000 with maturity and repricing data over three years"
                        if name:
                            return self.name
                        return self.row['RCONHK15']

            def SavingsMMDA(self, name=False):
                self.name = "Money Market Deposit Accounts (MMDAs)"
                if name:
                    return self.name
                return self.row['RCON6810']

            def SavingsOther(self, name=False):
                self.name = "Other Savings Deposits (excludes MMDAs)"
                if name:
                    return self.name
                return self.row['RCON0352']

            def SavingsTotal(self):
                return self.SavingsMMDA() + self.SavingsOther()

class CallReport_031:
    def __init__(self, row):
        self.root = self
        self.row = row
        self.Maturities = SecuritiesMaturities(row, "RCFDA")
        self.RegulatoryCapital = RegulatoryCapital(
            row, "RCFD", "RCFA", self.Maturities
        )
        self.BalanceSheet = self.BalanceSheet(self)
        self.Securities = self.Securities(self)
        self.DepositLiabilities = self.DepositLiabilities(self)

    def _zero(self, v):
        if v is None:
            return 0
        if isinstance(v, float) and math.isnan(v):
            return 0
        if v == '':
            return 0
        return v

    def _div(self, num, den):
        num = self._zero(num)
        den = self._zero(den)

        if den == 0:
            return 0
        return num / den

    def RSSDID(self):
        return self.row['IDRSSD']

    def ReportingDate(self):
        return self.row['RCON9999']

    def Certificate(self):
        return self.row['FDIC Certificate Number']

    def Value(self, column):
        return self.row[column]

    class BalanceSheet:
        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.DepositDomesticOffices = self.DepositDomesticOffices(self)
            self.LoansAndLeaseFinancingReceivables = self.LoansAndLeaseFinancingReceivables(self)

        def CashAndBalancesDue(self):
            return self.row['RCFD0081'] + self.row['RCFD0071']

        def TotalSecurities(self):
            if self.root.ReportingDate() >= 20190331:
                return self.row['RCFDJJ34'] + self.row['RCFD1773'] + self.row['RCFDJA22']
            else:
                return self.row['RCFD1754'] + self.row['RCFD1773']

        def HTMSecurities(self):
            if self.root.ReportingDate() >= 20190331:
                return self.row['RCFDJJ34']
            else:
                return self.row['RCFD1754']

        def AFSSecurities(self):
            return self.row['RCFD1773']

        class LoansAndLeaseFinancingReceivables:
            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

                self.name = "Loans and Leases held for Investment, Net of Allowance (Schedule RC)"
                self.flags = {}
                self.messages = {}

            def Total(self, validate=False):
                total = self.row['RCFDB529']
                if not validate:
                    return total
                comp = (
                    self.LoansAndLeasesHeldForSale()
                    + self.LoansAndLeasesHeldForInvestment()
                    - self.AllowanceForCreditLossesOnLoansAndLeases()
                )
                difference = total - comp

                self.flags["Total"] = False
                self.messages["Total"] = None
                self.name = "Loans and Leases held for Investment, Net of Allowance (Schedule RC)"

                if total != comp:
                    self.flags["Total"] = True
                    self.messages["Total"] = (
                        f"{total} does not equal {comp} by {difference} "
                        f"in {self.name} for IDRSSD {self.root.RSSDID()} "
                        f"on {self.root.ReportingDate()}"
                    )
                    print(self.messages["Total"])
                return total

            def LoansAndLeasesHeldForSale(self):
                return self.row['RCFD5369']

            def LoansAndLeasesHeldForInvestment(self):
                return self.row['RCFDB528']

            def AllowanceForCreditLossesOnLoansAndLeases(self):
                return self.row['RCFD3123']

            def TotalIncludingHeldForSale(self):
                return self.LoansAndLeasesHeldForSale() + self.Total()

        def TradingAssets(self):
            return self.row['RCFD3545']

        def OtherRealEstateOwned(self):
            return self.row['RCFD2150']

        def IntangibleAssets(self):
            if self.root.ReportingDate() >= 20180630:
                return self.row['RCFD2143']
            else:
                return self.row['RCFD3163'] + self.row['RCFD0426']

        def TotalAssets(self):
            if self.root.ReportingDate() >= 20180331:
                return self.row['RCFD2170'] - self.row['RCFDJA22'] + self.row['RCFD3123']
            else:
                return self.row['RCFD2170'] + self.row['RCFD3123']

        def FederalFundsPurchased(self):
            return self.row['RCONB993'] + self.row['RCFDB995']

        def FederalFundsSold(self):
            return self.row['RCFDB987'] + self.row['RCFDB989']

        class DepositDomesticOffices:
            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def NonInterestBearing(self):
                return self.row['RCFD66631']

            def InterestBearing(self):
                return self.row['RCFD66636']

            def Total(self, name=False):
                return self.NonInterestBearing() + self.InterestBearing()

        def TradingLiabilities(self):
            return self.row['RCFD3548']

        def OtherLiabilities(self):
            return self.row['RCFD2930']

        def OtherBorrowedMoney(self):
            return self.row['RCFD3190']

        def TotalLiabilities(self):
            return self.row['RCFD2948']

        def TotalLiabilitiesIncludingAllowance(self):
            return self.TotalLiabilities() + (
                self.LoansAndLeaseFinancingReceivables.AllowanceForCreditLossesOnLoansAndLeases()
            )

        def ReportedTotalEquityCapital(self):
            return self.row['RCFDG105']

        def TotalEquityCapital(self):
            if self.root.ReportingDate() >= 20180331:
                return self.row['RCFDG105'] - self.row['RCFDJA22']
            else:
                return self.row['RCFDG105']

    class Securities:
        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.ResidentialPassThru = self.ResidentialPassThru(self)

        def USTreasuries(self, accounting, valuation):
            if accounting == "htm":
                if valuation == "ac":
                    return self.row['RCFD0211']
                elif valuation == "fv":
                    return self.row['RCFD0213']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCFD1286']
                elif valuation == "fv":
                    return self.row['RCFD1287']

        def USGovtObligations(self, accounting, valuation):
            if self.root.ReportingDate() > 20180331:
                if accounting == "htm":
                    if valuation == "ac":
                        return self.row['RCFDHT50']
                    elif valuation == "fv":
                        return self.row['RCFDHT51']
                elif accounting == "afs":
                    if valuation == "ac":
                        return self.row['RCFDHT52']
                    elif valuation == "fv":
                        return self.row['RCFDHT53']
            else:
                if accounting == "htm":
                    if valuation == "ac":
                        return self.row['RCFD1289'] + self.row['RCFD1294']
                    elif valuation == "fv":
                        return self.row['RCFD1290'] + self.row['RCFD1295']
                elif accounting == "afs":
                    if valuation == "ac":
                        return self.row['RCFD1291'] + self.row['RCFD1297']
                    elif valuation == "fv":
                        return self.row['RCFD1293'] + self.row['RCFD1298']

        def StateSecurities(self, accounting, valuation):
            if accounting == "htm":
                if valuation == "ac":
                    return self.row['RCFD8496']
                elif valuation == "fv":
                    return self.row['RCFD8497']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCFD8498']
                elif valuation == "fv":
                    return self.row['RCFD8499']

        class ResidentialPassThru:
            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def Total(self, accounting, valuation):
                if accounting == "htm":
                    if valuation == "ac":
                        return (self.parent.GNMAPassThru(accounting="htm", valuation="ac") +
                                self.parent.FNMAPassThru(accounting="htm", valuation="ac") +
                                self.parent.OtherPassThru(accounting="htm", valuation="ac"))
                    elif valuation == "fv":
                        return (self.parent.GNMAPassThru(accounting="htm", valuation="fv") +
                                self.parent.FNMAPassThru(accounting="htm", valuation="fv") +
                                self.parent.OtherPassThru(accounting="htm", valuation="fv"))
                elif accounting == "afs":
                    if valuation == "ac":
                        return (self.parent.GNMAPassThru(accounting="afs", valuation="ac") +
                                self.parent.FNMAPassThru(accounting="afs", valuation="ac") +
                                self.parent.OtherPassThru(accounting="afs", valuation="ac"))
                    elif valuation == "fv":
                        return (self.parent.GNMAPassThru(accounting="afs", valuation="fv") +
                                self.parent.FNMAPassThru(accounting="afs", valuation="fv") +
                                self.parent.OtherPassThru(accounting="afs", valuation="fv"))

            def ThreeMonths(self, name=False):
                return self.row['RCFDA555']

            def TwelveMonths(self, name=False):
                return self.row['RCFDA556']

            def ThreeYears(self, name=False):
                return self.row['RCFDA557']

            def FiveYears(self, name=False):
                return self.row['RCFDA558']

            def FifteenYears(self, name=False):
                return self.row['RCFDA559']

            def OverFifteenYears(self, name=False):
                return self.row['RCFDA560']

        def OtherResidentialPassThru(self, accounting, valuation):
            return (
                self.OtherResidentialGNMA(accounting, valuation)
                + self.OtherResidentialFNMA(accounting, valuation)
                + self.OtherResidentialOther(accounting, valuation)
            )

        def OtherResidentialGNMA(self, accounting, valuation):
            if accounting == "htm":
                if valuation == "ac":
                    return self.row['RCFDG312']
                elif valuation == "fv":
                    return self.row['RCFDG313']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCFDG314']
                elif valuation == "fv":
                    return self.row['RCFDG315']

        def OtherResidentialFNMA(self, accounting, valuation):
            suffix = {("htm", "ac"): "G316", ("htm", "fv"): "G317",
                      ("afs", "ac"): "G318", ("afs", "fv"): "G319"}
            return self.row["RCFD" + suffix[(accounting, valuation)]]

        def OtherResidentialOther(self, accounting, valuation):
            suffix = {("htm", "ac"): "G320", ("htm", "fv"): "G321",
                      ("afs", "ac"): "G322", ("afs", "fv"): "G323"}
            return self.row["RCFD" + suffix[(accounting, valuation)]]

        def CommericalPassThru(self, accounting, valuation):
            if self.root.ReportingDate() > 20110331:
                if accounting == "htm":
                    if valuation == "ac":
                        return self.row['RCFDK142'] + self.row['RCFDK146']
                    elif valuation == "fv":
                        return self.row['RCFDK143'] + self.row['RCFDK147']
                elif accounting == "afs":
                    if valuation == "ac":
                        return self.row['RCFDK144'] + self.row['RCFDK148']
                    elif valuation == "fv":
                        return self.row['RCFDK145'] + self.row['RCFDK149']
            else:
                if accounting == "htm":
                    if valuation == "ac":
                        return self.row['RCFDG324']
                    elif valuation == "fv":
                        return self.row['RCFDG325']
                elif accounting == "afs":
                    if valuation == "ac":
                        return self.row['RCFDG326']
                    elif valuation == "fv":
                        return self.row['RCFDG327']

        def OtherCommericalMBS(self, accounting, valuation):
            if self.root.ReportingDate() > 20110331:
                if accounting == "htm":
                    if valuation == "ac":
                        return self.row['RCFDK150'] + self.row['RCFDK154']
                    elif valuation == "fv":
                        return self.row['RCFDK151'] + self.row['RCFDK155']
                elif accounting == "afs":
                    if valuation == "ac":
                        return self.row['RCFDK152'] + self.row['RCFDK156']
                    elif valuation == "fv":
                        return self.row['RCFDK153'] + self.row['RCFDK157']
            else:
                if accounting == "htm":
                    if valuation == "ac":
                        return self.row['RCFDG328']
                    elif valuation == "fv":
                        return self.row['RCFDG329']
                elif accounting == "afs":
                    if valuation == "ac":
                        return self.row['RCFDG330']
                    elif valuation == "fv":
                        return self.row['RCFDG331']

        def GNMAPassThru(self, accounting, valuation):
            if accounting == "htm":
                if valuation == "ac":
                    return self.row['RCFDG300']
                elif valuation == "fv":
                    return self.row['RCFDG301']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCFDG302']
                elif valuation == "fv":
                    return self.row['RCFDG303']

        def FNMAPassThru(self, accounting, valuation):
            if accounting == "htm":
                if valuation == "ac":
                    return self.row['RCFDG304']
                elif valuation == "fv":
                    return self.row['RCFDG305']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCFDG306']
                elif valuation == "fv":
                    return self.row['RCFDG307']

        def OtherPassThru(self, accounting, valuation):
            if accounting == "htm":
                if valuation == "ac":
                    return self.row['RCFDG308']
                elif valuation == "fv":
                    return self.row['RCFDG309']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCFDG310']
                elif valuation == "fv":
                    return self.row['RCFDG311']

        def MBSTotal(self, accounting, valuation, name=False):
            if accounting == "htm":
                if valuation == "ac":
                    self.name = "Total Mortgage-backed Securities Held-to-Maturity at Amortized Cost (Schedule RC-B)"
                    if name:
                        return self.name
                    return (
                        self.ResidentialPassThru.Total(accounting="htm", valuation="ac") +
                        self.OtherResidentialPassThru(accounting="htm", valuation="ac") +
                        self.CommericalPassThru(accounting="htm", valuation="ac") +
                        self.OtherCommericalMBS(accounting="htm", valuation="ac")
                    )

                elif valuation == "fv":
                    if name:
                        return None
                    return (
                        self.ResidentialPassThru.Total(accounting="htm", valuation="fv") +
                        self.OtherResidentialPassThru(accounting="htm", valuation="fv") +
                        self.CommericalPassThru(accounting="htm", valuation="fv") +
                        self.OtherCommericalMBS(accounting="htm", valuation="fv")
                    )

            elif accounting == "afs":
                if valuation == "ac":
                    if name:
                        return None
                    return (
                        self.ResidentialPassThru.Total(accounting="afs", valuation="ac") +
                        self.OtherResidentialPassThru(accounting="afs", valuation="ac") +
                        self.CommericalPassThru(accounting="afs", valuation="ac") +
                        self.OtherCommericalMBS(accounting="afs", valuation="ac")
                    )

                elif valuation == "fv":
                    self.name = "Total Mortgage-backed Securities Available-for-Sale at Fair Value (Schedule RC-B)"
                    if name:
                        return self.name
                    return (
                        self.ResidentialPassThru.Total(accounting="afs", valuation="fv") +
                        self.OtherResidentialPassThru(accounting="afs", valuation="fv") +
                        self.CommericalPassThru(accounting="afs", valuation="fv") +
                        self.OtherCommericalMBS(accounting="afs", valuation="fv")
                    )

        def ABS(self, accounting, valuation, name=False):
            if accounting == "htm":
                if valuation == "ac":
                    self.name = "Asset-backed Securities Held-to-Maturity at Amortized Cost (Schedule RC-B)"
                    if name:
                        return self.name
                    return self.row['RCFDC026']
                elif valuation == "fv":
                    return self.row['RCFDC988']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCFDC989']
                elif valuation == "fv":
                    self.name = "Asset-backed Securities Available-for-Sale at Fair Value (Schedule RC-B)"
                    if name:
                        return self.name
                    return self.row['RCFDC027']

        def OtherDebtSecurities(self, accounting, valuation, name=False):
            if accounting == "htm":
                if valuation == "ac":
                    self.name = "Other Debt Securities Held-to-Maturity at Amortized Cost from (Schedule RC-B)"
                    if name:
                        return self.name
                    return self.row['RCFD1737'] + self.row['RCFD1742']
                elif valuation == "fv":
                    return self.row['RCFD1738'] + self.row['RCFD1743']
            elif accounting == "afs":
                if valuation == "ac":
                    return self.row['RCFD1739'] + self.row['RCFD1744']
                elif valuation == "fv":
                    self.name = "Other Debt Securities Available-for-Sale at Fair Value from (Schedule RC-B)"
                    if name:
                        return self.name
                    return self.row['RCFD1741'] + self.row['RCFD1746']

        def Total(self, accounting, valuation, name=False):
            if accounting == "htm":
                if valuation == "ac":
                    total = self.row['RCFD1754']
                    self.name = "Total Held-to-Maturity Securities at Amortized Cost"
                    if name:
                        return self.name
                    return total

                    u1 = self.USGovt(accounting="htm",valuation="ac")
                    u2 = self.USTreasuries(accounting="htm",valuation="ac")
                    s = self.StatesAndPolitical(accounting="htm",valuation="ac")
                    m = self.MBSTotal(accounting="htm",valuation="ac")
                    a = self.ABS(accounting="htm",valuation="ac")
                    o = self.OtherDebtSecurities(accounting="htm",valuation="ac")


                    comp = u1 + u2 + s + m + a + o
                    difference = total - comp

                    self.flags["Total"] = False
                    self.messages["Total"] = None
                    self.name = "Total Transaction Deposits"

                    if total != comp:
                        self.flags["TotalSecuritiesHTM"] = True
                        self.messages["TotalSecuritiesHTM"] = (
                            f"{self.name}: {total} does not equal {comp} by {difference} "
                            f"in {self.name}: "
                            f"{self.USGovt(name=True)}={u1}, "
                            f"{self.USTreasuries(name=True)}={u2}, "
                            f"{self.StatesAndPolitical(name=True)}={s}, "
                            f"{self.MBSTotal(name=True)}={m}, "
                            f"{self.ABS(name=True)}={a}, "
                            f"{self.OtherDebtSecurities(name=True)}={o} "
                            f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                        )
                        print(self.messages["TotalSecuritiesHTM"])
                    return total
                elif valuation == "fv":
                    self.name = "Total Held-to-Maturity Securities at Fair Value"
                    if name:
                        return self.name
                    return self.row['RCFD1771']
            elif accounting == "afs":
                if valuation == "ac":
                    self.name = "Total Available-for-Sale Securities at Amortized Cost"
                    if name:
                        return self.name
                    return self.row['RCFD1772']
                elif valuation == "fv":
                    total = self.row['RCFD1773']
                    self.name = "Total Available-for-Sale Securities at Amortized Cost"
                    if name:
                        return self.name
                    return total

                    u1 = self.USGovt(accounting="afs",valuation="fv")
                    u2 = self.USTreasuries(accounting="afs",valuation="fv")
                    s = self.StatesAndPolitical(accounting="afs",valuation="fv")
                    m = self.MBSTotal(accounting="afs",valuation="fv")
                    a = self.ABS(accounting="afs",valuation="fv")
                    o = self.OtherDebtSecurities(accounting="afs",valuation="fv")


                    comp = u1 + u2 + s + m + a + o
                    difference = total - comp

                    self.flags["Total"] = False
                    self.messages["Total"] = None
                    self.name = "Total Transaction Deposits"

                    if total != comp:
                        self.flags["TotalSecuritiesAFS"] = True
                        self.messages["TotalSecuritiesAFS"] = (
                            f"{self.name}: {total} does not equal {comp} by {difference} "
                            f"in {self.name}: "
                            f"{self.USGovt(name=True)}={u1}, "
                            f"{self.USTreasuries(name=True)}={u2}, "
                            f"{self.StatesAndPolitical(name=True)}={s}, "
                            f"{self.MBSTotal(name=True)}={m}, "
                            f"{self.ABS(name=True)}={a}, "
                            f"{self.OtherDebtSecurities(name=True)}={o} "
                            f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                        )
                        print(self.messages["TotalSecuritiesAFS"])
                    return total

    class DepositLiabilities:
        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.TransactionDeposits = self.TransactionDeposits(self)
            self.NonTransactionDeposits = self.NonTransactionDeposits(self)

            self.name = "Domestic Deposits"
            self.flags = {}
            self.messages = {}

        def ReportedTotal(self):
            return self.row['RCON2200']

        def DomesticDeposits(self, name=False):
            DomesticDeposits = self.root.BalanceSheet.DepositDomesticOffices.Total()
            self.name = "Total Domestic Deposits"
            if name:
                return self.name

            comp = (
                self.TransactionDeposits.Total()
                + self.NonTransactionDeposits.Total()
            )
            difference = DomesticDeposits - comp

            self.flags["DomesticDeposits"] = False
            self.messages["DomesticDeposits"] = None

            if (self.TransactionDeposits.flags.get("Total", False) or
                self.NonTransactionDeposits.flags.get("Total", False)):

                causes = []

                if self.TransactionDeposits.flags.get("Total", False):
                    causes.append(self.TransactionDeposits.messages.get("Total"))

                if self.NonTransactionDeposits.flags.get("Total", False):
                    causes.append(self.NonTransactionDeposits.messages.get("Total"))

                self.flags["DomesticDeposits"] = True
                self.messages["DomesticDeposits"] = (
                    f"{DomesticDeposits} does not equal {comp} by {difference} "
                    f"in {self.name} for IDRSSD {self.root.RSSDID()} "
                    f"on {self.root.ReportingDate()} "
                    f"check {' | '.join(causes)}"
                )
                print(self.messages["DomesticDeposits"])

            elif DomesticDeposits != comp:
                self.flags["DomesticDeposits"] = True
                self.messages["DomesticDeposits"] = (
                    f"{DomesticDeposits} does not equal {comp} by {difference} "
                    f"in {self.name} for IDRSSD {self.root.RSSDID()} "
                    f"on {self.root.ReportingDate()} "
                )
                print(self.messages["DomesticDeposits"])

            return DomesticDeposits

        def Individuals(self, name=False):
            self.name = "Individual Domestic Deposits"
            if name:
                return self.name
            return self.TransactionDeposits.Individuals() + self.NonTransactionDeposits.Individuals()

        def USGovt(self, name=False):
            self.name = "U.S. Government Domestic Deposits"
            if name:
                return self.name
            return self.TransactionDeposits.USGovt() + self.NonTransactionDeposits.USGovt()

        def StatesAndPolitical(self, name=False):
            self.name = "States and Political Subdivisions Domestic Deposits"
            if name:
                return self.name
            return self.TransactionDeposits.StatesAndPolitical() + self.NonTransactionDeposits.StatesAndPolitical()

        def CommercialBanks(self, name=False):
            self.name = "Commercial Banks Domestic Deposits"
            if name:
                return self.name
            return self.TransactionDeposits.CommercialBanks() + self.NonTransactionDeposits.CommercialBanks()

        def ForeignBanks(self, name=False):
            self.name = "Banks in Foreign Countires Domestic Deposits"
            if name:
                return self.name
            return self.TransactionDeposits.ForeignBanks() + self.NonTransactionDeposits.ForeignBanks()

        def ForeignGovt(self, name=False):
            self.name = "Foreign government Domestic Deposits"
            if name:
                return self.name
            return self.TransactionDeposits.ForeignGovt() + self.NonTransactionDeposits.ForeignGovt()

        class TransactionDeposits:
            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

                self.name = "Transaction Deposits Total"
                self.flags = {}
                self.messages = {}

            def Individuals(self, name=False):
                self.name = "Individual Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCFDB549']

            def USGovt(self, name=False):
                self.name = "U.S. Government Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCFD2202']

            def StatesAndPolitical(self, name=False):
                self.name = "States and Political Subdivisions Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCFD2203']

            def CommercialBanks(self, name=False):
                self.name = "Commercial Banks Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCFDB551']

            def ForeignBanks(self, name=False):
                self.name = "Banks in Foriegn Countries Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCFD2213']

            def ForeignGovt(self, name=False):
                self.name = "Foreign Government Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCFD2216']

            def Total(self, name=False):
                i = self.Individuals()
                u = self.USGovt()
                s = self.StatesAndPolitical()
                c = self.CommercialBanks()
                f = self.ForeignBanks()
                g = self.ForeignGovt()
                total = self.row['RCFD2215']
                if name:
                    return self.name

                comp = i + u + s + c + f + g
                difference = total - comp

                self.flags["Total"] = False
                self.messages["Total"] = None
                self.name = "Total Transaction Deposits"


                if total != comp:
                    self.flags["Total"] = True
                    self.messages["Total"] = (
                        f"{self.name}: {total} does not equal {comp} by {difference} "
                        f"in {self.name}: "
                        f"{self.Individuals(name=True)}={i}, "
                        f"{self.USGovt(name=True)}={u}, "
                        f"{self.StatesAndPolitical(name=True)}={s}, "
                        f"{self.CommercialBanks(name=True)}={c}, "
                        f"{self.ForeignBanks(name=True)}={f}, "
                        f"{self.ForeignGovt(name=True)}={g} "
                        f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                    )
                    print(self.messages["Total"])
                return total

        class NonTransactionDeposits:
            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.TimeDeposits = self.TimeDeposits(self)

                self.name = "Non-Transaction Deposits Total"
                self.flags = {}
                self.messages = {}

            def Individuals(self, name=False):
                self.name = "Individual Non-Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCFDB550']

            def USGovt(self, name=False):
                self.name = "U.S. Government Non-Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCFD2520']

            def StatesAndPolitical(self, name=False):
                self.name = "States and Political Subdivisions Non-Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCFD2530']

            def CommercialBanks(self, name=False):
                self.name = "Commercial Banks Non-Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCFDB552']

            def ForeignBanks(self, name=False):
                self.name = "Banks in Foriegn Countries Non-Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCFD2236']

            def ForeignGovt(self, name=False):
                self.name = "Foreign Government Non-Transaction Deposits"
                if name:
                    return self.name
                return self.row['RCFD2237']

            def Total(self, name=False):
                total = self.row['RCFD2385']
                if name:
                    return self.name

                i1 = self.Individuals()
                u1 = self.USGovt()
                s1 = self.StatesAndPolitical()
                c1 = self.CommercialBanks()
                f1 = self.ForeignBanks()
                g1 = self.ForeignGovt()

                i2 = self.TimeDeposits.LessThan100k()
                u2 = self.TimeDeposits.LessThan250k.Total()
                s2 = self.TimeDeposits.MoreThan250k.Total()
                c2 = self.SavingsMMDA()
                f2 = self.SavingsOther()

                comp1 = i1 + u1 + s1 + c1 + f1 + g1
                comp2 = i2 + u2 + s2 + c2 + f2
                difference1 = total - comp1
                difference2 = total - comp2

                self.flags["Total"] = False
                self.flags["Memoranda2"] = False
                self.messages["Total"] = None
                self.messages["Memoranda2"] = None
                self.name = "Total Non-Transaction Deposits"

                if total != comp1:
                    self.flags["Total"] = True
                    self.messages["Total"] = (
                        f"{self.Total(name=True)}: {total} does not equal {comp1} by {difference1} "
                        f"in {self.Total(name=True)}: "
                        f"{self.Individuals(name=True)}={i1}, "
                        f"{self.USGovt(name=True)}={u1}, "
                        f"{self.StatesAndPolitical(name=True)}={s1}, "
                        f"{self.CommercialBanks(name=True)}={c1}, "
                        f"{self.ForeignBanks(name=True)}={f1}, "
                        f"{self.ForeignGovt(name=True)}={g1} "
                        f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                    )
                    print(self.messages["Total"])
                if total != comp2:
                    self.flags["Memoranda2"] = True
                    self.messages["Memoranda2"] = (
                        f"{self.name}: {total} does not equal {comp2} by {difference2} "
                        f"in {self.name}: "
                        f"{self.TimeDeposits.LessThan100k(name=True)}={i2}, "
                        f"{self.TimeDeposits.LessThan250k.Total(name=True)}={u2}, "
                        f"{self.TimeDeposits.MoreThan250k.Total(name=True)}={s2}, "
                        f"{self.SavingsMMDA(name=True)}={c2}, "
                        f"{self.SavingsOther(name=True)}={f2}, "
                        f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                    )
                    print(self.messages["Memoranda2"])
                return total

            class TimeDeposits:
                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.LessThan250k = self.LessThan250k(self)
                    self.MoreThan250k = self.MoreThan250k(self)

                    self.name = "Non-Transaction Deposits Total"
                    self.flags = {}
                    self.messages = {}

                def LessThan100k(self, name=False):
                    self.name = "Total Time Deposits of less than $100,000"
                    if name:
                        return self.name
                    return self.row['RCFD6648']

                def MoreThan100kLessThan250k(self, name=False):
                    self.name = "Total Time Deposits of $100,000 through $250,000"
                    if name:
                        return self.name
                    return self.row['RCFD6648']

                class LessThan250k:
                    def __init__(self, parent):
                        self.parent = parent
                        self.root = parent.root
                        self.row = self.root.row

                        self.flags = {}
                        self.messages = {}

                    def Total(self, name=False):
                        self.name = "Total Time Deposits of less than $250,000"
                        if name:
                            return self.name
                        total = self.row['RCFDJ473']

                        i1 = self.ThreeMonths()
                        u1 = self.TwelveMonths()
                        s1 = self.ThreeYears()
                        c1 = self.OverThreeYears()

                        i2 = self.TimeDeposits.LessThan100k()
                        u2 = self.TimeDeposits.MoreThan100kLessThan250k()

                        comp1 = i1 + u1 + s1 + c1
                        comp2 = i1 + i2
                        difference1 = total - comp1
                        difference2 = total - comp2

                        self.flags["Total"] = False
                        self.flags["Maturity"] = False
                        self.messages["Total"] = None
                        self.messages["Maturity"] = None
                        self.name = "Total Non-Transaction Deposits of Less Than $250,000"

                        if total != comp1:
                            self.flags["Maturity"] = True
                            self.messages["Maturity"] = (
                                f"{self.Total(name=True)}: {total} does not equal {comp1} by {difference1} "
                                f"in {self.Total(name=True)}: "
                                f"{self.ThreeMonths(name=True)}={i1}, "
                                f"{self.TwelveMonths(name=True)}={u1}, "
                                f"{self.ThreeYears(name=True)}={s1}, "
                                f"{self.OverThreeYears(name=True)}={c1}, "
                                f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                            )
                            print(self.messages["Maturity"])
                        if total != comp2:
                            self.flags["Total"] = True
                            self.messages["Total"] = (
                                f"{self.Total(name=True)}: {total} does not equal {comp1} by {difference2} "
                                f"in {self.Total(name=True)}: "
                                f"{self.TimeDeposits.LessThan100k(name=True)}={i2}, "
                                f"{self.TimeDeposits.MoreThan100kLessThan250k(name=True)}={u2}, "
                                f"on {self.root.ReportingDate()} for {self.root.RSSDID()}"
                            )
                            print(self.messages["Total"])
                        return total

                    def ThreeMonths(self, name=False):
                        self.name = "Total Time Deposits of less than $250,000 with maturity and repricing data three months or less"
                        if name:
                            return self.name
                        return self.row['RCFDHK07']

                    def TwelveMonths(self, name=False):
                        self.name = "Total Time Deposits of less than $250,000 with maturity and repricing data over three months through 12 months"
                        if name:
                            return self.name
                        return self.row['RCFDHK08']

                    def ThreeYears(self, name=False):
                        self.name = "Total Time Deposits of less than $250,000 with maturity and repricing data over one year through three years"
                        if name:
                            return self.name
                        return self.row['RCFDHK09']

                    def OverThreeYears(self, name=False):
                        self.name = "Total Time Deposits of less than $250,000 with maturity and repricing data over three years"
                        if name:
                            return self.name
                        return self.row['RCFDHK10']

                class MoreThan250k:
                    def __init__(self, parent):
                        self.parent = parent
                        self.root = parent.root
                        self.row = self.root.row

                        self.flags = {}
                        self.messages = {}

                    def Total(self, name=False):
                        self.name = "Total Time Deposits of more than $250,000"
                        if name:
                            return self.name
                        return self.row['RCFDJ474']

                    def ThreeMonths(self, name=False):
                        self.name = "Total Time Deposits of more than $250,000 with maturity and repricing data three months or less"
                        if name:
                            return self.name
                        return self.row['RCFDHK12']

                    def TwelveMonths(self, name=False):
                        self.name = "Total Time Deposits of more than $250,000 with maturity and repricing data over three months through 12 months"
                        if name:
                            return self.name
                        return self.row['RCFDHK13']

                    def ThreeYears(self, name=False):
                        self.name = "Total Time Deposits of more than $250,000 with maturity and repricing data over one year through three years"
                        if name:
                            return self.name
                        return self.row['RCFDHK14']

                    def OverThreeYears(self, name=False):
                        self.name = "Total Time Deposits of more than $250,000 with maturity and repricing data over three years"
                        if name:
                            return self.name
                        return self.row['RCFDHK15']

            def SavingsMMDA(self, name=False):
                self.name = "Money Market Deposit Accounts (MMDAs)"
                if name:
                    return self.name
                return self.row['RCFD66810']

            def SavingsOther(self, name=False):
                self.name = "Other Savings Deposits (excludes MMDAs)"
                if name:
                    return self.name
                return self.row['RCFD0352']
