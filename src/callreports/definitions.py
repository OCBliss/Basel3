"""Explicit, date-aware FFIEC Call Report schedule functions."""
import math
import calendar
from datetime import date as calendar_date
from pathlib import Path
import pandas as pd
try:
    from collections.abc import Mapping
except ImportError:
    from collections import Mapping

def safe_divide(numerator, denominator):
    try:
        if pd.isna(numerator) or pd.isna(denominator):
            return float('nan')
    except (TypeError, ValueError):
        return float('nan')
    if denominator == 0:
        return 0.0
    return numerator / denominator
_PERIODS = ('P0', 'P1Q', 'P2Q', 'P3Q', 'P1Y')
_IDENTITY_COLUMNS = ('IDRSSD', 'RCON9999', 'FDIC Certificate Number')

def _safe_int(value):
    try:
        number = pd.to_numeric(value, errors='coerce')
        if pd.isna(number):
            return None
        return int(number)
    except (TypeError, ValueError, OverflowError):
        return None

def _row_value(row, column):
    getter = getattr(row, 'get', None)
    if getter is not None:
        return getter(column)
    try:
        return row[column]
    except (KeyError, IndexError, TypeError):
        return None

def _row_columns(row):
    for attribute in ('index', 'keys', 'columns'):
        value = getattr(row, attribute, None)
        if value is None:
            continue
        try:
            return list(value() if callable(value) else value)
        except TypeError:
            continue
    return []

class QuarterCache:

    """Resolve reporting quarters and read explicitly supplied bank histories.

    Without a quarter map, calendar quarter ends supply the lag dates. Historical
    rows come from ``frames`` or ``data_dir``; no Basel3 checkout is required.
    """

    def __init__(self, map_file=None, data_dir=None, frames=None):
        if isinstance(map_file, pd.DataFrame):
            self.map_file = map_file
        elif map_file is not None:
            self.map_file = Path(map_file)
        else:
            self.map_file = None
        self.data_dir = Path(data_dir) if data_dir is not None else None
        self._use_disk = data_dir is not None
        self._source = frames
        self._source_frames = {}
        self._sources_loaded = False
        self._frames = {}
        self._map = None
        self._quarters = None

    def _load_map(self):
        if self._map is not None:
            return
        if isinstance(self.map_file, pd.DataFrame):
            table = self.map_file.copy()
        else:
            table = pd.read_csv(str(self.map_file))
        table.columns = [str(column).lstrip('\ufeff') for column in table.columns]
        if 'P0' not in table.columns:
            raise ValueError('Quarter map must contain P0')
        for column in table.columns:
            table[column] = pd.to_numeric(table[column], errors='coerce')
        self._map = {}
        self._quarters = {}
        for (_, source) in table.iterrows():
            anchor = _safe_int(source.get('P0'))
            if anchor is None:
                continue
            self._map[anchor] = {label: _safe_int(source.get(label)) for label in _PERIODS[1:]}
            self._quarters[anchor] = _safe_int(source.get('Quarter'))

    def resolve(self, anchor, date='P0'):
        if isinstance(date, _ActualDate):
            return date.value
        if date not in _PERIODS:
            raise ValueError('date must be one of {0}'.format(_PERIODS))
        anchor = _safe_int(anchor)
        if date == 'P0':
            return anchor
        if anchor is None:
            return None
        if self.map_file is None:
            current = self._calendar_quarter(anchor)
            if current is None:
                return None
            lag = {'P1Q': 1, 'P2Q': 2, 'P3Q': 3, 'P1Y': 4}[date]
            absolute_month = current.year * 12 + current.month - 1 - 3 * lag
            year, month = divmod(absolute_month, 12)
            month += 1
            if year < 1:
                return None
            return year * 10000 + month * 100 + calendar.monthrange(year, month)[1]
        self._load_map()
        return self._map.get(anchor, {}).get(date)

    @staticmethod
    def _calendar_quarter(actual):
        try:
            current = calendar_date(int(actual) // 10000, int(actual) // 100 % 100, int(actual) % 100)
        except (TypeError, ValueError, OverflowError):
            return None
        if current.month not in (3, 6, 9, 12) or current.day != calendar.monthrange(current.year, current.month)[1]:
            return None
        return current

    def previous(self, actual, quarters=1):
        current = _safe_int(actual)
        for _ in range(quarters):
            if current is None:
                return None
            current = self.resolve(current, 'P1Q')
        return current

    def quarter(self, actual):
        actual = _safe_int(actual)
        if actual is None:
            return None
        if self.map_file is None:
            current = self._calendar_quarter(actual)
            return current.month // 3 if current is not None else None
        self._load_map()
        quarter = self._quarters.get(actual)
        if quarter in (1, 2, 3, 4):
            return quarter
        return {331: 1, 630: 2, 930: 3, 1231: 4}.get(actual % 10000)

    def _load_sources(self):
        if self._sources_loaded:
            return
        self._sources_loaded = True
        if self._source is None:
            return
        if isinstance(self._source, Mapping):
            for (date, frame) in self._source.items():
                actual = _safe_int(date)
                if actual is not None:
                    self._source_frames[actual] = frame
            return
        if isinstance(self._source, pd.DataFrame):
            dates = pd.to_numeric(self._source['RCON9999'], errors='coerce')
            for date in dates.dropna().unique():
                actual = int(date)
                self._source_frames[actual] = self._source.loc[dates == date]
            return
        for frame in self._source:
            if isinstance(frame, pd.Series):
                actual = _safe_int(frame.get('RCON9999'))
            elif isinstance(frame, pd.DataFrame) and (not frame.empty):
                actual = _safe_int(frame.iloc[0].get('RCON9999'))
            else:
                continue
            if actual is not None:
                self._source_frames[actual] = frame

    @staticmethod
    def _prepare(frame):
        if isinstance(frame, pd.Series):
            frame = frame.to_frame().T
        if not isinstance(frame, pd.DataFrame):
            raise TypeError('Historical frames must be DataFrames')
        data = frame.copy()
        identifiers = pd.to_numeric(data['IDRSSD'] if 'IDRSSD' in data.columns else data.index, errors='coerce')
        keep = pd.notna(identifiers)
        data = data.loc[keep].copy()
        data.index = identifiers[keep].astype('int64')
        data.index.name = 'IDRSSD'
        return data

    def frame(self, actual):
        actual = _safe_int(actual)
        if actual is None:
            return None
        if actual in self._frames:
            return self._frames[actual]
        self._load_sources()
        source = self._source_frames.get(actual)
        if source is None and self._use_disk:
            exact = self.data_dir / 'Cleaned_Call_Report_{0}.csv'.format(actual)
            if exact.is_file():
                source = pd.read_csv(str(exact), low_memory=False)
            else:
                matches = sorted(self.data_dir.rglob('Cleaned_Call_Report_{0}.csv'.format(actual)))
                if not matches:
                    matches = sorted(self.data_dir.glob('*{0}*.csv'.format(actual)))
                if len(matches) > 1:
                    raise ValueError('Ambiguous historical CSVs for {0}'.format(actual))
                if matches:
                    source = pd.read_csv(str(matches[0]), low_memory=False)
        if source is None:
            return None
        frame = self._prepare(source)
        self._frames[actual] = frame
        return frame

    def row(self, actual, rssd):
        frame = self.frame(actual)
        rssd = _safe_int(rssd)
        if frame is None or rssd is None or rssd not in frame.index:
            return None
        row = frame.loc[rssd]
        if isinstance(row, pd.DataFrame):
            raise ValueError('Duplicate IDRSSD {0} on {1}'.format(rssd, actual))
        return row

    def columns(self, actual):
        frame = self.frame(actual)
        return () if frame is None else tuple(frame.columns)

class _ActualDate:

    def __init__(self, value):
        self.value = _safe_int(value)
DEFAULT_HISTORY = QuarterCache()

class LagSupport:

    def _init_lags(self, row, history=None):
        self.root = self
        self.row = row
        self.history = history if history is not None else DEFAULT_HISTORY
        self._anchor_date = _safe_int(_row_value(row, 'RCON9999'))
        self._rssd_id = _safe_int(_row_value(row, 'IDRSSD'))
        self._dated_rows = {}
        if self._anchor_date is not None:
            self._dated_rows[self._anchor_date] = row

    def actual_date(self, date='P0'):
        return self.history.resolve(self._anchor_date, date)

    def get_row(self, date='P0'):
        actual = self.actual_date(date)
        if date == 'P0' or (actual is not None and actual == self._anchor_date):
            return self.row
        if actual in self._dated_rows:
            return self._dated_rows[actual]
        found = self.history.row(actual, self._rssd_id)
        if found is None:
            columns = _row_columns(self.row)
            columns.extend(self.history.columns(actual))
            columns.extend(_IDENTITY_COLUMNS)
            columns = list(dict.fromkeys(columns))
            found = pd.Series(float('nan'), index=columns, dtype='float64')
            if self._rssd_id is not None:
                found['IDRSSD'] = self._rssd_id
            if actual is not None:
                found['RCON9999'] = actual
        else:
            columns = list(dict.fromkeys(_row_columns(self.row) + list(found.index)))
            found = found.reindex(columns)
        self._dated_rows[actual] = found
        return found

class Global_uc:

    def __init__(self, row):
        self.row = row

    def _zero(self, value, *args, **kwargs):
        if isinstance(value, str):
            value = _row_value(self.row, value)
        try:
            if value is None or pd.isna(value) or value in ('', ' '):
                return 0.0
        except (TypeError, ValueError):
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError, OverflowError):
            return 0.0

    def _div(self, numerator, denominator, *args, **kwargs):
        numerator = self._zero(numerator)
        denominator = self._zero(denominator)
        if denominator == 0:
            return 0.0
        return numerator / denominator

    @staticmethod
    def _number(value):
        try:
            if value is None or pd.isna(value) or value in ('', ' '):
                return float('nan')
        except (TypeError, ValueError):
            return float('nan')
        try:
            return float(value)
        except (TypeError, ValueError, OverflowError):
            return float('nan')

    def _historical_divide(self, numerator, denominator):
        numerator = self._number(numerator)
        denominator = self._number(denominator)
        if math.isnan(numerator) or math.isnan(denominator):
            return float('nan')
        if denominator == 0:
            return 0.0
        return numerator / denominator

    @staticmethod
    def _call_root(value):
        owner = getattr(value, '__self__', None)
        return getattr(owner, 'root', None)

    def _value_at(self, value, args, actual, kwargs):
        if callable(value):
            return value(*args, date=_ActualDate(actual), **kwargs)
        return value

    def _change(self, value, quarters, args, date, kwargs):
        root = self._call_root(value)
        if root is None:
            return float('nan')
        actual = root.actual_date(date)
        prior = root.history.previous(actual, quarters)
        current_value = self._number(self._value_at(value, args, actual, kwargs))
        prior_value = self._number(self._value_at(value, args, prior, kwargs))
        if math.isnan(current_value) or math.isnan(prior_value):
            return float('nan')
        return self._historical_divide(current_value - prior_value, prior_value)

    def CHANGE1Q(self, value, *args, date='P0', **kwargs):
        return self._change(value, 1, args, date, kwargs)

    def CHANGE2Q(self, value, *args, date='P0', **kwargs):
        return self._change(value, 2, args, date, kwargs)

    def CHANGE3Q(self, value, *args, date='P0', **kwargs):
        return self._change(value, 3, args, date, kwargs)

    def CHANGE1Y(self, value, *args, date='P0', **kwargs):
        return self._change(value, 4, args, date, kwargs)

    def CAVG04X(self, value, *args, date='P0', **kwargs):
        root = self._call_root(value)
        if root is None:
            return float('nan')
        actual = root.actual_date(date)
        quarter = root.history.quarter(actual)
        if quarter not in (1, 2, 3, 4):
            return float('nan')
        values = [self._number(self._value_at(value, args, root.history.previous(actual, lag), kwargs)) for lag in range(quarter)]
        if any(math.isnan(item) for item in values):
            return float('nan')
        return sum(values) / float(quarter)

    def ANN(self, value, *args, date='P0', **kwargs):
        root = self._call_root(value)
        if root is None:
            return float('nan')
        actual = root.actual_date(date)
        quarter = root.history.quarter(actual)
        if quarter not in (1, 2, 3, 4):
            return float('nan')
        amount = self._number(self._value_at(value, args, actual, kwargs))
        if math.isnan(amount):
            return float('nan')
        return amount * (4.0 / quarter)

    def PCTANN(self, numerator, denominator, *args, date='P0', **kwargs):
        root = self._call_root(denominator) or self._call_root(numerator)
        if root is None:
            return float('nan')
        actual = root.actual_date(date)
        denominator_value = self._value_at(denominator, args, actual, kwargs)
        return self._historical_divide(self.ANN(numerator, *args, date=date, **kwargs), denominator_value)

    def PCTOFANN(self, numerator, denominator, *args, date='P0', **kwargs):
        return self.PCTANN(numerator, denominator, *args, date=date, **kwargs) * 100.0

    def PCTOF(self, numerator, denominator, *args, date='P0', **kwargs):
        root = self._call_root(denominator) or self._call_root(numerator)
        actual = root.actual_date(date) if root is not None else None
        num = self._value_at(numerator, args, actual, kwargs) if callable(numerator) else numerator
        den = self._value_at(denominator, args, actual, kwargs) if callable(denominator) else denominator
        return self._historical_divide(num, den) * 100.0

    def PCT(self, numerator, denominator, *args, date='P0', **kwargs):
        return self.PCTOF(numerator, denominator, *args, date=date, **kwargs)

class CallReport_031(LagSupport):

    def __init__(self, row, history=None):
        self._init_lags(row, history)
        self.Maturities = self.Maturities(self)
        self.RegulatoryCapital = self.RegulatoryCapital(self)
        self.BalanceSheet = self.BalanceSheet(self)
        self.Securities = self.Securities(self)
        self.LoansAndLeases = self.LoansAndLeases(self)
        self.DepositLiabilities = self.DepositLiabilities(self)
        self.OtherLiabilities = self.OtherLiabilities(self)
        self.DerivativesOffBalanceSheet = self.DerivativesOffBalanceSheet(self)
        self.NonaccrualPastDue = self.NonaccrualPastDue(self)
        self.DepositInsurance = self.DepositInsurance(self)
        self.MeasuredAtFV = self.MeasuredAtFV(self)

    def _zero(self, value, name=False, *args, date='P0', **kwargs):
        row = self.get_row(date)
        return Global_uc(row)._zero(value, date=date)

    def _div(self, numerator, denominator, name=False, *args, date='P0', **kwargs):
        row = self.get_row(date)
        return Global_uc(row)._div(numerator, denominator, date=date)

    def RSSDID(self, name=False, *args, date='P0', **kwargs):
        row = self.get_row(date)
        return row['IDRSSD']

    def ReportingDate(self, name=False, *args, date='P0', **kwargs):
        row = self.get_row(date)
        return row['RCON9999']

    def Certificate(self, name=False, *args, date='P0', **kwargs):
        row = self.get_row(date)
        return row['FDIC Certificate Number']

    def Value(self, column, name=False, *args, date='P0', **kwargs):
        row = self.get_row(date)
        return row[column]

    class Maturities:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.Government = self.Government(self)
            self.ResidentialMortgage = self.ResidentialMortgage(self)

        class Government:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA549']

            def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA550']

            def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA551']

            def FiveYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA552']

            def FifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA553']

            def OverFifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA554']

            def Values(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return (self.ThreeMonths(date=date), self.TwelveMonths(date=date), self.ThreeYears(date=date), self.FiveYears(date=date), self.FifteenYears(date=date), self.OverFifteenYears(date=date))

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return sum(self.Values(date=date))

        class ResidentialMortgage:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA555']

            def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA556']

            def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA557']

            def FiveYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA558']

            def FifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA559']

            def OverFifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA560']

            def Values(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return (self.ThreeMonths(date=date), self.TwelveMonths(date=date), self.ThreeYears(date=date), self.FiveYears(date=date), self.FifteenYears(date=date), self.OverFifteenYears(date=date))

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return sum(self.Values(date=date))

        def Values(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return self.Government.Values(date=date) + self.ResidentialMortgage.Values(date=date)

    class RegulatoryCapital:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.EquityCapital = self.EquityCapital(self)
            self.CET1 = self.CET1(self)
            self.flags = {}
            self.messages = {}

        def RiskWeightedAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCFAA223']

        def TierOneCapital(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCFAP840']

        def CommonEquityTierOneCapital(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCFAP859']

        def AugmentedRiskWeightedAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            values = self.root.Maturities.Values(date=date)
            return self.RiskWeightedAssets(date=date) + (0.15 * values[5] + 0.1 * values[4] + 0.08 * values[3] + 0.15 * values[11] + 0.1 * values[10] + 0.08 * values[9])

        def ZeroRiskWeightedAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) >= 20150331:
                return row['RCOND987']
            return row['RCFDB696']

        def ZeroRiskWeightExposureRatio(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            domestic = row['RCON1754'] + row['RCON1773']
            if self.root.ReportingDate(date=date) >= 20150331:
                denominator = domestic
                if denominator == 0:
                    denominator = row['RCFD1754'] + row['RCFD1773']
                return safe_divide(row['RCOND962'] + row['RCOND967'], denominator)
            return safe_divide(row['RCONB603'] + row['RCONB608'], domestic)

        def RiskWeightAdjustment(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            values = self.root.Maturities.Values(date=date)
            return values[5] + values[4] + values[11] + values[10]

        def AdjustedZeroRiskWeightedAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) < 20150331:
                return self.ZeroRiskWeightedAssets(date=date)
            return self.ZeroRiskWeightedAssets(date=date) - self.ZeroRiskWeightExposureRatio(date=date) * self.RiskWeightAdjustment(date=date)

        def ZeroRiskToReportedRWA(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return safe_divide(self.ZeroRiskWeightedAssets(date=date), self.RiskWeightedAssets(date=date))

        def ZeroRiskToAugmentedRWA(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            denominator = self.AugmentedRiskWeightedAssets(date=date) if self.root.ReportingDate(date=date) >= 20150331 else self.RiskWeightedAssets(date=date)
            return safe_divide(self.ZeroRiskWeightedAssets(date=date), denominator)

        def AdjustedZeroRiskToAugmentedRWA(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            denominator = self.AugmentedRiskWeightedAssets(date=date) if self.root.ReportingDate(date=date) >= 20150331 else self.RiskWeightedAssets(date=date)
            return safe_divide(self.AdjustedZeroRiskWeightedAssets(date=date), denominator)

        def RelativeZeroRiskAdjustment(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            baseline = self.ZeroRiskToAugmentedRWA(date=date)
            if baseline == 0:
                return 0.0
            return 1.0 - safe_divide(self.AdjustedZeroRiskToAugmentedRWA(date=date), baseline)

        class EquityCapital:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.AOCI = self.AOCI(self)
                self.flags = {}
                self.messages = {}

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = '[calculated] Common stock, plus surplus, net of treasury stock + retained earnings + AOCI'
                if name:
                    return self.name
                return row['RCFAP742'] + row['RCFAKW00'] + row['RCFAB530']

            def CommonStockSurplus(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Common stock plus related surplus, net of treasury stock and unearned employee stock ownership plan shares'
                if name:
                    return self.name
                return row['RCFAP742']

            def RetainedEarnings(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Retained earnings'
                if name:
                    return self.name
                return row['RCFAKW00']

            def CECLDesignation(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'CECL transition election'
                if name:
                    return self.name
                return row['RCOAJJ29']

            class AOCI:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def BeforeAdjustments(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Accumulated other comprehensive income (AOCI)'
                    if name:
                        return self.name
                    return row['RCFAKW00']

                def OptOutElection(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'AOCI opt-out election'
                    if name:
                        return self.name
                    return row['RCOAP838']

                def AFSSecuritiesNet(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if self.OptOutElection(date=date) == 0 or self.OptOutElection(date=date) == '0':
                        self.name = 'Net unrealized gains on Available-for-Sale debt securities'
                        if name:
                            return self.name
                        return row['RCFAP844']
                    elif self.OptOutElection(date=date) == 1 or self.OptOutElection(date=date) == '1':
                        self.name = 'Net unrealized gains on Available-for-Sale debt securities'
                        if name:
                            return self.name
                        return 0.0

                def CashFlowHedgesNet(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if self.OptOutElection(date=date) == 0 or self.OptOutElection(date=date) == '0':
                        self.name = 'Accumulated net gains on cash flow hedges'
                        if name:
                            return self.name
                        return row['RCFAP846']
                    elif self.OptOutElection(date=date) == 1 or self.OptOutElection(date=date) == '1':
                        self.name = 'Accumulated net gains on cash flow hedges'
                        if name:
                            return self.name
                        return 0.0

                def DefinedBenefits(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if self.OptOutElection(date=date) == 0 or self.OptOutElection(date=date) == '0':
                        self.name = 'Accumulated net gains on cash flow hedges'
                        if name:
                            return self.name
                        return row['RCFAP847']
                    if self.OptOutElection(date=date) == 1 or self.OptOutElection(date=date) == '1':
                        self.name = 'Accumulated net gains on cash flow hedges'
                        if name:
                            return self.name
                        return 0.0

                def HTMSecuritiesNet(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if self.OptOutElection(date=date) == 0 or self.OptOutElection(date=date) == '0':
                        self.name = 'Net unrealized gains on Held-to-Maturity securities that are included in AOCI'
                        if name:
                            return self.name
                        return row['RCFAP848']
                    if self.OptOutElection(date=date) == 1 or self.OptOutElection(date=date) == '1':
                        self.name = 'Net unrealized gains on Held-to-Maturity securities that are included in AOCI'
                        if name:
                            return self.name
                        return 0.0

                def AOCICashFlowHedgesNet(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if self.OptOutElection(date=date) == 0 or self.OptOutElection(date=date) == '0':
                        self.name = 'Accumulated net gain on cash flow hedges included in AOCI'
                        if name:
                            return self.name
                        return row['RCFAP849']
                    if self.OptOutElection(date=date) == 1 or self.OptOutElection(date=date) == '1':
                        self.name = 'Accumulated net gain on cash flow hedges included in AOCI'
                        if name:
                            return self.name
                        return 0.0

        class CET1:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def MinorityInterests(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Common equity tier 1 minority interest includable in common equity tier 1 capital'
                if name:
                    return self.name
                return row['RCFAP839']

            def BeforeDeductions(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Common equity tier 1 before deductions'
                if name:
                    return self.name
                c1 = self.root.RegulatoryCapital.EquityCapital.CommonStockSurplus(date=date)
                c2 = self.root.RegulatoryCapital.EquityCapital.RetainedEarnings(date=date)
                c3 = self.root.RegulatoryCapital.EquityCapital.AOCI.BeforeAdjustments(date=date)
                c4 = self.MinorityInterests(date=date)
                comp1 = c1 + c2 + c3 + c4
                CET1 = row['RCFAP840']
                difference1 = CET1 - comp1
                self.flags['CET1BeforeDeductions'] = False
                self.messages['CET1BeforeDeductions'] = None
                if difference1 > 0:
                    self.flags['CET1BeforeDeductions'] = True
                    self.messages['CET1BeforeDeductions'] = f'{self.name}: {CET1} does not equal {comp1} by {difference1} because {self.root.RegulatoryCapital.EquityCapital.CommonStockSurplus(name=True, date=date)} = {c1}, {self.root.RegulatoryCapital.EquityCapital.RetainedEarnings(name=True, date=date)} = {c2}, {self.root.RegulatoryCapital.EquityCapital.AOCI.BeforeAdjustments(name=True, date=date)} = {c3}, {self.MinorityInterests(name=True, date=date)} = {c4} in {self.name} for IDRSSD {self.root.RSSDID(date=date)} on {self.root.ReportingDate(date=date)}'
                    print(self.messages['CET1BeforeDeductions'])
                return row['RCFAP840']

    class BalanceSheet:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.LoansAndLeaseFinancingReceivables = self.LoansAndLeaseFinancingReceivables(self)
            self.DepositDomesticOffices = self.DepositDomesticOffices(self)

        def CashAndBalancesDue(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCFD0081'] + row['RCFD0071']

        def TotalSecurities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) >= 20190331:
                return row['RCFDJJ34'] + row['RCFD1773'] + row['RCFDJA22']
            else:
                return row['RCFD1754'] + row['RCFD1773']

        def HTMSecurities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) >= 20190331:
                return row['RCFDJJ34']
            else:
                return row['RCFD1754']

        def AFSSecurities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCFD1773']

        class LoansAndLeaseFinancingReceivables:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def Total(self, validate=False, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                total = row['RCFDB529']
                if not validate:
                    return total
                comp = self.LoansAndLeasesHeldForSale(date=date) + self.LoansAndLeasesHeldForInvestment(date=date) - self.AllowanceForCreditLossesOnLoansAndLeases(date=date)
                difference = total - comp
                self.flags['Total'] = False
                self.messages['Total'] = None
                self.name = 'Loans and Leases held for Investment, Net of Allowance (Schedule RC)'
                if total != comp:
                    self.flags['Total'] = True
                    self.messages['Total'] = f'{total} does not equal {comp} by {difference} in {self.name} for IDRSSD {self.root.RSSDID(date=date)} on {self.root.ReportingDate(date=date)}'
                    print(self.messages['Total'])
                return total

            def LoansAndLeasesHeldForSale(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFD5369']

            def LoansAndLeasesHeldForInvestment(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDB528']

            def AllowanceForCreditLossesOnLoansAndLeases(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFD3123']

            def TotalIncludingHeldForSale(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return self.LoansAndLeasesHeldForSale(date=date) + self.Total(date=date)

        def TradingAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCFD3545']

        def OtherRealEstateOwned(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCFD2150']

        def IntangibleAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) >= 20180630:
                return row['RCFD2143']
            else:
                return row['RCFD3163'] + row['RCFD0426']

        def TotalAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) >= 20180331:
                return row['RCFD2170'] - row['RCFDJA22'] + row['RCFD3123']
            else:
                return row['RCFD2170'] + row['RCFD3123']

        def FederalFundsPurchased(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCONB993'] + row['RCFDB995']

        def FederalFundsSold(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCONB987'] + row['RCFDB989']

        class DepositDomesticOffices:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def NonInterestBearing(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCON6631']

            def InterestBearing(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCON6636']

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return self.NonInterestBearing(date=date) + self.InterestBearing(date=date)

        def TradingLiabilities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCFD3548']

        def OtherLiabilities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCFD2930']

        def OtherBorrowedMoney(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCFD3190']

        def TotalLiabilities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCFD2948']

        def TotalLiabilitiesIncludingAllowance(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return self.TotalLiabilities(date=date) + self.LoansAndLeaseFinancingReceivables.AllowanceForCreditLossesOnLoansAndLeases(date=date)

        def ReportedTotalEquityCapital(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCFDG105']

        def TotalEquityCapital(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) >= 20180331:
                return row['RCFDG105'] - row['RCFDJA22']
            else:
                return row['RCFDG105']

    class Securities:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.ResidentialPassThru = self.ResidentialPassThru(self)
            self.flags = {}
            self.messages = {}

        def USTreasuries(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    return row['RCFD0211']
                elif valuation == 'fv':
                    return row['RCFD0213']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCFD1286']
                elif valuation == 'fv':
                    return row['RCFD1287']

        def USGovtObligations(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) > 20180331:
                if accounting == 'htm':
                    if valuation == 'ac':
                        return row['RCFDHT50']
                    elif valuation == 'fv':
                        return row['RCFDHT51']
                elif accounting == 'afs':
                    if valuation == 'ac':
                        return row['RCFDHT52']
                    elif valuation == 'fv':
                        return row['RCFDHT53']
            elif accounting == 'htm':
                if valuation == 'ac':
                    return row['RCFD1289'] + row['RCFD1294']
                elif valuation == 'fv':
                    return row['RCFD1290'] + row['RCFD1295']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCFD1291'] + row['RCFD1297']
                elif valuation == 'fv':
                    return row['RCFD1293'] + row['RCFD1298']

        def StateSecurities(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    return row['RCFD8496']
                elif valuation == 'fv':
                    return row['RCFD8497']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCFD8498']
                elif valuation == 'fv':
                    return row['RCFD8499']

        class ResidentialPassThru:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def Total(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if accounting == 'htm':
                    if valuation == 'ac':
                        return self.parent.GNMAPassThru(accounting='htm', valuation='ac', date=date) + self.parent.FNMAPassThru(accounting='htm', valuation='ac', date=date) + self.parent.OtherPassThru(accounting='htm', valuation='ac', date=date)
                    elif valuation == 'fv':
                        return self.parent.GNMAPassThru(accounting='htm', valuation='fv', date=date) + self.parent.FNMAPassThru(accounting='htm', valuation='fv', date=date) + self.parent.OtherPassThru(accounting='htm', valuation='fv', date=date)
                elif accounting == 'afs':
                    if valuation == 'ac':
                        return self.parent.GNMAPassThru(accounting='afs', valuation='ac', date=date) + self.parent.FNMAPassThru(accounting='afs', valuation='ac', date=date) + self.parent.OtherPassThru(accounting='afs', valuation='ac', date=date)
                    elif valuation == 'fv':
                        return self.parent.GNMAPassThru(accounting='afs', valuation='fv', date=date) + self.parent.FNMAPassThru(accounting='afs', valuation='fv', date=date) + self.parent.OtherPassThru(accounting='afs', valuation='fv', date=date)

            def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA555']

            def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA556']

            def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA557']

            def FiveYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA558']

            def FifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA559']

            def OverFifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCFDA560']

        def OtherResidentialPassThru(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return self.OtherResidentialGNMA(accounting, valuation, date=date) + self.OtherResidentialFNMA(accounting, valuation, date=date) + self.OtherResidentialOther(accounting, valuation, date=date)

        def OtherResidentialGNMA(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    return row['RCFDG312']
                elif valuation == 'fv':
                    return row['RCFDG313']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCFDG314']
                elif valuation == 'fv':
                    return row['RCFDG315']

        def OtherResidentialFNMA(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            suffix = {('htm', 'ac'): 'G316', ('htm', 'fv'): 'G317', ('afs', 'ac'): 'G318', ('afs', 'fv'): 'G319'}
            return row['RCFD' + suffix[accounting, valuation]]

        def OtherResidentialOther(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            suffix = {('htm', 'ac'): 'G320', ('htm', 'fv'): 'G321', ('afs', 'ac'): 'G322', ('afs', 'fv'): 'G323'}
            return row['RCFD' + suffix[accounting, valuation]]

        def CommericalPassThru(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) > 20110331:
                if accounting == 'htm':
                    if valuation == 'ac':
                        return row['RCFDK142'] + row['RCFDK146']
                    elif valuation == 'fv':
                        return row['RCFDK143'] + row['RCFDK147']
                elif accounting == 'afs':
                    if valuation == 'ac':
                        return row['RCFDK144'] + row['RCFDK148']
                    elif valuation == 'fv':
                        return row['RCFDK145'] + row['RCFDK149']
            elif accounting == 'htm':
                if valuation == 'ac':
                    return row['RCFDG324']
                elif valuation == 'fv':
                    return row['RCFDG325']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCFDG326']
                elif valuation == 'fv':
                    return row['RCFDG327']

        def OtherCommericalMBS(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) > 20110331:
                if accounting == 'htm':
                    if valuation == 'ac':
                        return row['RCFDK150'] + row['RCFDK154']
                    elif valuation == 'fv':
                        return row['RCFDK151'] + row['RCFDK155']
                elif accounting == 'afs':
                    if valuation == 'ac':
                        return row['RCFDK152'] + row['RCFDK156']
                    elif valuation == 'fv':
                        return row['RCFDK153'] + row['RCFDK157']
            elif accounting == 'htm':
                if valuation == 'ac':
                    return row['RCFDG328']
                elif valuation == 'fv':
                    return row['RCFDG329']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCFDG330']
                elif valuation == 'fv':
                    return row['RCFDG331']

        def GNMAPassThru(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    return row['RCFDG300']
                elif valuation == 'fv':
                    return row['RCFDG301']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCFDG302']
                elif valuation == 'fv':
                    return row['RCFDG303']

        def FNMAPassThru(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    return row['RCFDG304']
                elif valuation == 'fv':
                    return row['RCFDG305']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCFDG306']
                elif valuation == 'fv':
                    return row['RCFDG307']

        def OtherPassThru(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    return row['RCFDG308']
                elif valuation == 'fv':
                    return row['RCFDG309']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCFDG310']
                elif valuation == 'fv':
                    return row['RCFDG311']

        def MBSTotal(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    self.name = 'Total Mortgage-backed Securities Held-to-Maturity at Amortized Cost (Schedule RC-B)'
                    if name:
                        return self.name
                    return self.ResidentialPassThru.Total(accounting='htm', valuation='ac', date=date) + self.OtherResidentialPassThru(accounting='htm', valuation='ac', date=date) + self.CommericalPassThru(accounting='htm', valuation='ac', date=date) + self.OtherCommericalMBS(accounting='htm', valuation='ac', date=date)
                elif valuation == 'fv':
                    if name:
                        return None
                    return self.ResidentialPassThru.Total(accounting='htm', valuation='fv', date=date) + self.OtherResidentialPassThru(accounting='htm', valuation='fv', date=date) + self.CommericalPassThru(accounting='htm', valuation='fv', date=date) + self.OtherCommericalMBS(accounting='htm', valuation='fv', date=date)
            elif accounting == 'afs':
                if valuation == 'ac':
                    if name:
                        return None
                    return self.ResidentialPassThru.Total(accounting='afs', valuation='ac', date=date) + self.OtherResidentialPassThru(accounting='afs', valuation='ac', date=date) + self.CommericalPassThru(accounting='afs', valuation='ac', date=date) + self.OtherCommericalMBS(accounting='afs', valuation='ac', date=date)
                elif valuation == 'fv':
                    self.name = 'Total Mortgage-backed Securities Available-for-Sale at Fair Value (Schedule RC-B)'
                    if name:
                        return self.name
                    return self.ResidentialPassThru.Total(accounting='afs', valuation='fv', date=date) + self.OtherResidentialPassThru(accounting='afs', valuation='fv', date=date) + self.CommericalPassThru(accounting='afs', valuation='fv', date=date) + self.OtherCommericalMBS(accounting='afs', valuation='fv', date=date)

        def ABS(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    self.name = 'Asset-backed Securities Held-to-Maturity at Amortized Cost (Schedule RC-B)'
                    if name:
                        return self.name
                    return row['RCFDC026']
                elif valuation == 'fv':
                    return row['RCFDC988']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCFDC989']
                elif valuation == 'fv':
                    self.name = 'Asset-backed Securities Available-for-Sale at Fair Value (Schedule RC-B)'
                    if name:
                        return self.name
                    return row['RCFDC027']

        def OtherDebtSecurities(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    self.name = 'Other Debt Securities Held-to-Maturity at Amortized Cost from (Schedule RC-B)'
                    if name:
                        return self.name
                    return row['RCFD1737'] + row['RCFD1742']
                elif valuation == 'fv':
                    return row['RCFD1738'] + row['RCFD1743']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCFD1739'] + row['RCFD1744']
                elif valuation == 'fv':
                    self.name = 'Other Debt Securities Available-for-Sale at Fair Value from (Schedule RC-B)'
                    if name:
                        return self.name
                    return row['RCFD1741'] + row['RCFD1746']

        def Total(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    total = row['RCFD1754']
                    self.name = 'Total Held-to-Maturity Securities at Amortized Cost'
                    if name:
                        return self.name
                    return total
                elif valuation == 'fv':
                    self.name = 'Total Held-to-Maturity Securities at Fair Value'
                    if name:
                        return self.name
                    return row['RCFD1771']
            elif accounting == 'afs':
                if valuation == 'ac':
                    self.name = 'Total Available-for-Sale Securities at Amortized Cost'
                    if name:
                        return self.name
                    return row['RCFD1772']
                elif valuation == 'fv':
                    total = row['RCFD1773']
                    self.name = 'Total Available-for-Sale Securities at Amortized Cost'
                    if name:
                        return self.name
                    return total

    class LoansAndLeases:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.SecuredRealEstate = self.SecuredRealEstate(self)
            self.Individuals = self.Individuals(self)
            self.ExcludingClosedEnd = self.ExcludingClosedEnd(self)
            self.DepositoryInstitutions = self.DepositoryInstitutions(self)
            self.flags = {}
            self.messages = {}

        def Total(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'domestic':
                self.name = 'Loans and leases in domestic offices (schedule RC-C Part I)'
                if name:
                    return self.name
                return row['RCON2122']
            if column == 'consolidated':
                self.name = 'Loans and leases in consolidated bank (schedule RC-C Part I)'
                if name:
                    return self.name
                return row['RCFD2122']

        class SecuredRealEstate:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.SFR = self.SFR(self)

            def Total(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Total loans secured by real estate in domestic offices'
                    if name:
                        return self.name
                    return self.ConstructionSFR(column='domestic', date=date) + self.ConstructionOther(column='domestic', date=date) + self.Farmland(column='domestic', date=date) + self.SFR.OpenEndRevolving(column='domestic', date=date)

            def ConstructionSFR(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Loans secured by real estate for the construction of 1-4 family residential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF158']
                if column == 'consolidated':
                    self.name = 'Loans secured by real estate for the construction of 1-4 family residential properties in consolidated bank'
                    if name:
                        return self.name
                    return row['RCFDF158']

            def ConstructionOther(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Loans secured by real estate for all land development in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF159']
                if column == 'consolidated':
                    self.name = 'Loans secured by real estate for all land development in consolidated bank'
                    if name:
                        return self.name
                    return row['RCFDF159']

            def Farmland(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Loans secured by farmland in domestic offices'
                    if name:
                        return self.name
                    return row['RCON1420']
                if column == 'consolidated':
                    self.name = 'Loans secured by farmland in consolidated bank'
                    if name:
                        return self.name
                    return row['RCFD1420']

            class SFR:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.ClosedEndFirstLiens = self.ClosedEndFirstLiens(self)
                    self.flags = {}
                    self.messages = {}

                def OpenEndRevolving(self, column, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if column == 'domestic':
                        self.name = 'Loans secured by real estate for all land development in domestic offices'
                        if name:
                            return self.name
                        return row['RCON1797']
                    if column == 'consolidated':
                        self.name = 'Loans secured by real estate for all land development in consolidated bank'
                        if name:
                            return self.name
                        return row['RCFD1797']

                class ClosedEndFirstLiens:

                    def __init__(self, parent):
                        self.parent = parent
                        self.root = parent.root
                        self.row = self.root.row
                        self.flags = {}
                        self.messages = {}

                    def Total(self, name=False, column='domestic', *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if column == 'domestic':
                            self.name = 'Loans secured by real estate for closed-end family residential secured by first liens in domestic offices (Schedule RC-C Part I)'
                            if name:
                                return self.name
                            return row['RCON5367']
                        elif column == 'consolidated':
                            self.name = 'Loans secured by real estate for closed-end family residential secured by first liens in consolidated bank (Schedule RC-C Part I)'
                            if name:
                                return self.name
                            return row['RCFD5367']

                    def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Closed-end first liens with maturity and repricing data three months or less'
                        if name:
                            return self.name
                        return row['RCONA564']

                    def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Closed-end first liens with maturity and repricing data over three months through 12 months'
                        if name:
                            return self.name
                        return row['RCONA565']

                    def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Closed-end first liens with maturity and repricing data over one year through three years'
                        if name:
                            return self.name
                        return row['RCONA566']

                    def FiveYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Closed-end first liens with maturity and repricing data over three years through five years'
                        if name:
                            return self.name
                        return row['RCONA567']

                    def FifteenYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Closed-end first liens with maturity and repricing data over five years through fifteen years'
                        if name:
                            return self.name
                        return row['RCONA568']

                    def OverFifteenYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Closed-end first liens with maturity and repricing data over fifteen years'
                        if name:
                            return self.name
                        return row['RCONA569']

            def FinanceAgricultural(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Loans to finance agricultural production and other loans to farmers'
                    if name:
                        return self.name
                    return row['RCON1590']
                elif column == 'consolidated':
                    self.name = 'Loans to finance agricultural production and other loans to farmers'
                    if name:
                        return self.name
                    return row['RCFD1590']

            def CommercialAndIndustrial(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Commercial and industrial loans in domestic offices'
                    if name:
                        return self.name
                    return row['RCON1763'] + row['RCON1764']
                elif column == 'consolidated':
                    self.name = 'Commercial and industrial loans in consolidated bank'
                    if name:
                        return self.name
                    return row['RCFD1763'] + row['RCFD1764']

            def multifamily(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Secured by multifamily (5 or more) residential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCON1460']
                elif column == 'consolidated':
                    self.name = 'Secured by multifamily (5 or more) residential properties in consolidated bank'
                    if name:
                        return self.name
                    return row['RCFD1460']

            def SecuredNonfarmOwner(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Secured by owner-occupied nonfarm non-residential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF160']
                elif column == 'consolidated':
                    self.name = 'Secured by owner-occupied nonfarm non-residential properties in consolidated bank'
                    if name:
                        return self.name
                    return row['RCFDF160']

            def SecuredNonfarmOther(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Secured by other nonfarm non-residential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF161']
                elif column == 'consolidated':
                    self.name = 'Secured by other nonfarm non-residential properties in consolidated bank'
                    if name:
                        return self.name
                    return row['RCFDF161']

        class Individuals:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def CreditCardLines(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Loans to individuals for credit card lines in domestic offices'
                    if name:
                        return self.name
                    return row['RCONB538']
                elif column == 'consolidated':
                    self.name = 'Loans to individuals for credit card lines in consolidated bank'
                    if name:
                        return self.name
                    return row['RCFDB538']

            def RevolvingCredit(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Loans to individuals for other revolving credit lines in domestic offices'
                    if name:
                        return self.name
                    return row['RCONB539']
                elif column == 'consolidated':
                    self.name = 'Loans to individuals for other revolving credit lines in consolidated bank'
                    if name:
                        return self.name
                    return row['RCFDB539']

            def AutomobileLoans(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Loans to individuals for automobile loans in domestic offices'
                    if name:
                        return self.name
                    return row['RCONK137']
                elif column == 'consolidated':
                    self.name = 'Loans to individuals for automobile loans in consolidated bank'
                    if name:
                        return self.name
                    return row['RCFDK137']

            def ConsumerLoans(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Loans to individuals for consumer loans in domestic offices'
                    if name:
                        return self.name
                    return row['RCONK207']
                elif column == 'consolidated':
                    self.name = 'Loans to individuals for consumer loans in consolidated bank'
                    if name:
                        return self.name
                    return row['RCFDK207']

        class ExcludingClosedEnd:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def Total(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Loans secured by real estate for closed-end family residential secured by first liens in domestic offices (Schedule RC-C Part I)'
                    if name:
                        return self.name
                    return row['RCONF158'] + row['RCONF159'] + row['RCON1420'] + row['RCON1797'] + row['RCON5368'] + row['RCON1460'] + row['RCONF160'] + row['RCONF161'] + row['RCONB531'] + row['RCONB534'] + row['RCONB535'] + row['RCON1590'] + row['RCON1763'] + row['RCON1764'] + row['RCONB538'] + row['RCONB539'] + row['RCONK137'] + row['RCONK207'] + row['RCON2081'] + row['RCON2107'] + row['RCONJ454'] + row['RCON1545'] + row['RCONJ451'] + row['RCON2165']
                elif column == 'consolidated':
                    self.name = 'Loans secured by real estate for closed-end family residential secured by first liens in consolidated bank (Schedule RC-C Part I)'
                    if name:
                        return self.name
                    return row['RCFDF158'] + row['RCFDF159'] + row['RCFD1420'] + row['RCFD1797'] + row['RCFD5368'] + row['RCFD1460'] + row['RCFDF160'] + row['RCFDF161'] + row['RCFDB532'] + row['RCFDB533'] + row['RCFDB534'] + row['RCFDB536'] + row['RCFDB537'] + row['RCFD1590'] + row['RCFD1763'] + row['RCFD1764'] + row['RCFDB538'] + row['RCFDB539'] + row['RCFDK137'] + row['RCFDK207'] + row['RCFD2081'] + row['RCFD2107'] + row['RCFD1563'] + row['RCFDF162'] + row['RCFDF163']

            def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'All loans excluding Closed-end first liens with maturity and repricing data three months or less'
                if name:
                    return self.name
                return row['RCFDA570']

            def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'All loans excluding Closed-end first liens with maturity and repricing data over three months through 12 months'
                if name:
                    return self.name
                return row['RCFDA571']

            def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'All loans excluding Closed-end first liens with maturity and repricing data over one year through three years'
                if name:
                    return self.name
                return row['RCFDA572']

            def FiveYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'All loans excluding Closed-end first liens with maturity and repricing data over three years through five years'
                if name:
                    return self.name
                return row['RCFDA573']

            def FifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'All loans excluding Closed-end first liens with maturity and repricing data over five years through fifteen years'
                if name:
                    return self.name
                return row['RCFDA574']

            def OverFifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'All loans excluding Closed-end first liens with maturity and repricing data over fifteen years'
                if name:
                    return self.name
                return row['RCFDA575']

        def ForeignGovt(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'domestic':
                self.name = 'Loans to foreign governments in domestic offices'
                if name:
                    return self.name
                return row['RCON2081']
            elif column == 'consolidated':
                self.name = 'Loans to foreign governments in domestic offices'
                if name:
                    return self.name
                return row['RCFD2081']

        def StatesAndPolitical(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'domestic':
                self.name = 'Obligations (other than securities and leases) of state and plitical subdivisions in the U.S. in domestic offices'
                if name:
                    return self.name
                return row['RCON2107']
            elif column == 'consolidated':
                self.name = 'Obligations (other than securities and leases) of state and plitical subdivisions in the U.S. in conslidated bank'
                if name:
                    return self.name
                return row['RCFD2107']

        class DepositoryInstitutions:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def Total(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Total loans to all depository institutions in domestic offices'
                    if name:
                        return self.name
                    return self.CommercialBanks(column='domestic', date=date) + self.Other(column='domestic', date=date) + self.ForeignCountries(column='domestic', date=date)
                elif column == 'consolidated':
                    self.name = 'Total loans to all depository institutions in domestic offices'
                    if name:
                        return self.name
                    return self.CommercialBanks(column='consolidated', date=date) + self.Other(column='consolidated', date=date) + self.ForeignCountries(column='consolidated', date=date)

            def USBanksTotal(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Loans to all depository institutions in the U.S.'
                    if name:
                        return self.name
                    return self.CommercialBanks(column='domestic', date=date) + self.Other(column='domestic', date=date)
                elif column == 'consolidated':
                    self.name = 'Loans to all depository institutions in the U.S.'
                    if name:
                        return self.name
                    return self.CommercialBanks(column='domestic', date=date) + self.Other(column='domestic', date=date)

            def CommercialBanks(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Loans to depository institutions: commercial banks in domestic offices (Schedule RC-C Part I)'
                    if name:
                        return self.name
                    return row['RCONB531']
                elif column == 'consolidated':
                    self.name = 'Loans to depository institutions: commercial banks in consolidated bank (Schedule RC-C Part I)'
                    if name:
                        return self.name
                    return row['RCFDB532'] + row['RCFDB533']

            def Other(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Loans to depository institutions: other depository institutions in domestic offices (Schedule RC-C Part I)'
                    if name:
                        return self.name
                    return row['RCONB534']
                elif column == 'consolidated':
                    self.name = 'Loans to depository institutions: other depository institutions in consolidated bank (Schedule RC-C Part I)'
                    if name:
                        return self.name
                    return row['RCFDB534']

            def ForeignCountries(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'domestic':
                    self.name = 'Loans to depository institutions with foreign branches (Schedule RC-C Part I)'
                    if name:
                        return self.name
                    return row['RCONB535']
                elif column == 'consolidated':
                    self.name = 'Loans to depository institutions with foreign branches (Schedule RC-C Part I)'
                    if name:
                        return self.name
                    return row['RCFDB536'] + row['RCFDB537']

        def NonDepository(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCONJ454']
            self.name = 'Loans to nondepository financial institutions (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def NonDepositoryOther(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCONJ464']
            self.name = 'Loans to nondepository financial institutions and other loans (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def UnearnedIncome(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCON2123']
            self.name = 'Loans to nondepository financial institutions (Schedule RC-C Part I)'
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
            self.flags = {}
            self.messages = {}

        def ReportedTotal(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCON2200']

        def DomesticDeposits(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            DomesticDeposits = self.root.BalanceSheet.DepositDomesticOffices.Total(date=date)
            self.name = 'Total Domestic Deposits'
            if name:
                return self.name
            comp = self.TransactionDeposits.Total(date=date) + self.NonTransactionDeposits.Total(date=date)
            difference = DomesticDeposits - comp
            self.flags['DomesticDeposits'] = False
            self.messages['DomesticDeposits'] = None
            if self.TransactionDeposits.flags.get('Total', False) or self.NonTransactionDeposits.flags.get('Total', False):
                causes = []
                if self.TransactionDeposits.flags.get('Total', False):
                    causes.append(self.TransactionDeposits.messages.get('Total'))
                if self.NonTransactionDeposits.flags.get('Total', False):
                    causes.append(self.NonTransactionDeposits.messages.get('Total'))
                self.flags['DomesticDeposits'] = True
                self.messages['DomesticDeposits'] = f"{DomesticDeposits} does not equal {comp} by {difference} in {self.name} for IDRSSD {self.root.RSSDID(date=date)} on {self.root.ReportingDate(date=date)} check {' | '.join(causes)}"
                print(self.messages['DomesticDeposits'])
            elif DomesticDeposits != comp:
                self.flags['DomesticDeposits'] = True
                self.messages['DomesticDeposits'] = f'{DomesticDeposits} does not equal {comp} by {difference} in {self.name} for IDRSSD {self.root.RSSDID(date=date)} on {self.root.ReportingDate(date=date)} '
                print(self.messages['DomesticDeposits'])
            return DomesticDeposits

        def Individuals(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Individual Domestic Deposits'
            if name:
                return self.name
            return self.TransactionDeposits.Individuals(date=date) + self.NonTransactionDeposits.Individuals(date=date)

        def USGovt(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'U.S. Government Domestic Deposits'
            if name:
                return self.name
            return self.TransactionDeposits.USGovt(date=date) + self.NonTransactionDeposits.USGovt(date=date)

        def StatesAndPolitical(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'States and Political Subdivisions Domestic Deposits'
            if name:
                return self.name
            return self.TransactionDeposits.StatesAndPolitical(date=date) + self.NonTransactionDeposits.StatesAndPolitical(date=date)

        def CommercialBanks(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Commercial Banks Domestic Deposits'
            if name:
                return self.name
            return self.TransactionDeposits.CommercialBanks(date=date) + self.NonTransactionDeposits.CommercialBanks(date=date)

        def ForeignBanks(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Banks in Foreign Countires Domestic Deposits'
            if name:
                return self.name
            return self.TransactionDeposits.ForeignBanks(date=date) + self.NonTransactionDeposits.ForeignBanks(date=date)

        def ForeignGovt(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Foreign government Domestic Deposits'
            if name:
                return self.name
            return self.TransactionDeposits.ForeignGovt(date=date) + self.NonTransactionDeposits.ForeignGovt(date=date)

        class TransactionDeposits:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def Individuals(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Individual Transaction Deposits'
                if name:
                    return self.name
                return row['RCONB549']

            def USGovt(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'U.S. Government Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2202']

            def StatesAndPolitical(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'States and Political Subdivisions Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2203']

            def CommercialBanks(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Commercial Banks Transaction Deposits'
                if name:
                    return self.name
                return row['RCONB551']

            def ForeignBanks(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Banks in Foriegn Countries Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2213']

            def ForeignGovt(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Foreign Government Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2216']

            def ReportedTotal(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCON2215']

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                i = self.Individuals(date=date)
                u = self.USGovt(date=date)
                s = self.StatesAndPolitical(date=date)
                c = self.CommercialBanks(date=date)
                f = self.ForeignBanks(date=date)
                g = self.ForeignGovt(date=date)
                total = row['RCON2215']
                if name:
                    return self.name
                comp = i + u + s + c + f + g
                difference = total - comp
                self.flags['Total'] = False
                self.messages['Total'] = None
                self.name = 'Total Transaction Deposits'
                if total != comp:
                    self.flags['Total'] = True
                    self.messages['Total'] = f'{self.name}: {total} does not equal {comp} by {difference} in {self.name}: {self.Individuals(name=True, date=date)}={i}, {self.USGovt(name=True, date=date)}={u}, {self.StatesAndPolitical(name=True, date=date)}={s}, {self.CommercialBanks(name=True, date=date)}={c}, {self.ForeignBanks(name=True, date=date)}={f}, {self.ForeignGovt(name=True, date=date)}={g} on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                    print(self.messages['Total'])
                return total

        class NonTransactionDeposits:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.TimeDeposits = self.TimeDeposits(self)
                self.flags = {}
                self.messages = {}

            def Individuals(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Individual Non-Transaction Deposits'
                if name:
                    return self.name
                return row['RCONB550']

            def ReportedTotal(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCON2385']

            def USGovt(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'U.S. Government Non-Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2520']

            def StatesAndPolitical(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'States and Political Subdivisions Non-Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2530']

            def CommercialBanks(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Commercial Banks Non-Transaction Deposits'
                if name:
                    return self.name
                return row['RCONB552']

            def ForeignBanks(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Banks in Foriegn Countries Non-Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2236']

            def ForeignGovt(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Foreign Government Non-Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2377']

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                total = row['RCON2385']
                if name:
                    return self.name
                i1 = self.Individuals(date=date)
                u1 = self.USGovt(date=date)
                s1 = self.StatesAndPolitical(date=date)
                c1 = self.CommercialBanks(date=date)
                f1 = self.ForeignBanks(date=date)
                g1 = self.ForeignGovt(date=date)
                i2 = self.TimeDeposits.LessThan100k(date=date)
                u2 = self.TimeDeposits.LessThan250k.Total(date=date)
                s2 = self.TimeDeposits.MoreThan250k.Total(date=date)
                c2 = self.SavingsMMDA(date=date)
                f2 = self.SavingsOther(date=date)
                comp1 = i1 + u1 + s1 + c1 + f1 + g1
                comp2 = i2 + u2 + s2 + c2 + f2
                difference1 = total - comp1
                difference2 = total - comp2
                self.flags['Total'] = False
                self.flags['Memoranda2'] = False
                self.messages['Total'] = None
                self.messages['Memoranda2'] = None
                self.name = 'Total Non-Transaction Deposits'
                if total != comp1:
                    self.flags['Total'] = True
                    self.messages['Total'] = f'{self.Total(name=True, date=date)}: {total} does not equal {comp1} by {difference1} in {self.Total(name=True, date=date)}: {self.Individuals(name=True, date=date)}={i1}, {self.USGovt(name=True, date=date)}={u1}, {self.StatesAndPolitical(name=True, date=date)}={s1}, {self.CommercialBanks(name=True, date=date)}={c1}, {self.ForeignBanks(name=True, date=date)}={f1}, {self.ForeignGovt(name=True, date=date)}={g1} on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                    print(self.messages['Total'])
                if total != comp2:
                    self.flags['Memoranda2'] = True
                    self.messages['Memoranda2'] = f'{self.name}: {total} does not equal {comp2} by {difference2} in {self.name}: {self.TimeDeposits.LessThan100k(name=True, date=date)}={i2}, {self.TimeDeposits.LessThan250k.Total(name=True, date=date)}={u2}, {self.TimeDeposits.MoreThan250k.Total(name=True, date=date)}={s2}, {self.SavingsMMDA(name=True, date=date)}={c2}, {self.SavingsOther(name=True, date=date)}={f2}, on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                    print(self.messages['Memoranda2'])
                return total

            class TimeDeposits:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.LessThan250k = self.LessThan250k(self)
                    self.MoreThan250k = self.MoreThan250k(self)
                    self.flags = {}
                    self.messages = {}

                def LessThan100k(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total Time Deposits of less than $100,000'
                    if name:
                        return self.name
                    return row['RCON6648']

                def MoreThan100kLessThan250k(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total Time Deposits of $100,000 through $250,000'
                    if name:
                        return self.name
                    return row['RCONJ473'] - row['RCON6648']

                class LessThan250k:

                    def __init__(self, parent):
                        self.parent = parent
                        self.root = parent.root
                        self.row = self.root.row
                        self.flags = {}
                        self.messages = {}

                    def ReportedTotal(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        return row['RCONJ473']

                    def EffectiveThreeMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if self.root.ReportingDate(date=date) >= 20170331:
                            return self.ThreeMonths(date=date)
                        return row['RCONA579']

                    def EffectiveTwelveMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if self.root.ReportingDate(date=date) >= 20170331:
                            return self.TwelveMonths(date=date)
                        return row['RCONA580']

                    def EffectiveThreeYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if self.root.ReportingDate(date=date) >= 20170331:
                            return self.ThreeYears(date=date)
                        return row['RCONA581']

                    def EffectiveOverThreeYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if self.root.ReportingDate(date=date) >= 20170331:
                            return self.OverThreeYears(date=date)
                        return row['RCONA582']

                    def Total(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of less than $250,000'
                        if name:
                            return self.name
                        total = row['RCONJ473']
                        i1 = self.ThreeMonths(date=date)
                        u1 = self.TwelveMonths(date=date)
                        s1 = self.ThreeYears(date=date)
                        c1 = self.OverThreeYears(date=date)
                        i2 = self.parent.LessThan100k(date=date)
                        u2 = self.parent.MoreThan100kLessThan250k(date=date)
                        comp1 = i1 + u1 + s1 + c1
                        comp2 = i2 + u2
                        difference1 = total - comp1
                        difference2 = total - comp2
                        self.flags['Total'] = False
                        self.flags['Maturity'] = False
                        self.messages['Total'] = None
                        self.messages['Maturity'] = None
                        self.name = 'Total Non-Transaction Deposits of Less Than $250,000'
                        if total != comp1:
                            self.flags['Maturity'] = True
                            self.messages['Maturity'] = f'{self.Total(name=True, date=date)}: {total} does not equal {comp1} by {difference1} in {self.Total(name=True, date=date)}: {self.ThreeMonths(name=True, date=date)}={i1}, {self.TwelveMonths(name=True, date=date)}={u1}, {self.ThreeYears(name=True, date=date)}={s1}, {self.OverThreeYears(name=True, date=date)}={c1}, on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                            print(self.messages['Maturity'])
                        if total != comp2:
                            self.flags['Total'] = True
                            self.messages['Total'] = f'{self.Total(name=True, date=date)}: {total} does not equal {comp2} by {difference2} in {self.Total(name=True, date=date)}: {self.parent.LessThan100k(name=True, date=date)}={i2}, {self.parent.MoreThan100kLessThan250k(name=True, date=date)}={u2}, on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                            print(self.messages['Total'])
                        return total

                    def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of less than $250,000 with maturity and repricing data three months or less'
                        if name:
                            return self.name
                        return row['RCONHK07']

                    def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of less than $250,000 with maturity and repricing data over three months through 12 months'
                        if name:
                            return self.name
                        return row['RCONHK08']

                    def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of less than $250,000 with maturity and repricing data over one year through three years'
                        if name:
                            return self.name
                        return row['RCONHK09']

                    def OverThreeYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of less than $250,000 with maturity and repricing data over three years'
                        if name:
                            return self.name
                        return row['RCONHK10']

                class MoreThan250k:

                    def __init__(self, parent):
                        self.parent = parent
                        self.root = parent.root
                        self.row = self.root.row
                        self.flags = {}
                        self.messages = {}

                    def ReportedTotal(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        return row['RCONJ474']

                    def Total(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of more than $250,000'
                        if name:
                            return self.name
                        return row['RCONJ474']

                    def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of more than $250,000 with maturity and repricing data three months or less'
                        if name:
                            return self.name
                        return row['RCONHK12']

                    def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of more than $250,000 with maturity and repricing data over three months through 12 months'
                        if name:
                            return self.name
                        return row['RCONHK13']

                    def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of more than $250,000 with maturity and repricing data over one year through three years'
                        if name:
                            return self.name
                        return row['RCONHK14']

                    def OverThreeYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of more than $250,000 with maturity and repricing data over three years'
                        if name:
                            return self.name
                        return row['RCONHK15']

            def SavingsMMDA(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Money Market Deposit Accounts (MMDAs)'
                if name:
                    return self.name
                return row['RCON6810']

            def SavingsOther(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Other Savings Deposits (excludes MMDAs)'
                if name:
                    return self.name
                return row['RCON0352']

            def SavingsTotal(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return self.SavingsMMDA(date=date) + self.SavingsOther(date=date)

    class OtherLiabilities:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.flags = {}
            self.messages = {}

        def InterestAccrued(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Interest Accrued and Unpaid on Deposits in Domestic Offices'
            if name:
                return self.name
            return row['RCON3645']

        def ExpensesAccruedOther(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Other expenses accrued and unpaid (includes accrued income taxes (payable))'
            if name:
                return self.name
            return row['RCFD3646']

        def DTLsNet(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Net deferred tax liabilities'
            if name:
                return self.name
            return row['RCFD3049']

        def CreditLosses(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Allowance for Credit Losses on off-balanace sheet credit exposures'
            if name:
                return self.name
            return row['RCFDB557']

        def AllOtherLiabilities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'All Other Liabilities'
            if name:
                return self.name
            return row['RCFD2938']

        def Total(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Other Liabilities Total from Schedule RC-G'
            if name:
                return self.name
            return row['RCFD2930']

    class DerivativesOffBalanceSheet:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.CreditDerivatives = self.CreditDerivatives(self)
            self.OtherDerivatives = self.OtherDerivatives(self)
            self.flags = {}
            self.messages = {}

        class CreditDerivatives:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.SoldProtection = self.SoldProtection(self)
                self.PurchasedProtection = self.PurchasedProtection(self)
                self.flags = {}
                self.messages = {}

            class SoldProtection:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.Notional = self.Notional(self)
                    self.flags = {}
                    self.messages = {}

                def CDS(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of sold protection in credit derivatives: Credit default swaps'
                    if name:
                        return self.name
                    return row['RCFDC968']

                def TotalReturnSwaps(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of sold protection in credit derivatives: Total return swaps'
                    if name:
                        return self.name
                    return row['RCFDC970']

                def CreditOptions(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts: Credit Options'
                    if name:
                        return self.name
                    return row['RCFDC972']

                def OtherCreditDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of sold protection in credit derivatives: Other credit derivatives'
                    if name:
                        return self.name
                    return row['RCFDC974']

                class Notional:

                    def __init__(self, parent):
                        self.parent = parent
                        self.root = parent.root
                        self.row = self.root.row
                        self.flags = {}
                        self.messages = {}

                    def Total(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Notional amounts of sold protection in credit derivatives'
                        if name:
                            return self.name
                        notional = self.parent.CDS(date=date) + self.parent.TotalReturnSwaps(date=date) + self.parent.CreditOptions(date=date) + self.parent.OtherCreditDerivatives(date=date)
                        u1 = self.parent.CDS(name, date=date)
                        u2 = self.parent.TotalReturnSwaps(name, date=date)
                        u3 = self.parent.CreditOptions(name, date=date)
                        u4 = self.parent.OtherCreditDerivatives(name, date=date)
                        v1 = self.SubInvestmentGrade(name, date=date)
                        v2 = self.InvestmentGrade(name, date=date)
                        comp1 = u1 + u2 + u3 + u4
                        comp2 = v1 + v2
                        difference1 = notional - comp1
                        difference2 = notional - comp2
                        self.flags['Notional'] = False
                        self.flags['Rating'] = False
                        self.messages['Notional'] = None
                        self.messages['Rating'] = None
                        if difference1 != 0:
                            self.flags['Notional'] = True
                            self.messages['Notional'] = f'{self.name}: {notional} does not equal {comp1} by {difference1}'
                            print(self.messages['Notional'])
                        if difference2 != 0:
                            self.flags['Rating'] = True
                            self.messages['Rating'] = f'{self.name}: {notional} does not equal {comp2} by {difference2}'
                            print(self.messages['Rating'])
                        return notional

                    def TwelveMonths(self, rating, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if rating == 'IG':
                            self.name = 'Total notional amounts of investment grade sold protection in credit derivatives with a remaining maturity of one year or less'
                            if name:
                                return self.name
                            return row['RCFDG406']
                        elif rating == 'SubIG':
                            self.name = 'Total notional amounts of subinvestment grade sold protection in credit derivatives with a remaining maturity of one year or less'
                            if name:
                                return self.name
                            return row['RCFDG409']

                    def FiveYears(self, rating, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if rating == 'IG':
                            self.name = 'Total notional amounts of investment grade sold protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCFDG407']
                        elif rating == 'SubIG':
                            self.name = 'Total notional amounts of subinvestment grade sold protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCFDG410']

                    def OverFiveYears(self, rating, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if rating == 'IG':
                            self.name = 'Total notional amounts of investment grade sold protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCFDG408']
                        elif rating == 'SubIG':
                            self.name = 'Total notional amounts of subinvestment grade sold protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCFDG411']

                    def InvestmentGrade(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total notional amounts of subinvestment grade purchased protection credit derivatives'
                        if name:
                            return self.name
                        return self.TwelveMonths(rating='IG', name=False, date=date) + self.FiveYears(rating='IG', name=False, date=date) + self.OverFiveYears(rating='IG', name=False, date=date)

                    def SubInvestmentGrade(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total notional amounts of subinvestment grade purchased protection credit derivatives'
                        if name:
                            return self.name
                        return self.TwelveMonths(rating='SubIG', name=False, date=date) + self.FiveYears(rating='SubIG', name=False, date=date) + self.OverFiveYears(rating='SubIG', name=False, date=date)

                def MarketRiskRule(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of sold protection in CDSs by regulatory capital treatment: Market Risk Rule positions'
                    if name:
                        return self.name
                    total = row['RCFDG401']
                    u1 = self.CDS(name, date=date)
                    u2 = self.TotalReturnSwaps(name, date=date)
                    u3 = self.CreditOptions(name, date=date)
                    u4 = self.OtherCreditDerivatives(name, date=date)
                    comp1 = u1 + u2 + u3 + u4
                    difference1 = total - comp1
                    self.flags['MarketRiskRule'] = False
                    self.messages['MarketRiskRule'] = None
                    if difference1 > 0:
                        self.flags['MarketRiskRule'] = True
                        self.messages['MarketRiskRule'] = f'{self.MarketRiskRule(name=True, date=date)}: {total} does not equal {comp1} by {difference1} check in {self.MarketRiskRule(name=True, date=date)}: {self.CDS(name=True, date=date)}={u1}, {self.TotalReturnSwaps(name=True, date=date)}={u2}, {self.CreditOptions(name=True, date=date)}={u3}, {self.OtherCreditDerivatives(name=True, date=date)}={u4}, on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                        print(self.messages['MarketRiskRule'])
                    return total

            class PurchasedProtection:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.Notional = self.Notional(self)
                    self.flags = {}
                    self.messages = {}

                def CDS(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of Purchased Protection in CDSs: Credit default swaps'
                    if name:
                        return self.name
                    return row['RCFDC969']

                def TotalReturnSwaps(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of Purchased Protection in CDSs: Total return swaps'
                    if name:
                        return self.name
                    return row['RCFDC971']

                def CreditOptions(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of Purchased Protection in CDSs: Credit Options'
                    if name:
                        return self.name
                    return row['RCFDC973']

                def OtherCreditDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of Purchased Protection in CDSs: Other credit derivatives'
                    if name:
                        return self.name
                    return row['RCFDC975']

                class Notional:

                    def __init__(self, parent):
                        self.parent = parent
                        self.root = parent.root
                        self.row = self.root.row
                        self.flags = {}
                        self.messages = {}

                    def Total(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Notional amounts of purchased protection in CDSs'
                        if name:
                            return self.name
                        notional = self.parent.CDS(date=date) + self.parent.TotalReturnSwaps(date=date) + self.parent.CreditOptions(date=date) + self.parent.OtherCreditDerivatives(date=date)
                        u1 = self.parent.CDS(name, date=date)
                        u2 = self.parent.TotalReturnSwaps(name, date=date)
                        u3 = self.parent.CreditOptions(name, date=date)
                        u4 = self.parent.OtherCreditDerivatives(name, date=date)
                        v1 = self.SubInvestmentGrade(name, date=date)
                        v2 = self.InvestmentGrade(name, date=date)
                        comp1 = u1 + u2 + u3 + u4
                        comp2 = v1 + v2
                        difference1 = notional - comp1
                        difference2 = notional - comp2
                        self.flags['Notional'] = False
                        self.flags['Rating'] = False
                        self.messages['Notional'] = None
                        self.messages['Rating'] = None
                        if difference1 != 0:
                            self.flags['Notional'] = True
                            self.messages['Notional'] = f'{self.name}: {notional} does not equal {comp1} by {difference1}'
                            print(self.messages['Notional'])
                        if difference2 != 0:
                            self.flags['Rating'] = True
                            self.messages['Rating'] = f'{self.name}: {notional} does not equal {comp2} by {difference2}'
                            print(self.messages['Rating'])
                        return notional

                    def TwelveMonths(self, rating='IG', name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if rating == 'IG':
                            self.name = 'Total notional amounts of investment grade purchased protection in credit derivatives with a remaining maturity of one year or less'
                            if name:
                                return self.name
                            return row['RCFDG412']
                        elif rating == 'SubIG':
                            self.name = 'Total notional amounts of subinvestment grade purchased protection in credit derivatives with a remaining maturity of one year or less'
                            if name:
                                return self.name
                            return row['RCFDG415']

                    def FiveYears(self, rating, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if rating == 'IG':
                            self.name = 'Total notional amounts of investment grade purchased protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCFDG413']
                        elif rating == 'SubIG':
                            self.name = 'Total notional amounts of subinvestment grade purchased protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCFDG416']

                    def OverFiveYears(self, rating, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if rating == 'IG':
                            self.name = 'Total notional amounts of investment grade purchased protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCFDG414']
                        elif rating == 'SubIG':
                            self.name = 'Total notional amounts of subinvestment grade purchased protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCFDG417']

                    def InvestmentGrade(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total notional amounts of subinvestment grade purchased protection credit derivatives'
                        if name:
                            return self.name
                        return self.TwelveMonths(rating='IG', name=False, date=date) + self.FiveYears(rating='IG', name=False, date=date) + self.OverFiveYears(rating='IG', name=False, date=date)

                    def SubInvestmentGrade(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total notional amounts of subinvestment grade purchased protection credit derivatives'
                        if name:
                            return self.name
                        return self.TwelveMonths(rating='SubIG', name=False, date=date) + self.FiveYears(rating='SubIG', name=False, date=date) + self.OverFiveYears(rating='SubIG', name=False, date=date)

                def MarketRiskRule(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of Purchased Protection in CDSs by regulatory capital treatment: Market Risk Rule positions'
                    if name:
                        return self.name
                    MRR = row['RCFDG402']
                    u1 = self.CDS(name, date=date)
                    u2 = self.TotalReturnSwaps(name, date=date)
                    u3 = self.CreditOptions(name, date=date)
                    u4 = self.OtherCreditDerivatives(name, date=date)
                    comp1 = u1 + u2 + u3 + u4
                    difference1 = MRR - comp1
                    self.flags['MarketRiskRule'] = False
                    self.messages['MarketRiskRule'] = None
                    if difference1 > 0:
                        self.flags['MarketRiskRule'] = True
                        self.messages['MarketRiskRule'] = f'{self.MarketRiskRule(name=True, date=date)}: {MRR} does not equal {comp1} by {difference1} check in {self.MarketRiskRule(name=True, date=date)}: {self.CDS(name=True, date=date)}={u1}, {self.TotalReturnSwaps(name=True, date=date)}={u2}, {self.CreditOptions(name=True, date=date)}={u3}, {self.OtherCreditDerivatives(name=True, date=date)}={u4}, on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                        print(self.messages['MarketRiskRule'])
                    return MRR

        class OtherDerivatives:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.HeldForTrading = self.HeldForTrading(self)
                self.NotHeldForTrading = self.NotHeldForTrading(self)
                self.Futures = self.Futures(self)
                self.Forwards = self.Forwards(self)
                self.ETDOptions = self.ETDOptions(self)
                self.OTCOptions = self.OTCOptions(self)
                self.Swaps = self.Swaps(self)
                self.flags = {}
                self.messages = {}

            class HeldForTrading:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of derivatives contracts held for trading'
                    if name:
                        return self.name
                    return self.InterestRates(name, date=date) + self.ForeignExchange(name, date=date) + self.EquityDerivatives(name, date=date) + self.CommoditiesOther(name, date=date)

                def InterestRates(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of interest rate derivative contracts held for trading'
                    if name:
                        return self.name
                    return row['RCFDA126']

                def ForeignExchange(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of foreign exchange derivative contracts held for trading'
                    if name:
                        return self.name
                    return row['RCFDA127']

                def EquityDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of equity derivative contracts held for trading'
                    if name:
                        return self.name
                    return row['RCFD8723']

                def CommoditiesOther(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of commodities and other derivative contracts held for trading'
                    if name:
                        return self.name
                    return row['RCFD8724']

            class NotHeldForTrading:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of derivatives contracts not held for trading'
                    if name:
                        return self.name
                    return self.InterestRates(name, date=date) + self.ForeignExchange(name, date=date) + self.EquityDerivatives(name, date=date) + self.CommoditiesOther(name, date=date)

                def InterestRates(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of interest rate derivative contracts not held for trading'
                    if name:
                        return self.name
                    return row['RCFD8725']

                def ForeignExchange(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of foreign exchange derivative contracts not held for trading'
                    if name:
                        return self.name
                    return row['RCFD8726']

                def EquityDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of equity derivative contracts not held for trading'
                    if name:
                        return self.name
                    return row['RCFD8727']

                def CommoditiesOther(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of commodities and other derivative contracts not held for trading'
                    if name:
                        return self.name
                    return row['RCFD8728']

            class Futures:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of futures (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(name, date=date) + self.ForeignExchange(name, date=date) + self.EquityDerivatives(name, date=date) + self.CommoditiesOther(name, date=date)

                def InterestRates(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Futures on Interest Rates Contracts'
                    if name:
                        return self.name
                    return row['RCFD8693']

                def ForeignExchange(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Futures on foreign exchange contracts'
                    if name:
                        return self.name
                    return row['RCFD8694']

                def EquityDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Futures on Equity Derivatives Contracts'
                    if name:
                        return self.name
                    return row['RCFD8695']

                def CommoditiesOther(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Futures on Commodities and Other Contracts'
                    if name:
                        return self.name
                    return row['RCFD8696']

            class Forwards:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of Forwards (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(name, date=date) + self.ForeignExchange(name, date=date) + self.EquityDerivatives(name, date=date) + self.CommoditiesOther(name, date=date)

                def InterestRates(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Forwards on Interest Rates Contracts'
                    if name:
                        return self.name
                    return row['RCFD8697']

                def ForeignExchange(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Forwards on foreign exchange contracts'
                    if name:
                        return self.name
                    return row['RCFD8698']

                def EquityDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Forwards on Equity Derivatives Contracts'
                    if name:
                        return self.name
                    return row['RCFD8699']

                def CommoditiesOther(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Forwards on Commodities and Other Contracts'
                    if name:
                        return self.name
                    return row['RCFD8700']

            class ETDOptions:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of exchange-traded derivatives contracts (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.TotalWritten(name, date=date) + self.TotalPurchased(name, date=date)

                def TotalWritten(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of written option exchange-traded derivatives contracts (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(claim='written', date=date) + self.ForeignExchange(claim='written', date=date) + self.EquityDerivatives(claim='written', date=date) + self.CommoditiesOther(claim='written', date=date)

                def TotalPurchased(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of purchased option exchange-traded derivatives contracts (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(claim='purchased', date=date) + self.ForeignExchange(claim='purchased', date=date) + self.EquityDerivatives(claim='purchased', date=date) + self.CommoditiesOther(claim='purchased', date=date)

                def InterestRates(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Options on Interest Rates Contracts'
                        if name:
                            return self.name
                        return row['RCFD8701']
                    elif claim == 'purchased':
                        self.name = 'Purchased Options on Interest Rates Contracts'
                        if name:
                            return self.name
                        return row['RCFD8705']

                def ForeignExchange(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Options on foreign exchange contracts'
                        if name:
                            return self.name
                        return row['RCFD8702']
                    elif claim == 'purchased':
                        self.name = 'Purchased Options on foreign exchange contracts'
                        if name:
                            return self.name
                        return row['RCFD8706']

                def EquityDerivatives(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Options on Equity Derivatives Contracts'
                        if name:
                            return self.name
                        return row['RCFD8703']
                    elif claim == 'purchased':
                        self.name = 'Written Options on Equity Derivatives Contracts'
                        if name:
                            return self.name
                        return row['RCFD8707']

                def CommoditiesOther(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Purchased Options on Commodities and Other Contracts'
                        if name:
                            return self.name
                        return row['RCFD8704']
                    elif claim == 'purchased':
                        self.name = 'Purchased Options on Commodities and Other Contracts'
                        if name:
                            return self.name
                        return row['RCFD8708']

            class OTCOptions:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of over-the-counter options (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.TotalWritten(name, date=date) + self.TotalPurchased(name, date=date)

                def TotalWritten(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of over-the-counter written options (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(claim='written', date=date) + self.ForeignExchange(claim='written', date=date) + self.EquityDerivatives(claim='written', date=date) + self.CommoditiesOther(claim='written', date=date)

                def TotalPurchased(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of over-the-counter purchased options (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(claim='purchased', date=date) + self.ForeignExchange(claim='purchased', date=date) + self.EquityDerivatives(claim='purchased', date=date) + self.CommoditiesOther(claim='purchased', date=date)

                def InterestRates(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Over-the-counter Options on Interest Rates Contracts'
                        if name:
                            return self.name
                        return row['RCFD8709']
                    elif claim == 'purchased':
                        self.name = 'Purchased Over-the-counter Options on Interest Rates Contracts'
                        if name:
                            return self.name
                        return row['RCFD8713']

                def ForeignExchange(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Over-the-counter Options on foreign exchange contracts'
                        if name:
                            return self.name
                        return row['RCFD8710']
                    elif claim == 'purchased':
                        self.name = 'Purchased Over-the-counter Options on foreign exchange contracts'
                        if name:
                            return self.name
                        return row['RCFD8714']

                def EquityDerivatives(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Over-the-counter Options on Equity Derivatives Contracts'
                        if name:
                            return self.name
                        return row['RCFD8711']
                    elif claim == 'purchased':
                        self.name = 'Purchased Over-the-counter Options on Equity Derivatives Contracts'
                        if name:
                            return self.name
                        return row['RCFD8715']

                def CommoditiesOther(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Over-the-counter Options on Commodities and Other Contracts'
                        if name:
                            return self.name
                        return row['RCFD8712']
                    elif claim == 'purchased':
                        self.name = 'Purchased Over-the-counter Options on Commodities and Other Contracts'
                        if name:
                            return self.name
                        return row['RCFD8716']

            class Swaps:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of swaps (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(name, date=date) + self.ForeignExchange(name, date=date) + self.EquityDerivatives(name, date=date) + self.CommoditiesOther(name, date=date)

                def InterestRates(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Swaps on Interest Rates Contracts'
                    if name:
                        return self.name
                    return row['RCFD3450']

                def ForeignExchange(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Swaps on foreign exchange contracts'
                    if name:
                        return self.name
                    return row['RCFD3826']

                def EquityDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Swaps on Equity Derivatives Contracts'
                    if name:
                        return self.name
                    return row['RCFD8719']

                def CommoditiesOther(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Swaps on Commodities and Other Contracts'
                    if name:
                        return self.name
                    return row['RCFD8720']

    class NonaccrualPastDue:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.LoansAndLeaseFinancingReceivables = self.LoansAndLeaseFinancingReceivables(self)
            self.SecuredRealEstate = self.SecuredRealEstate(self)
            self.DepositoryInstitutions = self.DepositoryInstitutions(self)
            self.Individuals = self.Individuals(self)

        class LoansAndLeaseFinancingReceivables:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def Total(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: total loans and lease financing receivables (RC-N, item 8)'
                    if name:
                        return self.name
                    return row['RCFD1406']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: total loans and lease financing receivables (RC-N, item 8)'
                    if name:
                        return self.name
                    return row['RCFD1407']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: total loans and lease financing receivables (RC-N, item 8)'
                    if name:
                        return self.name
                    return row['RCFD1403']

            def GuaranteedByUSGovt(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: total loans and leases that are wholly or partially guaranteed by the U.S. Government, excluding FDIC-loss sharing agreements'
                    if name:
                        return self.name
                    return row['RCFDK036']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: total loans and leases that are wholly or partially guaranteed by the U.S. Government, excluding FDIC-loss sharing agreements'
                    if name:
                        return self.name
                    return row['RCFDK037']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: total loans and leases that are wholly or partially guaranteed by the U.S. Government, excluding FDIC-loss sharing agreements'
                    if name:
                        return self.name
                    return row['RCFDK038']

            def LoansAndLeasesHeldForSale(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: total loans and leases that are wholly or partially guaranteed by the U.S. Government, excluding FDIC-loss sharing agreements'
                    if name:
                        return self.name
                    return row['RCFDC240']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: total loans and leases that are wholly or partially guaranteed by the U.S. Government, excluding FDIC-loss sharing agreements'
                    if name:
                        return self.name
                    return row['RCFDC241']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: total loans and leases that are wholly or partially guaranteed by the U.S. Government, excluding FDIC-loss sharing agreements'
                    if name:
                        return self.name
                    return row['RCFDC226']

        class SecuredRealEstate:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.SFR = self.SFR(self)

            def ConstructionSFR(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: 1-4 family residential construction loans secured by real estate'
                    if name:
                        return self.name
                    return row['RCONF172']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: 1-4 family residential construction loans secured by real estate'
                    if name:
                        return self.name
                    return row['RCONF174']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: 1-4 family residential construction loans secured by real estate'
                    if name:
                        return self.name
                    return row['RCONF176']

            def ConstructionOther(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: 1-4 family residential construction loans secured by real estate'
                    if name:
                        return self.name
                    return row['RCONF173']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: 1-4 family residential construction loans secured by real estate'
                    if name:
                        return self.name
                    return row['RCONF175']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: 1-4 family residential construction loans secured by real estate'
                    if name:
                        return self.name
                    return row['RCONF177']

            def Farmland(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: secured by farmland in domestic offices'
                    if name:
                        return self.name
                    return row['RCON3493']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: secured by farmland in domestic offices'
                    if name:
                        return self.name
                    return row['RCON3494']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: secured by farmland in domestic offices'
                    if name:
                        return self.name
                    return row['RCON3495']

            class SFR:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row

                def OpenEndRevolving(self, column, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if column == 'A' or column == 'past due 30 days':
                        self.name = 'Past due by 30 days to 89 days: revolving, open-end loans secured by 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCON5398']
                    if column == 'B' or column == 'past due 90 days':
                        self.name = 'Past due by 90 or more: revolving, open-end loans secured by 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCON5399']
                    if column == 'C' or column == 'nonaccrual':
                        self.name = 'nonaccrual: revolving, open-end loans secured by 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCON5400']

                def ClosedEndFirstLiens(self, column, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if column == 'A' or column == 'past due 30 days':
                        self.name = 'Past due by 30 days to 89 days: closed-end loans secured by first lien 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCONC236']
                    if column == 'B' or column == 'past due 90 days':
                        self.name = 'Past due by 90 or more: closed-end loans secured by first lien 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCONC237']
                    if column == 'C' or column == 'nonaccrual':
                        self.name = 'nonaccrual: closed-end loans secured by first lien 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCONC229']

                def ClosedEndJuniorLiens(self, column, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if column == 'A' or column == 'past due 30 days':
                        self.name = 'Past due by 30 days to 89 days: closed-end loans secured by junior lien 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCONC238']
                    if column == 'B' or column == 'past due 90 days':
                        self.name = 'Past due by 90 or more: closed-end loans secured by junior lien 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCONC239']
                    if column == 'C' or column == 'nonaccrual':
                        self.name = 'nonaccrual: closed-end loans secured by junior lien 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCONC230']

            def SecuredMultifamily(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: secured by multifamily (5 or more) residential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCON3499']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: secured by multifamily (5 or more) residential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCON3500']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: secured by multifamily (5 or more) residential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCON3501']

            def SecuredNonfarmOwner(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: secured by owner-occupied nonfarm nonresidential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF178']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: secured by owner-occupied nonfarm nonresidential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF180']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: secured by owner-occupied nonfarm nonresidential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF182']

            def SecuredNonfarmOther(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: secured by other nonfarm nonresidential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF179']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: secured by other nonfarm nonresidential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF181']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: secured by other nonfarm nonresidential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF183']

        class DepositoryInstitutions:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def USBanksTotal(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: Loans to U.S. banks and other depository institutions in the U.S.'
                    if name:
                        return self.name
                    return row['RCFD5377']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: Loans to U.S. banks and other depository institutions in the U.S.'
                    if name:
                        return self.name
                    return row['RCFD5378']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: Loans to U.S. banks and other depository institutions in the U.S.'
                    if name:
                        return self.name
                    return row['RCFD5379']

            def ForeignBanks(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: Loans to foreign banks'
                    if name:
                        return self.name
                    return row['RCFD5380']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: Loans to foreign banks'
                    if name:
                        return self.name
                    return row['RCFD5381']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: Loans to foreign banks'
                    if name:
                        return self.name
                    return row['RCFD5382']

        def FinanceAgricultural(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A' or column == 'past due 30 days':
                self.name = 'Past due by 30 days to 89 days: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCFD1594']
            if column == 'B' or column == 'past due 90 days':
                self.name = 'Past due by 90 or more: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCFD1597']
            if column == 'C' or column == 'nonaccrual':
                self.name = 'nonaccrual: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCFD1583']

        def CommercialAndIndustrial(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A' or column == 'past due 30 days':
                self.name = 'Past due by 30 days to 89 days: commerical and industrial loans in domestic offices'
                if name:
                    return self.name
                return row['RCFD1251']
            if column == 'B' or column == 'past due 90 days':
                self.name = 'Past due by 90 or more: commerical and industrial loans in domestic offices'
                if name:
                    return self.name
                return row['RCFD1252']
            if column == 'C' or column == 'nonaccrual':
                self.name = 'nonaccrual: commerical and industrial loans in domestic offices'
                if name:
                    return self.name
                return row['RCFD1253']

        class Individuals:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def CreditCards(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: Loans to individuals for credit card lines'
                    if name:
                        return self.name
                    return row['RCFDB575']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: Loans to individuals for credit card lines'
                    if name:
                        return self.name
                    return row['RCFDB576']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: Loans to individuals for credit card lines'
                    if name:
                        return self.name
                    return row['RCFDB577']

            def AutomobileLoans(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: Loans to individuals for automobiles'
                    if name:
                        return self.name
                    return row['RCFDK213']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: Loans to individuals for automobiles'
                    if name:
                        return self.name
                    return row['RCFDK214']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: Loans to individuals for automobiles'
                    if name:
                        return self.name
                    return row['RCFDK215']

            def OtherLoans(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: Loans to individuals for other purposes (includes RC-C Part I, item 6.c and 6.d)'
                    if name:
                        return self.name
                    return row['RCFDK216']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: Loans to individuals for other purposes (includes RC-C Part I, item 6.c and 6.d)'
                    if name:
                        return self.name
                    return row['RCFDK217']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: Loans to individuals for other purposes (includes RC-C Part I, item 6.c and 6.d)'
                    if name:
                        return self.name
                    return row['RCFDK218']

        def ForeignGovt(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A' or column == 'past due 30 days':
                self.name = 'Past due by 30 days to 89 days: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCFD5389']
            if column == 'B' or column == 'past due 90 days':
                self.name = 'Past due by 90 or more: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCFD5390']
            if column == 'C' or column == 'nonaccrual':
                self.name = 'nonaccrual: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCFD5391']

        def AllOtherLoans(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A' or column == 'past due 30 days':
                self.name = 'Past due by 30 days to 89 days: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCFD5459']
            if column == 'B' or column == 'past due 90 days':
                self.name = 'Past due by 90 or more: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCFD5460']
            if column == 'C' or column == 'nonaccrual':
                self.name = 'nonaccrual: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCFD5461']

        def LeaseFinancingReceivables(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A' or column == 'past due 30 days':
                self.name = 'Past due by 30 days to 89 days: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCFDF166'] + row['RCFDF169']
            if column == 'B' or column == 'past due 90 days':
                self.name = 'Past due by 90 or more: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCFDF167'] + row['RCFDF170']
            if column == 'C' or column == 'nonaccrual':
                self.name = 'nonaccrual: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCFDF168'] + row['RCFDF171']

    class DepositInsurance:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.flags = {}
            self.messages = {}

        def Section3IDeposits(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Total deposit liabilities before exclusions (gross) defined in Section 3(I) of the Federal Deposit Insurance Act and FDIC regulations'
            if name:
                return self.name
            return row['RCFDF236']

        def TotalAllowableExclusions(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Total allowable exclusions, including interest acrrued and unpaid on allowable exclusions'
            if name:
                return self.name
            return row['RCFDF237']

        def TotalForeignDeposits(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Total deposits in foreign offices, Edge and Agreement subsidiaries, and IBFs'
            if name:
                return self.name
            return row['RCFN2200']

    class MeasuredAtFV:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.TradingAssets = self.TradingAssets(self)
            self.TradingLiabilities = self.TradingLiabilities(self)
            self.flags = {}
            self.messages = {}

        def AFSSecurities(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Available-for-Sale debt securities and equity securities with readily determinable fair value not held for trading, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCFDJA36']
            elif column == 'B':
                self.name = 'Available-for-Sale debt securities and equity securities with readily determinable fair value not held for trading, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCFDG474']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Available-for-Sale debt securities and equity securities with readily determinable fair value not held for trading, (Column C)'
                if name:
                    return self.name
                return row['RCFDG475']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Available-for-Sale debt securities and equity securities with readily determinable fair value not held for trading, (Column D)'
                if name:
                    return self.name
                return row['RCFDG476']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Available-for-Sale debt securities and equity securities with readily determinable fair value not held for trading, (Column E)'
                if name:
                    return self.name
                return row['RCFDG477']

        def FederalFundsSold(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Federal funds sold and securities purchased under agreements to resell, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCFDG478']
            elif column == 'B':
                self.name = 'Federal funds sold and securities purchased under agreements to resell, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCFDG479']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Federal funds sold and securities purchased under agreements to resell, (Column C)'
                if name:
                    return self.name
                return row['RCFDG480']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Federal funds sold and securities purchased under agreements to resell, (Column D)'
                if name:
                    return self.name
                return row['RCFDG481']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Federal funds sold and securities purchased under agreements to resell, (Column E)'
                if name:
                    return self.name
                return row['RCFDG482']

        def LoansAndLeasesHeldForSale(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Loans and leases held for sale, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCFDG483']
            elif column == 'B':
                self.name = 'Loans and leases held for sale, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCFDG484']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Loans and leases held for sale, (Column C)'
                if name:
                    return self.name
                return row['RCFDG485']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Loans and leases held for sale, (Column D)'
                if name:
                    return self.name
                return row['RCFDG486']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Loans and leases held for sale, (Column E)'
                if name:
                    return self.name
                return row['RCFDG487']

        def LoansAndLeasesHeldForInvestment(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Loans and leases held for investment, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCFDG488']
            elif column == 'B':
                self.name = 'Loans and leases held for investment, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCFDG489']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Loans and leases held for investment, (Column C)'
                if name:
                    return self.name
                return row['RCFDG490']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Loans and leases held for investment, (Column D)'
                if name:
                    return self.name
                return row['RCFDG491']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Loans and leases held for investment, (Column E)'
                if name:
                    return self.name
                return row['RCFDG492']

        class TradingAssets:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def Total(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A':
                    self.name = '([calculated] item 5.a & 5.b) Trading assets: derivative assets, (Column A) Reported on Schedule RC'
                    if name:
                        return self.name
                    return row['RCFD3543'] + row['RCFDG497']
                elif column == 'B':
                    self.name = '([calculated] item 5.a & 5.b) Trading assets: derivative assets, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                    if name:
                        return self.name
                    return row['RCFDG493'] + row['RCFDG498']
                elif column == 'C' or column == 'Level 1':
                    self.name = '([calculated] item 5.a & 5.b) Level 1 Fair Value Measurement: Trading assets: derivative assets, (Column C)'
                    if name:
                        return self.name
                    return row['RCFDG494'] + row['RCFDG499']
                elif column == 'D' or column == 'Level 2':
                    self.name = '([calculated] item 5.a & 5.b) Level 2 Fair Value Measurement: Trading assets: derivative assets, (Column D)'
                    if name:
                        return self.name
                    return row['RCFDG495'] + row['RCFDG500']
                elif column == 'E' or column == 'Level 3':
                    self.name = '([calculated] item 5.a & 5.b) Level 3 Fair Value Measurement: Trading assets: derivative assets, (Column E)'
                    if name:
                        return self.name
                    return row['RCFDG496'] + row['RCFDG501']

            def Derivatives(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A':
                    self.name = 'Trading assets: derivative assets, (Column A) Reported on Schedule RC'
                    if name:
                        return self.name
                    return row['RCFD3543']
                elif column == 'B':
                    self.name = 'Trading assets: derivative assets, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                    if name:
                        return self.name
                    return row['RCFDG493']
                elif column == 'C' or column == 'Level 1':
                    self.name = 'Level 1 Fair Value Measurement: Trading assets: derivative assets, (Column C)'
                    if name:
                        return self.name
                    return row['RCFDG494']
                elif column == 'D' or column == 'Level 2':
                    self.name = 'Level 2 Fair Value Measurement: Trading assets: derivative assets, (Column D)'
                    if name:
                        return self.name
                    return row['RCFDG495']
                elif column == 'E' or column == 'Level 3':
                    self.name = 'Level 3 Fair Value Measurement: Trading assets: derivative assets, (Column E)'
                    if name:
                        return self.name
                    return row['RCFDG496']

            def OtherAssets(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A':
                    self.name = 'Trading assets: other assets, (Column A) Reported on Schedule RC'
                    if name:
                        return self.name
                    return row['RCFDG497']
                elif column == 'B':
                    self.name = 'Trading assets: other assets, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                    if name:
                        return self.name
                    return row['RCFDG498']
                elif column == 'C' or column == 'Level 1':
                    self.name = 'Level 1 Fair Value Measurement: Trading assets: other assets, (Column C)'
                    if name:
                        return self.name
                    return row['RCFDG499']
                elif column == 'D' or column == 'Level 2':
                    self.name = 'Level 2 Fair Value Measurement: Trading assets: other assets, (Column D)'
                    if name:
                        return self.name
                    return row['RCFDG500']
                elif column == 'E' or column == 'Level 3':
                    self.name = 'Level 3 Fair Value Measurement: Trading assets: other assets, (Column E)'
                    if name:
                        return self.name
                    return row['RCFDG501']

        def AllOtherAssets(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'All other assets, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCFDG391']
            elif column == 'B':
                self.name = 'All other assets, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCFDG392']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: All other assets, (Column C)'
                if name:
                    return self.name
                return row['RCFDG395']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: All other assets, (Column D)'
                if name:
                    return self.name
                return row['RCFDG396']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: All other assets, (Column E)'
                if name:
                    return self.name
                return row['RCFDG804']

        def DepositLiabilities(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Deposit liabilities, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCFDF252']
            elif column == 'B':
                self.name = 'Deposit liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCFDF686']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Deposit liabilities, (Column C)'
                if name:
                    return self.name
                return row['RCFDF694']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Deposit liabilities, (Column D)'
                if name:
                    return self.name
                return row['RCFDF253']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Deposit liabilities, (Column E)'
                if name:
                    return self.name
                return row['RCFDF254']

        def FederalFundsPurchased(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Federal funds purchased and securities sold with agreements to repurchase, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCFDG507']
            elif column == 'B':
                self.name = 'Federal funds purchased and securities sold with agreements to repurchase, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCFDG508']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Federal funds purchased and securities sold with agreements to repurchase, (Column C)'
                if name:
                    return self.name
                return row['RCFDG509']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Federal funds purchased and securities sold with agreements to repurchase, (Column D)'
                if name:
                    return self.name
                return row['RCFDG510']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Federal funds purchased and securities sold with agreements to repurchase, (Column E)'
                if name:
                    return self.name
                return row['RCFDG511']

        class TradingLiabilities:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def Total(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A':
                    self.name = '([calculated] item 10.a & 10.b) Trading liabilities: derivative liabilities, (Column A) Reported on Schedule RC'
                    if name:
                        return self.name
                    return row['RCFD3547'] + row['RCFDG516']
                elif column == 'B':
                    self.name = '([calculated] item 10.a & 10.b) Trading liabilities: derivative liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                    if name:
                        return self.name
                    return row['RCFDG512'] + row['RCFDG517']
                elif column == 'C' or column == 'Level 1':
                    self.name = '([calculated] item 10.a & 10.b) Level 1 Fair Value Measurement: Trading liabilities: derivative liabilities, (Column C)'
                    if name:
                        return self.name
                    return row['RCFDG513'] + row['RCFDG518']
                elif column == 'D' or column == 'Level 2':
                    self.name = '([calculated] item 10.a & 10.b) Level 2 Fair Value Measurement: Trading liabilities: derivative liabilities, (Column D)'
                    if name:
                        return self.name
                    return row['RCFDG514'] + row['RCFDG519']
                elif column == 'E' or column == 'Level 3':
                    self.name = '([calculated] item 10.a & 10.b) Level 3 Fair Value Measurement: Trading liabilities: derivative liabilities, (Column E)'
                    if name:
                        return self.name
                    return row['RCFDG515'] + row['RCFDG520']

            def Derivatives(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A':
                    self.name = 'Trading aliabilities: derivative liabilities, (Column A) Reported on Schedule RC'
                    if name:
                        return self.name
                    return row['RCFD3547']
                elif column == 'B':
                    self.name = 'Trading liabilities: derivative liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                    if name:
                        return self.name
                    return row['RCFDG512']
                elif column == 'C' or column == 'Level 1':
                    self.name = 'Level 1 Fair Value Measurement: Trading liabilities: derivative liabilities, (Column C)'
                    if name:
                        return self.name
                    return row['RCFDG513']
                elif column == 'D' or column == 'Level 2':
                    self.name = 'Level 2 Fair Value Measurement: Trading liabilities: derivative liabilities, (Column D)'
                    if name:
                        return self.name
                    return row['RCFDG514']
                elif column == 'E' or column == 'Level 3':
                    self.name = 'Level 3 Fair Value Measurement: Trading liabilities: derivative liabilities, (Column E)'
                    if name:
                        return self.name
                    return row['RCFDG515']

            def OtherLiabilities(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A':
                    self.name = 'Trading liabilities: other liabilities, (Column A) Reported on Schedule RC'
                    if name:
                        return self.name
                    return row['RCFDG516']
                elif column == 'B':
                    self.name = 'Trading liabilities: other liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                    if name:
                        return self.name
                    return row['RCFDG517']
                elif column == 'C' or column == 'Level 1':
                    self.name = 'Level 1 Fair Value Measurement: Trading liabilities: other liabilities, (Column C)'
                    if name:
                        return self.name
                    return row['RCFDG518']
                elif column == 'D' or column == 'Level 2':
                    self.name = 'Level 2 Fair Value Measurement: Trading liabilities: other liabilities, (Column D)'
                    if name:
                        return self.name
                    return row['RCFDG519']
                elif column == 'E' or column == 'Level 3':
                    self.name = 'Level 3 Fair Value Measurement: Trading liabilities: other liabilities, (Column E)'
                    if name:
                        return self.name
                    return row['RCFDG520']

        def SubordinatedNotes(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Subordinated notes and debentures, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCFDG526']
            elif column == 'B':
                self.name = 'Subordinated notes and debentures, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCFDG527']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Subordinated notes and debentures, (Column C)'
                if name:
                    return self.name
                return row['RCFDG528']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Subordinated notes and debentures, (Column D)'
                if name:
                    return self.name
                return row['RCFDG529']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Subordinated notes and debentures, (Column E)'
                if name:
                    return self.name
                return row['RCFDG530']

        def OtherLiabilities(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'All other liabilities, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCFDG805']
            elif column == 'B':
                self.name = 'All other liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCFDG806']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: All other liabilities, (Column C)'
                if name:
                    return self.name
                return row['RCFDG807']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: All other liabilities, (Column D)'
                if name:
                    return self.name
                return row['RCFDG808']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: All other liabilities, (Column E)'
                if name:
                    return self.name
                return row['RCFDG809']

        def TotalLiabilities(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Total liabilities, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCFDG531']
            elif column == 'B':
                self.name = 'Total liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCFDG532']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Total liabilities, (Column C)'
                if name:
                    return self.name
                return row['RCFDG533']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Total liabilities, (Column D)'
                if name:
                    return self.name
                return row['RCFDG534']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Total liabilities, (Column E)'
                if name:
                    return self.name
                return row['RCFDG535']

        def MSAs(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Total liabilities, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCFDG536']
            elif column == 'B':
                self.name = 'Total liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCFDG537']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Total liabilities, (Column C)'
                if name:
                    return self.name
                return row['RCFDG538']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Total liabilities, (Column D)'
                if name:
                    return self.name
                return row['RCFDG539']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Total liabilities, (Column E)'
                if name:
                    return self.name
                return row['RCFDG540']

class CallReport_051(LagSupport):

    def __init__(self, row, history=None):
        self._init_lags(row, history)
        self.Maturities = self.Maturities(self)
        self.RegulatoryCapital = self.RegulatoryCapital(self)
        self.BalanceSheet = self.BalanceSheet(self)
        self.Securities = self.Securities(self)
        self.LoansAndLeases = self.LoansAndLeases(self)
        self.DepositLiabilities = self.DepositLiabilities(self)
        self.OtherLiabilities = self.OtherLiabilities(self)
        self.DerivativesOffBalanceSheet = self.DerivativesOffBalanceSheet(self)
        self.NonaccrualPastDue = self.NonaccrualPastDue(self)
        self.DepositInsurance = self.DepositInsurance(self)
        self.MeasuredAtFV = self.MeasuredAtFV(self)

    def _zero(self, value, name=False, *args, date='P0', **kwargs):
        row = self.get_row(date)
        return Global_uc(row)._zero(value, date=date)

    def _div(self, numerator, denominator, name=False, *args, date='P0', **kwargs):
        row = self.get_row(date)
        return Global_uc(row)._div(numerator, denominator, date=date)

    def RSSDID(self, name=False, *args, date='P0', **kwargs):
        row = self.get_row(date)
        return row['IDRSSD']

    def ReportingDate(self, name=False, *args, date='P0', **kwargs):
        row = self.get_row(date)
        return row['RCON9999']

    def Certificate(self, name=False, *args, date='P0', **kwargs):
        row = self.get_row(date)
        return row['FDIC Certificate Number']

    def Value(self, column, name=False, *args, date='P0', **kwargs):
        row = self.get_row(date)
        return row[column]

    class Maturities:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.Government = self.Government(self)
            self.ResidentialMortgage = self.ResidentialMortgage(self)

        class Government:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA549']

            def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA550']

            def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA551']

            def FiveYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA552']

            def FifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA553']

            def OverFifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA554']

            def Values(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return (self.ThreeMonths(date=date), self.TwelveMonths(date=date), self.ThreeYears(date=date), self.FiveYears(date=date), self.FifteenYears(date=date), self.OverFifteenYears(date=date))

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return sum(self.Values(date=date))

        class ResidentialMortgage:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA555']

            def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA556']

            def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA557']

            def FiveYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA558']

            def FifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA559']

            def OverFifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA560']

            def Values(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return (self.ThreeMonths(date=date), self.TwelveMonths(date=date), self.ThreeYears(date=date), self.FiveYears(date=date), self.FifteenYears(date=date), self.OverFifteenYears(date=date))

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return sum(self.Values(date=date))

        def Values(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return self.Government.Values(date=date) + self.ResidentialMortgage.Values(date=date)

    class RegulatoryCapital:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.EquityCapital = self.EquityCapital(self)
            self.CET1 = self.CET1(self)
            self.flags = {}
            self.messages = {}

        def RiskWeightedAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCOAA223']

        def TierOneCapital(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCOAP840']

        def CommonEquityTierOneCapital(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCOAP859']

        def AugmentedRiskWeightedAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            values = self.root.Maturities.Values(date=date)
            return self.RiskWeightedAssets(date=date) + (0.15 * values[5] + 0.1 * values[4] + 0.08 * values[3] + 0.15 * values[11] + 0.1 * values[10] + 0.08 * values[9])

        def ZeroRiskWeightedAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) >= 20150331:
                return row['RCOND987']
            return row['RCONB696']

        def ZeroRiskWeightExposureRatio(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            domestic = row['RCON1754'] + row['RCON1773']
            if self.root.ReportingDate(date=date) >= 20150331:
                denominator = domestic
                return safe_divide(row['RCOND962'] + row['RCOND967'], denominator)
            return safe_divide(row['RCONB603'] + row['RCONB608'], domestic)

        def RiskWeightAdjustment(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            values = self.root.Maturities.Values(date=date)
            return values[5] + values[4] + values[11] + values[10]

        def AdjustedZeroRiskWeightedAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) < 20150331:
                return self.ZeroRiskWeightedAssets(date=date)
            return self.ZeroRiskWeightedAssets(date=date) - self.ZeroRiskWeightExposureRatio(date=date) * self.RiskWeightAdjustment(date=date)

        def ZeroRiskToReportedRWA(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return safe_divide(self.ZeroRiskWeightedAssets(date=date), self.RiskWeightedAssets(date=date))

        def ZeroRiskToAugmentedRWA(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            denominator = self.AugmentedRiskWeightedAssets(date=date) if self.root.ReportingDate(date=date) >= 20150331 else self.RiskWeightedAssets(date=date)
            return safe_divide(self.ZeroRiskWeightedAssets(date=date), denominator)

        def AdjustedZeroRiskToAugmentedRWA(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            denominator = self.AugmentedRiskWeightedAssets(date=date) if self.root.ReportingDate(date=date) >= 20150331 else self.RiskWeightedAssets(date=date)
            return safe_divide(self.AdjustedZeroRiskWeightedAssets(date=date), denominator)

        def RelativeZeroRiskAdjustment(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            baseline = self.ZeroRiskToAugmentedRWA(date=date)
            if baseline == 0:
                return 0.0
            return 1.0 - safe_divide(self.AdjustedZeroRiskToAugmentedRWA(date=date), baseline)

        class EquityCapital:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.AOCI = self.AOCI(self)
                self.flags = {}
                self.messages = {}

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = '[calculated] Common stock, plus surplus, net of treasury stock + retained earnings + AOCI'
                if name:
                    return self.name
                return row['RCOAP742'] + row['RCOAKW00'] + row['RCOAB530']

            def CommonStockSurplus(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Common stock plus related surplus, net of treasury stock and unearned employee stock ownership plan shares'
                if name:
                    return self.name
                return row['RCOAP742']

            def RetainedEarnings(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Retained earnings'
                if name:
                    return self.name
                return row['RCOAKW00']

            def CECLDesignation(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'CECL transition election'
                if name:
                    return self.name
                return row['RCOAJJ29']

            class AOCI:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def BeforeAdjustments(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Accumulated other comprehensive income (AOCI)'
                    if name:
                        return self.name
                    return row['RCOAKW00']

                def OptOutElection(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'AOCI opt-out election'
                    if name:
                        return self.name
                    return row['RCOAP838']

                def AFSSecuritiesNet(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if self.OptOutElection(date=date) == 0 or self.OptOutElection(date=date) == '0':
                        self.name = 'Net unrealized gains on Available-for-Sale debt securities'
                        if name:
                            return self.name
                        return row['RCOAP844']
                    elif self.OptOutElection(date=date) == 1 or self.OptOutElection(date=date) == '1':
                        self.name = 'Net unrealized gains on Available-for-Sale debt securities'
                        if name:
                            return self.name
                        return 0.0

                def CashFlowHedgesNet(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if self.OptOutElection(date=date) == 0 or self.OptOutElection(date=date) == '0':
                        self.name = 'Accumulated net gains on cash flow hedges'
                        if name:
                            return self.name
                        return row['RCOAP846']
                    elif self.OptOutElection(date=date) == 1 or self.OptOutElection(date=date) == '1':
                        self.name = 'Accumulated net gains on cash flow hedges'
                        if name:
                            return self.name
                        return 0.0

                def DefinedBenefits(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if self.OptOutElection(date=date) == 0 or self.OptOutElection(date=date) == '0':
                        self.name = 'Accumulated net gains on cash flow hedges'
                        if name:
                            return self.name
                        return row['RCOAP847']
                    if self.OptOutElection(date=date) == 1 or self.OptOutElection(date=date) == '1':
                        self.name = 'Accumulated net gains on cash flow hedges'
                        if name:
                            return self.name
                        return 0.0

                def HTMSecuritiesNet(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if self.OptOutElection(date=date) == 0 or self.OptOutElection(date=date) == '0':
                        self.name = 'Net unrealized gains on Held-to-Maturity securities that are included in AOCI'
                        if name:
                            return self.name
                        return row['RCOAP848']
                    if self.OptOutElection(date=date) == 1 or self.OptOutElection(date=date) == '1':
                        self.name = 'Net unrealized gains on Held-to-Maturity securities that are included in AOCI'
                        if name:
                            return self.name
                        return 0.0

                def AOCICashFlowHedgesNet(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if self.OptOutElection(date=date) == 0 or self.OptOutElection(date=date) == '0':
                        self.name = 'Accumulated net gain on cash flow hedges included in AOCI'
                        if name:
                            return self.name
                        return row['RCOAP849']
                    if self.OptOutElection(date=date) == 1 or self.OptOutElection(date=date) == '1':
                        self.name = 'Accumulated net gain on cash flow hedges included in AOCI'
                        if name:
                            return self.name
                        return 0.0

        class CET1:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def MinorityInterests(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Common equity tier 1 minority interest includable in common equity tier 1 capital'
                if name:
                    return self.name
                return row['RCOAP839']

            def BeforeDeductions(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Common equity tier 1 before deductions'
                if name:
                    return self.name
                c1 = self.root.RegulatoryCapital.EquityCapital.CommonStockSurplus(date=date)
                c2 = self.root.RegulatoryCapital.EquityCapital.RetainedEarnings(date=date)
                c3 = self.root.RegulatoryCapital.EquityCapital.AOCI.BeforeAdjustments(date=date)
                c4 = self.MinorityInterests(date=date)
                comp1 = c1 + c2 + c3 + c4
                CET1 = row['RCOAP840']
                difference1 = CET1 - comp1
                self.flags['CET1BeforeDeductions'] = False
                self.messages['CET1BeforeDeductions'] = None
                if difference1 > 0:
                    self.flags['CET1BeforeDeductions'] = True
                    self.messages['CET1BeforeDeductions'] = f'{self.name}: {CET1} does not equal {comp1} by {difference1} because {self.root.RegulatoryCapital.EquityCapital.CommonStockSurplus(name=True, date=date)} = {c1}, {self.root.RegulatoryCapital.EquityCapital.RetainedEarnings(name=True, date=date)} = {c2}, {self.root.RegulatoryCapital.EquityCapital.AOCI.BeforeAdjustments(name=True, date=date)} = {c3}, {self.MinorityInterests(name=True, date=date)} = {c4} in {self.name} for IDRSSD {self.root.RSSDID(date=date)} on {self.root.ReportingDate(date=date)}'
                    print(self.messages['CET1BeforeDeductions'])
                return row['RCOAP840']

    class BalanceSheet:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.LoansAndLeaseFinancingReceivables = self.LoansAndLeaseFinancingReceivables(self)
            self.DepositDomesticOffices = self.DepositDomesticOffices(self)

        def CashAndBalancesDue(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCON0081'] + row['RCON0071']

        def TotalSecurities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) >= 20190331:
                return row['RCONJJ34'] + row['RCON1773'] + row['RCONJA22']
            else:
                return row['RCON1754'] + row['RCON1773']

        def HTMSecurities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) >= 20190331:
                return row['RCONJJ34']
            else:
                return row['RCON1754']

        def AFSSecurities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCON1773']

        class LoansAndLeaseFinancingReceivables:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def Total(self, validate=False, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                total = row['RCONB529']
                if not validate:
                    return total
                comp = self.LoansAndLeasesHeldForSale(date=date) + self.LoansAndLeasesHeldForInvestment(date=date) - self.AllowanceForCreditLossesOnLoansAndLeases(date=date)
                difference = total - comp
                self.flags['Total'] = False
                self.messages['Total'] = None
                self.name = 'Loans and Leases held for Investment, Net of Allowance (Schedule RC)'
                if total != comp:
                    self.flags['Total'] = True
                    self.messages['Total'] = f'{total} does not equal {comp} by {difference} in {self.name} for IDRSSD {self.root.RSSDID(date=date)} on {self.root.ReportingDate(date=date)}'
                    print(self.messages['Total'])
                return total

            def LoansAndLeasesHeldForSale(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCON5369']

            def LoansAndLeasesHeldForInvestment(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONB528']

            def AllowanceForCreditLossesOnLoansAndLeases(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCON3123']

            def TotalIncludingHeldForSale(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return self.LoansAndLeasesHeldForSale(date=date) + self.Total(date=date)

        def TradingAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCON3545']

        def OtherRealEstateOwned(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCON2150']

        def IntangibleAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) >= 20180630:
                return row['RCON2143']
            else:
                return row['RCON3163'] + row['RCON0426']

        def TotalAssets(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) >= 20180331:
                return row['RCON2170'] - row['RCONJA22'] + row['RCON3123']
            else:
                return row['RCON2170'] + row['RCON3123']

        def FederalFundsPurchased(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCONB993'] + row['RCONB995']

        def FederalFundsSold(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCONB987'] + row['RCONB989']

        class DepositDomesticOffices:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def NonInterestBearing(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCON6631']

            def InterestBearing(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCON6636']

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return self.NonInterestBearing(date=date) + self.InterestBearing(date=date)

        def TradingLiabilities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCON3548']

        def OtherLiabilities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCON2930']

        def OtherBorrowedMoney(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCON3190']

        def TotalLiabilities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCON2948']

        def TotalLiabilitiesIncludingAllowance(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return self.TotalLiabilities(date=date) + self.LoansAndLeaseFinancingReceivables.AllowanceForCreditLossesOnLoansAndLeases(date=date)

        def ReportedTotalEquityCapital(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCONG105']

        def TotalEquityCapital(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) >= 20180331:
                return row['RCONG105'] - row['RCONJA22']
            else:
                return row['RCONG105']

    class Securities:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.ResidentialPassThru = self.ResidentialPassThru(self)
            self.flags = {}
            self.messages = {}

        def USTreasuries(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    return row['RCON0211']
                elif valuation == 'fv':
                    return row['RCON0213']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCON1286']
                elif valuation == 'fv':
                    return row['RCON1287']

        def USGovtObligations(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) > 20180331:
                if accounting == 'htm':
                    if valuation == 'ac':
                        return row['RCONHT50']
                    elif valuation == 'fv':
                        return row['RCONHT51']
                elif accounting == 'afs':
                    if valuation == 'ac':
                        return row['RCONHT52']
                    elif valuation == 'fv':
                        return row['RCONHT53']
            elif accounting == 'htm':
                if valuation == 'ac':
                    return row['RCON1289'] + row['RCON1294']
                elif valuation == 'fv':
                    return row['RCON1290'] + row['RCON1295']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCON1291'] + row['RCON1297']
                elif valuation == 'fv':
                    return row['RCON1293'] + row['RCON1298']

        def StateSecurities(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    return row['RCON8496']
                elif valuation == 'fv':
                    return row['RCON8497']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCON8498']
                elif valuation == 'fv':
                    return row['RCON8499']

        class ResidentialPassThru:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def Total(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if accounting == 'htm':
                    if valuation == 'ac':
                        return self.parent.GNMAPassThru(accounting='htm', valuation='ac', date=date) + self.parent.FNMAPassThru(accounting='htm', valuation='ac', date=date) + self.parent.OtherPassThru(accounting='htm', valuation='ac', date=date)
                    elif valuation == 'fv':
                        return self.parent.GNMAPassThru(accounting='htm', valuation='fv', date=date) + self.parent.FNMAPassThru(accounting='htm', valuation='fv', date=date) + self.parent.OtherPassThru(accounting='htm', valuation='fv', date=date)
                elif accounting == 'afs':
                    if valuation == 'ac':
                        return self.parent.GNMAPassThru(accounting='afs', valuation='ac', date=date) + self.parent.FNMAPassThru(accounting='afs', valuation='ac', date=date) + self.parent.OtherPassThru(accounting='afs', valuation='ac', date=date)
                    elif valuation == 'fv':
                        return self.parent.GNMAPassThru(accounting='afs', valuation='fv', date=date) + self.parent.FNMAPassThru(accounting='afs', valuation='fv', date=date) + self.parent.OtherPassThru(accounting='afs', valuation='fv', date=date)

            def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA555']

            def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA556']

            def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA557']

            def FiveYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA558']

            def FifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA559']

            def OverFifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCONA560']

        def OtherResidentialPassThru(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return self.OtherResidentialGNMA(accounting, valuation, date=date) + self.OtherResidentialFNMA(accounting, valuation, date=date) + self.OtherResidentialOther(accounting, valuation, date=date)

        def OtherResidentialGNMA(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    return row['RCONG312']
                elif valuation == 'fv':
                    return row['RCONG313']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCONG314']
                elif valuation == 'fv':
                    return row['RCONG315']

        def OtherResidentialFNMA(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            suffix = {('htm', 'ac'): 'G316', ('htm', 'fv'): 'G317', ('afs', 'ac'): 'G318', ('afs', 'fv'): 'G319'}
            return row['RCON' + suffix[accounting, valuation]]

        def OtherResidentialOther(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            suffix = {('htm', 'ac'): 'G320', ('htm', 'fv'): 'G321', ('afs', 'ac'): 'G322', ('afs', 'fv'): 'G323'}
            return row['RCON' + suffix[accounting, valuation]]

        def CommericalPassThru(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) > 20110331:
                if accounting == 'htm':
                    if valuation == 'ac':
                        return row['RCONK142'] + row['RCONK146']
                    elif valuation == 'fv':
                        return row['RCONK143'] + row['RCONK147']
                elif accounting == 'afs':
                    if valuation == 'ac':
                        return row['RCONK144'] + row['RCONK148']
                    elif valuation == 'fv':
                        return row['RCONK145'] + row['RCONK149']
            elif accounting == 'htm':
                if valuation == 'ac':
                    return row['RCONG324']
                elif valuation == 'fv':
                    return row['RCONG325']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCONG326']
                elif valuation == 'fv':
                    return row['RCONG327']

        def OtherCommericalMBS(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if self.root.ReportingDate(date=date) > 20110331:
                if accounting == 'htm':
                    if valuation == 'ac':
                        return row['RCONK150'] + row['RCONK154']
                    elif valuation == 'fv':
                        return row['RCONK151'] + row['RCONK155']
                elif accounting == 'afs':
                    if valuation == 'ac':
                        return row['RCONK152'] + row['RCONK156']
                    elif valuation == 'fv':
                        return row['RCONK153'] + row['RCONK157']
            elif accounting == 'htm':
                if valuation == 'ac':
                    return row['RCONG328']
                elif valuation == 'fv':
                    return row['RCONG329']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCONG330']
                elif valuation == 'fv':
                    return row['RCONG331']

        def GNMAPassThru(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    return row['RCONG300']
                elif valuation == 'fv':
                    return row['RCONG301']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCONG302']
                elif valuation == 'fv':
                    return row['RCONG303']

        def FNMAPassThru(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    return row['RCONG304']
                elif valuation == 'fv':
                    return row['RCONG305']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCONG306']
                elif valuation == 'fv':
                    return row['RCONG307']

        def OtherPassThru(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    return row['RCONG308']
                elif valuation == 'fv':
                    return row['RCONG309']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCONG310']
                elif valuation == 'fv':
                    return row['RCONG311']

        def MBSTotal(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    self.name = 'Total Mortgage-backed Securities Held-to-Maturity at Amortized Cost (Schedule RC-B)'
                    if name:
                        return self.name
                    return self.ResidentialPassThru.Total(accounting='htm', valuation='ac', date=date) + self.OtherResidentialPassThru(accounting='htm', valuation='ac', date=date) + self.CommericalPassThru(accounting='htm', valuation='ac', date=date) + self.OtherCommericalMBS(accounting='htm', valuation='ac', date=date)
                elif valuation == 'fv':
                    if name:
                        return None
                    return self.ResidentialPassThru.Total(accounting='htm', valuation='fv', date=date) + self.OtherResidentialPassThru(accounting='htm', valuation='fv', date=date) + self.CommericalPassThru(accounting='htm', valuation='fv', date=date) + self.OtherCommericalMBS(accounting='htm', valuation='fv', date=date)
            elif accounting == 'afs':
                if valuation == 'ac':
                    if name:
                        return None
                    return self.ResidentialPassThru.Total(accounting='afs', valuation='ac', date=date) + self.OtherResidentialPassThru(accounting='afs', valuation='ac', date=date) + self.CommericalPassThru(accounting='afs', valuation='ac', date=date) + self.OtherCommericalMBS(accounting='afs', valuation='ac', date=date)
                elif valuation == 'fv':
                    self.name = 'Total Mortgage-backed Securities Available-for-Sale at Fair Value (Schedule RC-B)'
                    if name:
                        return self.name
                    return self.ResidentialPassThru.Total(accounting='afs', valuation='fv', date=date) + self.OtherResidentialPassThru(accounting='afs', valuation='fv', date=date) + self.CommericalPassThru(accounting='afs', valuation='fv', date=date) + self.OtherCommericalMBS(accounting='afs', valuation='fv', date=date)

        def ABS(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    self.name = 'Asset-backed Securities Held-to-Maturity at Amortized Cost (Schedule RC-B)'
                    if name:
                        return self.name
                    return row['RCONC026']
                elif valuation == 'fv':
                    return row['RCONC988']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCONC989']
                elif valuation == 'fv':
                    self.name = 'Asset-backed Securities Available-for-Sale at Fair Value (Schedule RC-B)'
                    if name:
                        return self.name
                    return row['RCONC027']

        def OtherDebtSecurities(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    self.name = 'Other Debt Securities Held-to-Maturity at Amortized Cost from (Schedule RC-B)'
                    if name:
                        return self.name
                    return row['RCON1737'] + row['RCON1742']
                elif valuation == 'fv':
                    return row['RCON1738'] + row['RCON1743']
            elif accounting == 'afs':
                if valuation == 'ac':
                    return row['RCON1739'] + row['RCON1744']
                elif valuation == 'fv':
                    self.name = 'Other Debt Securities Available-for-Sale at Fair Value from (Schedule RC-B)'
                    if name:
                        return self.name
                    return row['RCON1741'] + row['RCON1746']

        def Total(self, accounting, valuation, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if accounting == 'htm':
                if valuation == 'ac':
                    total = row['RCON1754']
                    self.name = 'Total Held-to-Maturity Securities at Amortized Cost'
                    if name:
                        return self.name
                    return total
                elif valuation == 'fv':
                    self.name = 'Total Held-to-Maturity Securities at Fair Value'
                    if name:
                        return self.name
                    return row['RCON1771']
            elif accounting == 'afs':
                if valuation == 'ac':
                    self.name = 'Total Available-for-Sale Securities at Amortized Cost'
                    if name:
                        return self.name
                    return row['RCON1772']
                elif valuation == 'fv':
                    total = row['RCON1773']
                    self.name = 'Total Available-for-Sale Securities at Amortized Cost'
                    if name:
                        return self.name
                    return total

    class LoansAndLeases:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.ExcludingClosedEnd = self.ExcludingClosedEnd(self)
            self.ClosedEndFirstLiens = self.ClosedEndFirstLiens(self)
            self.SecuredRealEstate = self.SecuredRealEstate(self)
            self.flags = {}
            self.messages = {}

        def Total(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCON2122']
            self.name = 'Total loans and leases held for investment and held for sale (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def FamilyResidentialConstruction(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCONF158']
            self.name = 'Loans secured by real estate for 1-4 family residential construction (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def OtherConstruction(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCONF159']
            self.name = 'Loans secured by real estate for other construction and all land development (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def Farmland(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCON1420']
            self.name = 'Loans secured by farmland (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def OpenEndSecuredFamily(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCON1797']
            self.name = 'Loans secured by real estate for revolving, open-end loans secured by 1-4 family residential properties (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        class ExcludingClosedEnd:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                total = self.ThreeMonths(date=date) + self.TwelveMonths(date=date) + self.ThreeYears(date=date) + self.FiveYears(date=date) + self.FifteenYears(date=date) + self.OverFifteenYears(date=date)
                self.name = 'Loans secured by real estate for closed-end family residential secured by first liens (Schedule RC-C Part I)'
                if name:
                    return self.name
                return total

            def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Closed-end first liens with maturity and repricing data three months or less'
                if name:
                    return self.name
                return row['RCONA570']

            def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Closed-end first liens with maturity and repricing data over three months through 12 months'
                if name:
                    return self.name
                return row['RCONA571']

            def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Closed-end first liens with maturity and repricing data over one year through three years'
                if name:
                    return self.name
                return row['RCONA572']

            def FiveYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Closed-end first liens with maturity and repricing data over three years through five years'
                if name:
                    return self.name
                return row['RCONA573']

            def FifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Closed-end first liens with maturity and repricing data over five years through fifteen years'
                if name:
                    return self.name
                return row['RCONA574']

            def OverFifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Closed-end first liens with maturity and repricing data over fifteen years'
                if name:
                    return self.name
                return row['RCONA575']

        class ClosedEndFirstLiens:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                total = row['RCON5367']
                self.name = 'Loans secured by real estate for closed-end family residential secured by first liens (Schedule RC-C Part I)'
                if name:
                    return self.name
                return total

            def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Closed-end first liens with maturity and repricing data three months or less'
                if name:
                    return self.name
                return row['RCONA564']

            def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Closed-end first liens with maturity and repricing data over three months through 12 months'
                if name:
                    return self.name
                return row['RCONA565']

            def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Closed-end first liens with maturity and repricing data over one year through three years'
                if name:
                    return self.name
                return row['RCONA566']

            def FiveYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Closed-end first liens with maturity and repricing data over three years through five years'
                if name:
                    return self.name
                return row['RCONA567']

            def FifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Closed-end first liens with maturity and repricing data over five years through fifteen years'
                if name:
                    return self.name
                return row['RCONA568']

            def OverFifteenYears(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Closed-end first liens with maturity and repricing data over fifteen years'
                if name:
                    return self.name
                return row['RCONA569']

        def ClosedEndJuniorLiens(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCON5368']
            self.name = 'Loans secured by real estate for closed-end family residential secured by junior liens (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def SecuredMultifamily(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCON1460']
            self.name = 'Loans secured by real estate for multifamily (5 or more) residential properties (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def SecuredNonfarmOwner(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCONF160']
            self.name = 'Loans secured by real estate for nonfarm nonresidential properties, owner-occupied (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def SecuredNonfarmOther(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCONF161']
            self.name = 'Loans secured by real estate for nonfarm nonresidential properties, other (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def DepositoryInstitutions(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCON1288']
            self.name = 'Loans to depository institutions and acceptances of other banks (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def FinanceAgricultural(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCON1590']
            self.name = 'Loans to finance agricultural production and other loans to farmers (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def CommercialAndIndustrial(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCON1766']
            self.name = 'Commercial and industrial loans (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def CreditCards(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCONB538']
            self.name = 'Loans to individuals for credit cards (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def RevolvingCredit(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCONB539']
            self.name = 'Loans to individuals for revolving credit plans (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def AutomobileLoans(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCONK137']
            self.name = 'Loans to individuals for automobile loans (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def ConsumerLoans(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCONK207']
            self.name = 'Other individual consumer laons (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def StatesAndPolitical(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCON2107']
            self.name = 'Obligations of state and political subdivisions (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def NonDepository(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCONJ454']
            self.name = 'Loans to nondepository financial institutions (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def NonDepositoryOther(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCONJ464']
            self.name = 'Loans to nondepository financial institutions and other loans (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        def UnearnedIncome(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            total = row['RCON2123']
            self.name = 'Loans to nondepository financial institutions (Schedule RC-C Part I)'
            if name:
                return self.name
            return total

        class SecuredRealEstate:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.SFR = self.SFR(self)

            def ConstructionSFR(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                uc = Global_uc(row)._zero
                self.name = 'Loans secured by real estate for the construction of 1-4 family residential properties in domestic offices'
                if name:
                    return self.name
                return uc('RCONF158')

            def ConstructionOther(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                uc = Global_uc(row)._zero
                self.name = 'Loans secured by real estate for all land development in domestic offices'
                if name:
                    return self.name
                return uc('RCONF159')

            def Farmland(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                uc = Global_uc(row)._zero
                self.name = 'Loans secured by farmland in domestic offices'
                if name:
                    return self.name
                return uc('RCON1420')

            class SFR:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def OpenEndRevolving(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    cc = Global_uc(row)._zero
                    self.name = 'Loans secured by real estate for all land development in domestic offices'
                    if name:
                        return self.name
                    return cc('RCON1797')

    class DepositLiabilities:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.TransactionDeposits = self.TransactionDeposits(self)
            self.NonTransactionDeposits = self.NonTransactionDeposits(self)
            self.flags = {}
            self.messages = {}

        def ReportedTotal(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            return row['RCON2200']

        def DomesticDeposits(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            DomesticDeposits = self.root.BalanceSheet.DepositDomesticOffices.Total(date=date)
            self.name = 'Total Domestic Deposits'
            if name:
                return self.name
            comp = self.TransactionDeposits.Total(date=date) + self.NonTransactionDeposits.Total(date=date)
            difference = DomesticDeposits - comp
            self.flags['DomesticDeposits'] = False
            self.messages['DomesticDeposits'] = None
            if self.TransactionDeposits.flags.get('Total', False) or self.NonTransactionDeposits.flags.get('Total', False):
                causes = []
                if self.TransactionDeposits.flags.get('Total', False):
                    causes.append(self.TransactionDeposits.messages.get('Total'))
                if self.NonTransactionDeposits.flags.get('Total', False):
                    causes.append(self.NonTransactionDeposits.messages.get('Total'))
                self.flags['DomesticDeposits'] = True
                self.messages['DomesticDeposits'] = f"{DomesticDeposits} does not equal {comp} by {difference} in {self.name} for IDRSSD {self.root.RSSDID(date=date)} on {self.root.ReportingDate(date=date)} check {' | '.join(causes)}"
                print(self.messages['DomesticDeposits'])
            elif DomesticDeposits != comp:
                self.flags['DomesticDeposits'] = True
                self.messages['DomesticDeposits'] = f'{DomesticDeposits} does not equal {comp} by {difference} in {self.name} for IDRSSD {self.root.RSSDID(date=date)} on {self.root.ReportingDate(date=date)} '
                print(self.messages['DomesticDeposits'])
            return DomesticDeposits

        def Individuals(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Individual Domestic Deposits'
            if name:
                return self.name
            return self.TransactionDeposits.Individuals(date=date) + self.NonTransactionDeposits.Individuals(date=date)

        def USGovt(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'U.S. Government Domestic Deposits'
            if name:
                return self.name
            return self.TransactionDeposits.USGovt(date=date) + self.NonTransactionDeposits.USGovt(date=date)

        def StatesAndPolitical(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'States and Political Subdivisions Domestic Deposits'
            if name:
                return self.name
            return self.TransactionDeposits.StatesAndPolitical(date=date) + self.NonTransactionDeposits.StatesAndPolitical(date=date)

        def CommercialBanks(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Commercial Banks Domestic Deposits'
            if name:
                return self.name
            return self.TransactionDeposits.CommercialBanks(date=date) + self.NonTransactionDeposits.CommercialBanks(date=date)

        def ForeignBanks(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Banks in Foreign Countires Domestic Deposits'
            if name:
                return self.name
            return self.TransactionDeposits.ForeignBanks(date=date) + self.NonTransactionDeposits.ForeignBanks(date=date)

        def ForeignGovt(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Foreign government Domestic Deposits'
            if name:
                return self.name
            return self.TransactionDeposits.ForeignGovt(date=date) + self.NonTransactionDeposits.ForeignGovt(date=date)

        class TransactionDeposits:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def Individuals(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Individual Transaction Deposits'
                if name:
                    return self.name
                return row['RCONB549']

            def USGovt(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'U.S. Government Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2202']

            def StatesAndPolitical(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'States and Political Subdivisions Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2203']

            def CommercialBanks(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Commercial Banks Transaction Deposits'
                if name:
                    return self.name
                return row['RCONB551']

            def ForeignBanks(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Banks in Foriegn Countries Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2213']

            def ForeignGovt(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Foreign Government Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2216']

            def ReportedTotal(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCON2215']

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                i = self.Individuals(date=date)
                u = self.USGovt(date=date)
                s = self.StatesAndPolitical(date=date)
                c = self.CommercialBanks(date=date)
                f = self.ForeignBanks(date=date)
                g = self.ForeignGovt(date=date)
                total = row['RCON2215']
                if name:
                    return self.name
                comp = i + u + s + c + f + g
                difference = total - comp
                self.flags['Total'] = False
                self.messages['Total'] = None
                self.name = 'Total Transaction Deposits'
                if total != comp:
                    self.flags['Total'] = True
                    self.messages['Total'] = f'{self.name}: {total} does not equal {comp} by {difference} in {self.name}: {self.Individuals(name=True, date=date)}={i}, {self.USGovt(name=True, date=date)}={u}, {self.StatesAndPolitical(name=True, date=date)}={s}, {self.CommercialBanks(name=True, date=date)}={c}, {self.ForeignBanks(name=True, date=date)}={f}, {self.ForeignGovt(name=True, date=date)}={g} on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                    print(self.messages['Total'])
                return total

        class NonTransactionDeposits:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.TimeDeposits = self.TimeDeposits(self)
                self.flags = {}
                self.messages = {}

            def Individuals(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Individual Non-Transaction Deposits'
                if name:
                    return self.name
                return row['RCONB550']

            def ReportedTotal(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return row['RCON2385']

            def USGovt(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'U.S. Government Non-Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2520']

            def StatesAndPolitical(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'States and Political Subdivisions Non-Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2530']

            def CommercialBanks(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Commercial Banks Non-Transaction Deposits'
                if name:
                    return self.name
                return row['RCONB552']

            def ForeignBanks(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Banks in Foriegn Countries Non-Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2236']

            def ForeignGovt(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Foreign Government Non-Transaction Deposits'
                if name:
                    return self.name
                return row['RCON2377']

            def Total(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                total = row['RCON2385']
                if name:
                    return self.name
                i1 = self.Individuals(date=date)
                u1 = self.USGovt(date=date)
                s1 = self.StatesAndPolitical(date=date)
                c1 = self.CommercialBanks(date=date)
                f1 = self.ForeignBanks(date=date)
                g1 = self.ForeignGovt(date=date)
                i2 = self.TimeDeposits.LessThan100k(date=date)
                u2 = self.TimeDeposits.LessThan250k.Total(date=date)
                s2 = self.TimeDeposits.MoreThan250k.Total(date=date)
                c2 = self.SavingsMMDA(date=date)
                f2 = self.SavingsOther(date=date)
                comp1 = i1 + u1 + s1 + c1 + f1 + g1
                comp2 = i2 + u2 + s2 + c2 + f2
                difference1 = total - comp1
                difference2 = total - comp2
                self.flags['Total'] = False
                self.flags['Memoranda2'] = False
                self.messages['Total'] = None
                self.messages['Memoranda2'] = None
                self.name = 'Total Non-Transaction Deposits'
                if total != comp1:
                    self.flags['Total'] = True
                    self.messages['Total'] = f'{self.Total(name=True, date=date)}: {total} does not equal {comp1} by {difference1} in {self.Total(name=True, date=date)}: {self.Individuals(name=True, date=date)}={i1}, {self.USGovt(name=True, date=date)}={u1}, {self.StatesAndPolitical(name=True, date=date)}={s1}, {self.CommercialBanks(name=True, date=date)}={c1}, {self.ForeignBanks(name=True, date=date)}={f1}, {self.ForeignGovt(name=True, date=date)}={g1} on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                    print(self.messages['Total'])
                if total != comp2:
                    self.flags['Memoranda2'] = True
                    self.messages['Memoranda2'] = f'{self.name}: {total} does not equal {comp2} by {difference2} in {self.name}: {self.TimeDeposits.LessThan100k(name=True, date=date)}={i2}, {self.TimeDeposits.LessThan250k.Total(name=True, date=date)}={u2}, {self.TimeDeposits.MoreThan250k.Total(name=True, date=date)}={s2}, {self.SavingsMMDA(name=True, date=date)}={c2}, {self.SavingsOther(name=True, date=date)}={f2}, on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                    print(self.messages['Memoranda2'])
                return total

            class TimeDeposits:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.LessThan250k = self.LessThan250k(self)
                    self.MoreThan250k = self.MoreThan250k(self)
                    self.flags = {}
                    self.messages = {}

                def LessThan100k(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total Time Deposits of less than $100,000'
                    if name:
                        return self.name
                    return row['RCON6648']

                def MoreThan100kLessThan250k(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total Time Deposits of $100,000 through $250,000'
                    if name:
                        return self.name
                    return row['RCONJ473'] - row['RCON6648']

                class LessThan250k:

                    def __init__(self, parent):
                        self.parent = parent
                        self.root = parent.root
                        self.row = self.root.row
                        self.flags = {}
                        self.messages = {}

                    def ReportedTotal(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        return row['RCONJ473']

                    def EffectiveThreeMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if self.root.ReportingDate(date=date) >= 20170331:
                            return self.ThreeMonths(date=date)
                        return row['RCONA579']

                    def EffectiveTwelveMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if self.root.ReportingDate(date=date) >= 20170331:
                            return self.TwelveMonths(date=date)
                        return row['RCONA580']

                    def EffectiveThreeYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if self.root.ReportingDate(date=date) >= 20170331:
                            return self.ThreeYears(date=date)
                        return row['RCONA581']

                    def EffectiveOverThreeYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if self.root.ReportingDate(date=date) >= 20170331:
                            return self.OverThreeYears(date=date)
                        return row['RCONA582']

                    def Total(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of less than $250,000'
                        if name:
                            return self.name
                        total = row['RCONJ473']
                        i1 = self.ThreeMonths(date=date)
                        u1 = self.TwelveMonths(date=date)
                        s1 = self.ThreeYears(date=date)
                        c1 = self.OverThreeYears(date=date)
                        i2 = self.parent.LessThan100k(date=date)
                        u2 = self.parent.MoreThan100kLessThan250k(date=date)
                        comp1 = i1 + u1 + s1 + c1
                        comp2 = i2 + u2
                        difference1 = total - comp1
                        difference2 = total - comp2
                        self.flags['Total'] = False
                        self.flags['Maturity'] = False
                        self.messages['Total'] = None
                        self.messages['Maturity'] = None
                        self.name = 'Total Non-Transaction Deposits of Less Than $250,000'
                        if total != comp1:
                            self.flags['Maturity'] = True
                            self.messages['Maturity'] = f'{self.Total(name=True, date=date)}: {total} does not equal {comp1} by {difference1} in {self.Total(name=True, date=date)}: {self.ThreeMonths(name=True, date=date)}={i1}, {self.TwelveMonths(name=True, date=date)}={u1}, {self.ThreeYears(name=True, date=date)}={s1}, {self.OverThreeYears(name=True, date=date)}={c1}, on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                            print(self.messages['Maturity'])
                        if total != comp2:
                            self.flags['Total'] = True
                            self.messages['Total'] = f'{self.Total(name=True, date=date)}: {total} does not equal {comp2} by {difference2} in {self.Total(name=True, date=date)}: {self.parent.LessThan100k(name=True, date=date)}={i2}, {self.parent.MoreThan100kLessThan250k(name=True, date=date)}={u2}, on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                            print(self.messages['Total'])
                        return total

                    def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of less than $250,000 with maturity and repricing data three months or less'
                        if name:
                            return self.name
                        return row['RCONHK07']

                    def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of less than $250,000 with maturity and repricing data over three months through 12 months'
                        if name:
                            return self.name
                        return row['RCONHK08']

                    def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of less than $250,000 with maturity and repricing data over one year through three years'
                        if name:
                            return self.name
                        return row['RCONHK09']

                    def OverThreeYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of less than $250,000 with maturity and repricing data over three years'
                        if name:
                            return self.name
                        return row['RCONHK10']

                class MoreThan250k:

                    def __init__(self, parent):
                        self.parent = parent
                        self.root = parent.root
                        self.row = self.root.row
                        self.flags = {}
                        self.messages = {}

                    def ReportedTotal(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        return row['RCONJ474']

                    def Total(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of more than $250,000'
                        if name:
                            return self.name
                        return row['RCONJ474']

                    def ThreeMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of more than $250,000 with maturity and repricing data three months or less'
                        if name:
                            return self.name
                        return row['RCONHK12']

                    def TwelveMonths(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of more than $250,000 with maturity and repricing data over three months through 12 months'
                        if name:
                            return self.name
                        return row['RCONHK13']

                    def ThreeYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of more than $250,000 with maturity and repricing data over one year through three years'
                        if name:
                            return self.name
                        return row['RCONHK14']

                    def OverThreeYears(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Time Deposits of more than $250,000 with maturity and repricing data over three years'
                        if name:
                            return self.name
                        return row['RCONHK15']

            def SavingsMMDA(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Money Market Deposit Accounts (MMDAs)'
                if name:
                    return self.name
                return row['RCON6810']

            def SavingsOther(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                self.name = 'Other Savings Deposits (excludes MMDAs)'
                if name:
                    return self.name
                return row['RCON0352']

            def SavingsTotal(self, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                return self.SavingsMMDA(date=date) + self.SavingsOther(date=date)

    class OtherLiabilities:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.flags = {}
            self.messages = {}

        def InterestAccrued(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Interest Accrued and Unpaid on Deposits in Domestic Offices'
            if name:
                return self.name
            return row['RCON3645']

        def ExpensesAccruedOther(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Other expenses accrued and unpaid (includes accrued income taxes (payable))'
            if name:
                return self.name
            return row['RCON3646']

        def DTLsNet(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Net deferred tax liabilities'
            if name:
                return self.name
            return row['RCON3049']

        def CreditLosses(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Allowance for Credit Losses on off-balanace sheet credit exposures'
            if name:
                return self.name
            return row['RCONB557']

        def AllOtherLiabilities(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'All Other Liabilities'
            if name:
                return self.name
            return row['RCON2938']

        def Total(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Other Liabilities Total from Schedule RC-G'
            if name:
                return self.name
            return row['RCON2930']

    class DerivativesOffBalanceSheet:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.CreditDerivatives = self.CreditDerivatives(self)
            self.OtherDerivatives = self.OtherDerivatives(self)
            self.flags = {}
            self.messages = {}

        class CreditDerivatives:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.SoldProtection = self.SoldProtection(self)
                self.PurchasedProtection = self.PurchasedProtection(self)
                self.flags = {}
                self.messages = {}

            class SoldProtection:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.Notional = self.Notional(self)
                    self.flags = {}
                    self.messages = {}

                def CDS(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of sold protection in credit derivatives: Credit default swaps'
                    if name:
                        return self.name
                    return row['RCONC968']

                def TotalReturnSwaps(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of sold protection in credit derivatives: Total return swaps'
                    if name:
                        return self.name
                    return row['RCONC970']

                def CreditOptions(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts: Credit Options'
                    if name:
                        return self.name
                    return row['RCONC972']

                def OtherCreditDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of sold protection in credit derivatives: Other credit derivatives'
                    if name:
                        return self.name
                    return row['RCONC974']

                class Notional:

                    def __init__(self, parent):
                        self.parent = parent
                        self.root = parent.root
                        self.row = self.root.row
                        self.flags = {}
                        self.messages = {}

                    def Total(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Notional amounts of sold protection in credit derivatives'
                        if name:
                            return self.name
                        notional = self.parent.CDS(date=date) + self.parent.TotalReturnSwaps(date=date) + self.parent.CreditOptions(date=date) + self.parent.OtherCreditDerivatives(date=date)
                        u1 = self.parent.CDS(name, date=date)
                        u2 = self.parent.TotalReturnSwaps(name, date=date)
                        u3 = self.parent.CreditOptions(name, date=date)
                        u4 = self.parent.OtherCreditDerivatives(name, date=date)
                        v1 = self.SubInvestmentGrade(name, date=date)
                        v2 = self.InvestmentGrade(name, date=date)
                        comp1 = u1 + u2 + u3 + u4
                        comp2 = v1 + v2
                        difference1 = notional - comp1
                        difference2 = notional - comp2
                        self.flags['Notional'] = False
                        self.flags['Rating'] = False
                        self.messages['Notional'] = None
                        self.messages['Rating'] = None
                        if difference1 != 0:
                            self.flags['Notional'] = True
                            self.messages['Notional'] = f'{self.name}: {notional} does not equal {comp1} by {difference1}'
                            print(self.messages['Notional'])
                        if difference2 != 0:
                            self.flags['Rating'] = True
                            self.messages['Rating'] = f'{self.name}: {notional} does not equal {comp2} by {difference2}'
                            print(self.messages['Rating'])
                        return notional

                    def TwelveMonths(self, rating, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if rating == 'IG':
                            self.name = 'Total notional amounts of investment grade sold protection in credit derivatives with a remaining maturity of one year or less'
                            if name:
                                return self.name
                            return row['RCONG406']
                        elif rating == 'SubIG':
                            self.name = 'Total notional amounts of subinvestment grade sold protection in credit derivatives with a remaining maturity of one year or less'
                            if name:
                                return self.name
                            return row['RCONG409']

                    def FiveYears(self, rating, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if rating == 'IG':
                            self.name = 'Total notional amounts of investment grade sold protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCONG407']
                        elif rating == 'SubIG':
                            self.name = 'Total notional amounts of subinvestment grade sold protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCONG410']

                    def OverFiveYears(self, rating, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if rating == 'IG':
                            self.name = 'Total notional amounts of investment grade sold protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCONG408']
                        elif rating == 'SubIG':
                            self.name = 'Total notional amounts of subinvestment grade sold protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCONG411']

                    def InvestmentGrade(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total notional amounts of subinvestment grade purchased protection credit derivatives'
                        if name:
                            return self.name
                        return self.TwelveMonths(rating='IG', name=False, date=date) + self.FiveYears(rating='IG', name=False, date=date) + self.OverFiveYears(rating='IG', name=False, date=date)

                    def SubInvestmentGrade(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total notional amounts of subinvestment grade purchased protection credit derivatives'
                        if name:
                            return self.name
                        return self.TwelveMonths(rating='SubIG', name=False, date=date) + self.FiveYears(rating='SubIG', name=False, date=date) + self.OverFiveYears(rating='SubIG', name=False, date=date)

                def MarketRiskRule(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of sold protection in CDSs by regulatory capital treatment: Market Risk Rule positions'
                    if name:
                        return self.name
                    total = row['RCONG401']
                    u1 = self.CDS(name, date=date)
                    u2 = self.TotalReturnSwaps(name, date=date)
                    u3 = self.CreditOptions(name, date=date)
                    u4 = self.OtherCreditDerivatives(name, date=date)
                    comp1 = u1 + u2 + u3 + u4
                    difference1 = total - comp1
                    self.flags['MarketRiskRule'] = False
                    self.messages['MarketRiskRule'] = None
                    if difference1 > 0:
                        self.flags['MarketRiskRule'] = True
                        self.messages['MarketRiskRule'] = f'{self.MarketRiskRule(name=True, date=date)}: {total} does not equal {comp1} by {difference1} check in {self.MarketRiskRule(name=True, date=date)}: {self.CDS(name=True, date=date)}={u1}, {self.TotalReturnSwaps(name=True, date=date)}={u2}, {self.CreditOptions(name=True, date=date)}={u3}, {self.OtherCreditDerivatives(name=True, date=date)}={u4}, on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                        print(self.messages['MarketRiskRule'])
                    return total

            class PurchasedProtection:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.Notional = self.Notional(self)
                    self.flags = {}
                    self.messages = {}

                def CDS(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of Purchased Protection in CDSs: Credit default swaps'
                    if name:
                        return self.name
                    return row['RCONC969']

                def TotalReturnSwaps(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of Purchased Protection in CDSs: Total return swaps'
                    if name:
                        return self.name
                    return row['RCONC971']

                def CreditOptions(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of Purchased Protection in CDSs: Credit Options'
                    if name:
                        return self.name
                    return row['RCONC973']

                def OtherCreditDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of Purchased Protection in CDSs: Other credit derivatives'
                    if name:
                        return self.name
                    return row['RCONC975']

                class Notional:

                    def __init__(self, parent):
                        self.parent = parent
                        self.root = parent.root
                        self.row = self.root.row
                        self.flags = {}
                        self.messages = {}

                    def Total(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total Notional amounts of purchased protection in CDSs'
                        if name:
                            return self.name
                        notional = self.parent.CDS(date=date) + self.parent.TotalReturnSwaps(date=date) + self.parent.CreditOptions(date=date) + self.parent.OtherCreditDerivatives(date=date)
                        u1 = self.parent.CDS(name, date=date)
                        u2 = self.parent.TotalReturnSwaps(name, date=date)
                        u3 = self.parent.CreditOptions(name, date=date)
                        u4 = self.parent.OtherCreditDerivatives(name, date=date)
                        v1 = self.SubInvestmentGrade(name, date=date)
                        v2 = self.InvestmentGrade(name, date=date)
                        comp1 = u1 + u2 + u3 + u4
                        comp2 = v1 + v2
                        difference1 = notional - comp1
                        difference2 = notional - comp2
                        self.flags['Notional'] = False
                        self.flags['Rating'] = False
                        self.messages['Notional'] = None
                        self.messages['Rating'] = None
                        if difference1 != 0:
                            self.flags['Notional'] = True
                            self.messages['Notional'] = f'{self.name}: {notional} does not equal {comp1} by {difference1}'
                            print(self.messages['Notional'])
                        if difference2 != 0:
                            self.flags['Rating'] = True
                            self.messages['Rating'] = f'{self.name}: {notional} does not equal {comp2} by {difference2}'
                            print(self.messages['Rating'])
                        return notional

                    def TwelveMonths(self, rating='IG', name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if rating == 'IG':
                            self.name = 'Total notional amounts of investment grade purchased protection in credit derivatives with a remaining maturity of one year or less'
                            if name:
                                return self.name
                            return row['RCONG412']
                        elif rating == 'SubIG':
                            self.name = 'Total notional amounts of subinvestment grade purchased protection in credit derivatives with a remaining maturity of one year or less'
                            if name:
                                return self.name
                            return row['RCONG415']

                    def FiveYears(self, rating, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if rating == 'IG':
                            self.name = 'Total notional amounts of investment grade purchased protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCONG413']
                        elif rating == 'SubIG':
                            self.name = 'Total notional amounts of subinvestment grade purchased protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCONG416']

                    def OverFiveYears(self, rating, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        if rating == 'IG':
                            self.name = 'Total notional amounts of investment grade purchased protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCONG414']
                        elif rating == 'SubIG':
                            self.name = 'Total notional amounts of subinvestment grade purchased protection in credit derivatives with a remaining maturity of over one year through five years'
                            if name:
                                return self.name
                            return row['RCONG417']

                    def InvestmentGrade(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total notional amounts of subinvestment grade purchased protection credit derivatives'
                        if name:
                            return self.name
                        return self.TwelveMonths(rating='IG', name=False, date=date) + self.FiveYears(rating='IG', name=False, date=date) + self.OverFiveYears(rating='IG', name=False, date=date)

                    def SubInvestmentGrade(self, name=False, *args, date='P0', **kwargs):
                        row = self.root.get_row(date)
                        self.name = 'Total notional amounts of subinvestment grade purchased protection credit derivatives'
                        if name:
                            return self.name
                        return self.TwelveMonths(rating='SubIG', name=False, date=date) + self.FiveYears(rating='SubIG', name=False, date=date) + self.OverFiveYears(rating='SubIG', name=False, date=date)

                def MarketRiskRule(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Notional amounts of Purchased Protection in CDSs by regulatory capital treatment: Market Risk Rule positions'
                    if name:
                        return self.name
                    MRR = row['RCONG402']
                    u1 = self.CDS(name, date=date)
                    u2 = self.TotalReturnSwaps(name, date=date)
                    u3 = self.CreditOptions(name, date=date)
                    u4 = self.OtherCreditDerivatives(name, date=date)
                    comp1 = u1 + u2 + u3 + u4
                    difference1 = MRR - comp1
                    self.flags['MarketRiskRule'] = False
                    self.messages['MarketRiskRule'] = None
                    if difference1 > 0:
                        self.flags['MarketRiskRule'] = True
                        self.messages['MarketRiskRule'] = f'{self.MarketRiskRule(name=True, date=date)}: {MRR} does not equal {comp1} by {difference1} check in {self.MarketRiskRule(name=True, date=date)}: {self.CDS(name=True, date=date)}={u1}, {self.TotalReturnSwaps(name=True, date=date)}={u2}, {self.CreditOptions(name=True, date=date)}={u3}, {self.OtherCreditDerivatives(name=True, date=date)}={u4}, on {self.root.ReportingDate(date=date)} for {self.root.RSSDID(date=date)}'
                        print(self.messages['MarketRiskRule'])
                    return MRR

        class OtherDerivatives:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.HeldForTrading = self.HeldForTrading(self)
                self.NotHeldForTrading = self.NotHeldForTrading(self)
                self.Futures = self.Futures(self)
                self.Forwards = self.Forwards(self)
                self.ETDOptions = self.ETDOptions(self)
                self.OTCOptions = self.OTCOptions(self)
                self.Swaps = self.Swaps(self)
                self.flags = {}
                self.messages = {}

            class HeldForTrading:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of derivatives contracts held for trading'
                    if name:
                        return self.name
                    return self.InterestRates(name, date=date) + self.ForeignExchange(name, date=date) + self.EquityDerivatives(name, date=date) + self.CommoditiesOther(name, date=date)

                def InterestRates(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of interest rate derivative contracts held for trading'
                    if name:
                        return self.name
                    return row['RCONA126']

                def ForeignExchange(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of foreign exchange derivative contracts held for trading'
                    if name:
                        return self.name
                    return row['RCONA127']

                def EquityDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of equity derivative contracts held for trading'
                    if name:
                        return self.name
                    return row['RCON8723']

                def CommoditiesOther(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of commodities and other derivative contracts held for trading'
                    if name:
                        return self.name
                    return row['RCON8724']

            class NotHeldForTrading:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of derivatives contracts not held for trading'
                    if name:
                        return self.name
                    return self.InterestRates(name, date=date) + self.ForeignExchange(name, date=date) + self.EquityDerivatives(name, date=date) + self.CommoditiesOther(name, date=date)

                def InterestRates(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of interest rate derivative contracts not held for trading'
                    if name:
                        return self.name
                    return row['RCON8725']

                def ForeignExchange(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of foreign exchange derivative contracts not held for trading'
                    if name:
                        return self.name
                    return row['RCON8726']

                def EquityDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of equity derivative contracts not held for trading'
                    if name:
                        return self.name
                    return row['RCON8727']

                def CommoditiesOther(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of commodities and other derivative contracts not held for trading'
                    if name:
                        return self.name
                    return row['RCON8728']

            class Futures:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of futures (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(name, date=date) + self.ForeignExchange(name, date=date) + self.EquityDerivatives(name, date=date) + self.CommoditiesOther(name, date=date)

                def InterestRates(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Futures on Interest Rates Contracts'
                    if name:
                        return self.name
                    return row['RCON8693']

                def ForeignExchange(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Futures on foreign exchange contracts'
                    if name:
                        return self.name
                    return row['RCON8694']

                def EquityDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Futures on Equity Derivatives Contracts'
                    if name:
                        return self.name
                    return row['RCON8695']

                def CommoditiesOther(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Futures on Commodities and Other Contracts'
                    if name:
                        return self.name
                    return row['RCON8696']

            class Forwards:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of Forwards (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(name, date=date) + self.ForeignExchange(name, date=date) + self.EquityDerivatives(name, date=date) + self.CommoditiesOther(name, date=date)

                def InterestRates(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Forwards on Interest Rates Contracts'
                    if name:
                        return self.name
                    return row['RCON8697']

                def ForeignExchange(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Forwards on foreign exchange contracts'
                    if name:
                        return self.name
                    return row['RCON8698']

                def EquityDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Forwards on Equity Derivatives Contracts'
                    if name:
                        return self.name
                    return row['RCON8699']

                def CommoditiesOther(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Forwards on Commodities and Other Contracts'
                    if name:
                        return self.name
                    return row['RCON8700']

            class ETDOptions:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of exchange-traded derivatives contracts (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.TotalWritten(name, date=date) + self.TotalPurchased(name, date=date)

                def TotalWritten(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of written option exchange-traded derivatives contracts (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(claim='written', date=date) + self.ForeignExchange(claim='written', date=date) + self.EquityDerivatives(claim='written', date=date) + self.CommoditiesOther(claim='written', date=date)

                def TotalPurchased(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of purchased option exchange-traded derivatives contracts (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(claim='purchased', date=date) + self.ForeignExchange(claim='purchased', date=date) + self.EquityDerivatives(claim='purchased', date=date) + self.CommoditiesOther(claim='purchased', date=date)

                def InterestRates(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Options on Interest Rates Contracts'
                        if name:
                            return self.name
                        return row['RCON8701']
                    elif claim == 'purchased':
                        self.name = 'Purchased Options on Interest Rates Contracts'
                        if name:
                            return self.name
                        return row['RCON8705']

                def ForeignExchange(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Options on foreign exchange contracts'
                        if name:
                            return self.name
                        return row['RCON8702']
                    elif claim == 'purchased':
                        self.name = 'Purchased Options on foreign exchange contracts'
                        if name:
                            return self.name
                        return row['RCON8706']

                def EquityDerivatives(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Options on Equity Derivatives Contracts'
                        if name:
                            return self.name
                        return row['RCON8703']
                    elif claim == 'purchased':
                        self.name = 'Written Options on Equity Derivatives Contracts'
                        if name:
                            return self.name
                        return row['RCON8707']

                def CommoditiesOther(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Purchased Options on Commodities and Other Contracts'
                        if name:
                            return self.name
                        return row['RCON8704']
                    elif claim == 'purchased':
                        self.name = 'Purchased Options on Commodities and Other Contracts'
                        if name:
                            return self.name
                        return row['RCON8708']

            class OTCOptions:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of over-the-counter options (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.TotalWritten(name, date=date) + self.TotalPurchased(name, date=date)

                def TotalWritten(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of over-the-counter written options (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(claim='written', date=date) + self.ForeignExchange(claim='written', date=date) + self.EquityDerivatives(claim='written', date=date) + self.CommoditiesOther(claim='written', date=date)

                def TotalPurchased(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of over-the-counter purchased options (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(claim='purchased', date=date) + self.ForeignExchange(claim='purchased', date=date) + self.EquityDerivatives(claim='purchased', date=date) + self.CommoditiesOther(claim='purchased', date=date)

                def InterestRates(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Over-the-counter Options on Interest Rates Contracts'
                        if name:
                            return self.name
                        return row['RCON8709']
                    elif claim == 'purchased':
                        self.name = 'Purchased Over-the-counter Options on Interest Rates Contracts'
                        if name:
                            return self.name
                        return row['RCON8713']

                def ForeignExchange(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Over-the-counter Options on foreign exchange contracts'
                        if name:
                            return self.name
                        return row['RCON8710']
                    elif claim == 'purchased':
                        self.name = 'Purchased Over-the-counter Options on foreign exchange contracts'
                        if name:
                            return self.name
                        return row['RCON8714']

                def EquityDerivatives(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Over-the-counter Options on Equity Derivatives Contracts'
                        if name:
                            return self.name
                        return row['RCON8711']
                    elif claim == 'purchased':
                        self.name = 'Purchased Over-the-counter Options on Equity Derivatives Contracts'
                        if name:
                            return self.name
                        return row['RCON8715']

                def CommoditiesOther(self, claim, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if claim == 'written':
                        self.name = 'Written Over-the-counter Options on Commodities and Other Contracts'
                        if name:
                            return self.name
                        return row['RCON8712']
                    elif claim == 'purchased':
                        self.name = 'Purchased Over-the-counter Options on Commodities and Other Contracts'
                        if name:
                            return self.name
                        return row['RCON8716']

            class Swaps:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row
                    self.flags = {}
                    self.messages = {}

                def Total(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Total gross notional amount of swaps (including held-for-trading and not held-for-trading'
                    if name:
                        return self.name
                    return self.InterestRates(name, date=date) + self.ForeignExchange(name, date=date) + self.EquityDerivatives(name, date=date) + self.CommoditiesOther(name, date=date)

                def InterestRates(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Swaps on Interest Rates Contracts'
                    if name:
                        return self.name
                    return row['RCON3450']

                def ForeignExchange(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Swaps on foreign exchange contracts'
                    if name:
                        return self.name
                    return row['RCON3826']

                def EquityDerivatives(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Swaps on Equity Derivatives Contracts'
                    if name:
                        return self.name
                    return row['RCON8719']

                def CommoditiesOther(self, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    self.name = 'Swaps on Commodities and Other Contracts'
                    if name:
                        return self.name
                    return row['RCON8720']

    class NonaccrualPastDue:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.LoansAndLeaseFinancingReceivables = self.LoansAndLeaseFinancingReceivables(self)
            self.SecuredRealEstate = self.SecuredRealEstate(self)
            self.DepositoryInstitutions = self.DepositoryInstitutions(self)
            self.Individuals = self.Individuals(self)

        class LoansAndLeaseFinancingReceivables:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def Total(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: total loans and lease financing receivables (RC-N, item 8)'
                    if name:
                        return self.name
                    return row['RCON1406']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: total loans and lease financing receivables (RC-N, item 8)'
                    if name:
                        return self.name
                    return row['RCON1407']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: total loans and lease financing receivables (RC-N, item 8)'
                    if name:
                        return self.name
                    return row['RCON1403']

            def GuaranteedByUSGovt(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: total loans and leases that are wholly or partially guaranteed by the U.S. Government, excluding FDIC-loss sharing agreements'
                    if name:
                        return self.name
                    return row['RCONK036']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: total loans and leases that are wholly or partially guaranteed by the U.S. Government, excluding FDIC-loss sharing agreements'
                    if name:
                        return self.name
                    return row['RCONK037']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: total loans and leases that are wholly or partially guaranteed by the U.S. Government, excluding FDIC-loss sharing agreements'
                    if name:
                        return self.name
                    return row['RCONK038']

            def LoansAndLeasesHeldForSale(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: total loans and leases that are wholly or partially guaranteed by the U.S. Government, excluding FDIC-loss sharing agreements'
                    if name:
                        return self.name
                    return row['RCONC240']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: total loans and leases that are wholly or partially guaranteed by the U.S. Government, excluding FDIC-loss sharing agreements'
                    if name:
                        return self.name
                    return row['RCONC241']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: total loans and leases that are wholly or partially guaranteed by the U.S. Government, excluding FDIC-loss sharing agreements'
                    if name:
                        return self.name
                    return row['RCONC226']

        class SecuredRealEstate:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.SFR = self.SFR(self)

            def ConstructionSFR(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: 1-4 family residential construction loans secured by real estate'
                    if name:
                        return self.name
                    return row['RCONF172']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: 1-4 family residential construction loans secured by real estate'
                    if name:
                        return self.name
                    return row['RCONF174']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: 1-4 family residential construction loans secured by real estate'
                    if name:
                        return self.name
                    return row['RCONF176']

            def ConstructionOther(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: 1-4 family residential construction loans secured by real estate'
                    if name:
                        return self.name
                    return row['RCONF173']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: 1-4 family residential construction loans secured by real estate'
                    if name:
                        return self.name
                    return row['RCONF175']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: 1-4 family residential construction loans secured by real estate'
                    if name:
                        return self.name
                    return row['RCONF177']

            def Farmland(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: secured by farmland in domestic offices'
                    if name:
                        return self.name
                    return row['RCON3493']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: secured by farmland in domestic offices'
                    if name:
                        return self.name
                    return row['RCON3494']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: secured by farmland in domestic offices'
                    if name:
                        return self.name
                    return row['RCON3495']

            class SFR:

                def __init__(self, parent):
                    self.parent = parent
                    self.root = parent.root
                    self.row = self.root.row

                def OpenEndRevolving(self, column, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if column == 'A' or column == 'past due 30 days':
                        self.name = 'Past due by 30 days to 89 days: revolving, open-end loans secured by 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCON5398']
                    if column == 'B' or column == 'past due 90 days':
                        self.name = 'Past due by 90 or more: revolving, open-end loans secured by 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCON5399']
                    if column == 'C' or column == 'nonaccrual':
                        self.name = 'nonaccrual: revolving, open-end loans secured by 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCON5400']

                def ClosedEndFirstLiens(self, column, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if column == 'A' or column == 'past due 30 days':
                        self.name = 'Past due by 30 days to 89 days: closed-end loans secured by first lien 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCONC236']
                    if column == 'B' or column == 'past due 90 days':
                        self.name = 'Past due by 90 or more: closed-end loans secured by first lien 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCONC237']
                    if column == 'C' or column == 'nonaccrual':
                        self.name = 'nonaccrual: closed-end loans secured by first lien 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCONC229']

                def ClosedEndJuniorLiens(self, column, name=False, *args, date='P0', **kwargs):
                    row = self.root.get_row(date)
                    if column == 'A' or column == 'past due 30 days':
                        self.name = 'Past due by 30 days to 89 days: closed-end loans secured by junior lien 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCONC238']
                    if column == 'B' or column == 'past due 90 days':
                        self.name = 'Past due by 90 or more: closed-end loans secured by junior lien 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCONC239']
                    if column == 'C' or column == 'nonaccrual':
                        self.name = 'nonaccrual: closed-end loans secured by junior lien 1-4 family residential properties in domestic offices'
                        if name:
                            return self.name
                        return row['RCONC230']

            def SecuredMultifamily(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: secured by multifamily (5 or more) residential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCON3499']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: secured by multifamily (5 or more) residential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCON3500']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: secured by multifamily (5 or more) residential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCON3501']

            def SecuredNonfarmOwner(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: secured by owner-occupied nonfarm nonresidential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF178']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: secured by owner-occupied nonfarm nonresidential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF180']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: secured by owner-occupied nonfarm nonresidential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF182']

            def SecuredNonfarmOther(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: secured by other nonfarm nonresidential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF179']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: secured by other nonfarm nonresidential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF181']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: secured by other nonfarm nonresidential properties in domestic offices'
                    if name:
                        return self.name
                    return row['RCONF183']

        class DepositoryInstitutions:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def USBanksTotal(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: Loans to U.S. banks and other depository institutions in the U.S.'
                    if name:
                        return self.name
                    return row['RCONB834']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: Loans to U.S. banks and other depository institutions in the U.S.'
                    if name:
                        return self.name
                    return row['RCONB835']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: Loans to U.S. banks and other depository institutions in the U.S.'
                    if name:
                        return self.name
                    return row['RCONB836']

            def ForeignBanks(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: Loans to foreign banks'
                    if name:
                        return self.name
                    return row['RCON5380']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: Loans to foreign banks'
                    if name:
                        return self.name
                    return row['RCON5381']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: Loans to foreign banks'
                    if name:
                        return self.name
                    return row['RCON5382']

        def FinanceAgricultural(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A' or column == 'past due 30 days':
                self.name = 'Past due by 30 days to 89 days: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCON1594']
            if column == 'B' or column == 'past due 90 days':
                self.name = 'Past due by 90 or more: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCON1597']
            if column == 'C' or column == 'nonaccrual':
                self.name = 'nonaccrual: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCON1583']

        def CommercialAndIndustrial(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A' or column == 'past due 30 days':
                self.name = 'Past due by 30 days to 89 days: commerical and industrial loans in domestic offices'
                if name:
                    return self.name
                return row['RCON1254']
            if column == 'B' or column == 'past due 90 days':
                self.name = 'Past due by 90 or more: commerical and industrial loans in domestic offices'
                if name:
                    return self.name
                return row['RCON1255']
            if column == 'C' or column == 'nonaccrual':
                self.name = 'nonaccrual: commerical and industrial loans in domestic offices'
                if name:
                    return self.name
                return row['RCON1256']

        class Individuals:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row

            def CreditCards(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: Loans to individuals for credit card lines'
                    if name:
                        return self.name
                    return row['RCONB575']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: Loans to individuals for credit card lines'
                    if name:
                        return self.name
                    return row['RCONB576']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: Loans to individuals for credit card lines'
                    if name:
                        return self.name
                    return row['RCONB577']

            def AutomobileLoans(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: Loans to individuals for automobiles'
                    if name:
                        return self.name
                    return row['RCONK213']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: Loans to individuals for automobiles'
                    if name:
                        return self.name
                    return row['RCONK214']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: Loans to individuals for automobiles'
                    if name:
                        return self.name
                    return row['RCONK215']

            def OtherLoans(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A' or column == 'past due 30 days':
                    self.name = 'Past due by 30 days to 89 days: Loans to individuals for other purposes (includes RC-C Part I, item 6.c and 6.d)'
                    if name:
                        return self.name
                    return row['RCONK216']
                if column == 'B' or column == 'past due 90 days':
                    self.name = 'Past due by 90 or more: Loans to individuals for other purposes (includes RC-C Part I, item 6.c and 6.d)'
                    if name:
                        return self.name
                    return row['RCONK217']
                if column == 'C' or column == 'nonaccrual':
                    self.name = 'nonaccrual: Loans to individuals for other purposes (includes RC-C Part I, item 6.c and 6.d)'
                    if name:
                        return self.name
                    return row['RCONK218']

        def ForeignGovt(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A' or column == 'past due 30 days':
                self.name = 'Past due by 30 days to 89 days: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return float('nan')
            if column == 'B' or column == 'past due 90 days':
                self.name = 'Past due by 90 or more: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return float('nan')
            if column == 'C' or column == 'nonaccrual':
                self.name = 'nonaccrual: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return float('nan')

        def AllOtherLoans(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A' or column == 'past due 30 days':
                self.name = 'Past due by 30 days to 89 days: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCON5459']
            if column == 'B' or column == 'past due 90 days':
                self.name = 'Past due by 90 or more: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCON5460']
            if column == 'C' or column == 'nonaccrual':
                self.name = 'nonaccrual: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCON5461']

        def LeaseFinancingReceivables(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A' or column == 'past due 30 days':
                self.name = 'Past due by 30 days to 89 days: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCONF166']
            if column == 'B' or column == 'past due 90 days':
                self.name = 'Past due by 90 or more: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCONF167']
            if column == 'C' or column == 'nonaccrual':
                self.name = 'nonaccrual: loans to finance agricultural production and other loans to farmers'
                if name:
                    return self.name
                return row['RCONF168']

    class DepositInsurance:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.flags = {}
            self.messages = {}

        def Section3IDeposits(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Total deposit liabilities before exclusions (gross) defined in Section 3(I) of the Federal Deposit Insurance Act and FDIC regulations'
            if name:
                return self.name
            return row['RCONF236']

        def TotalAllowableExclusions(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Total allowable exclusions, including interest acrrued and unpaid on allowable exclusions'
            if name:
                return self.name
            return row['RCONF237']

        def TotalForeignDeposits(self, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            self.name = 'Total deposits in foreign offices (not applicable to FFIEC 051 filers)'
            if name:
                return self.name
            return 0.0

    class MeasuredAtFV:

        def __init__(self, parent):
            self.parent = parent
            self.root = parent.root
            self.row = self.root.row
            self.TradingAssets = self.TradingAssets(self)
            self.TradingLiabilities = self.TradingLiabilities(self)
            self.flags = {}
            self.messages = {}

        def AFSSecurities(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Available-for-Sale debt securities and equity securities with readily determinable fair value not held for trading, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCONJA36']
            elif column == 'B':
                self.name = 'Available-for-Sale debt securities and equity securities with readily determinable fair value not held for trading, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCONG474']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Available-for-Sale debt securities and equity securities with readily determinable fair value not held for trading, (Column C)'
                if name:
                    return self.name
                return row['RCONG475']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Available-for-Sale debt securities and equity securities with readily determinable fair value not held for trading, (Column D)'
                if name:
                    return self.name
                return row['RCONG476']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Available-for-Sale debt securities and equity securities with readily determinable fair value not held for trading, (Column E)'
                if name:
                    return self.name
                return row['RCONG477']

        def FederalFundsSold(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Federal funds sold and securities purchased under agreements to resell, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return float('nan')
            elif column == 'B':
                self.name = 'Federal funds sold and securities purchased under agreements to resell, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return float('nan')
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Federal funds sold and securities purchased under agreements to resell, (Column C)'
                if name:
                    return self.name
                return float('nan')
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Federal funds sold and securities purchased under agreements to resell, (Column D)'
                if name:
                    return self.name
                return float('nan')
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Federal funds sold and securities purchased under agreements to resell, (Column E)'
                if name:
                    return self.name
                return float('nan')

        def LoansAndLeasesHeldForSale(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Loans and leases held for sale, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCONG483']
            elif column == 'B':
                self.name = 'Loans and leases held for sale, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCONG484']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Loans and leases held for sale, (Column C)'
                if name:
                    return self.name
                return row['RCONG485']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Loans and leases held for sale, (Column D)'
                if name:
                    return self.name
                return row['RCONG486']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Loans and leases held for sale, (Column E)'
                if name:
                    return self.name
                return row['RCONG487']

        def LoansAndLeasesHeldForInvestment(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Loans and leases held for investment, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCONG488']
            elif column == 'B':
                self.name = 'Loans and leases held for investment, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCONG489']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Loans and leases held for investment, (Column C)'
                if name:
                    return self.name
                return row['RCONG490']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Loans and leases held for investment, (Column D)'
                if name:
                    return self.name
                return row['RCONG491']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Loans and leases held for investment, (Column E)'
                if name:
                    return self.name
                return row['RCONG492']

        class TradingAssets:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def Total(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A':
                    self.name = '([calculated] item 5.a & 5.b) Trading assets: derivative assets, (Column A) Reported on Schedule RC'
                    if name:
                        return self.name
                    return row['RCON3543'] + row['RCONG497']
                elif column == 'B':
                    self.name = '([calculated] item 5.a & 5.b) Trading assets: derivative assets, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                    if name:
                        return self.name
                    return row['RCONG493'] + row['RCONG498']
                elif column == 'C' or column == 'Level 1':
                    self.name = '([calculated] item 5.a & 5.b) Level 1 Fair Value Measurement: Trading assets: derivative assets, (Column C)'
                    if name:
                        return self.name
                    return row['RCONG494'] + row['RCONG499']
                elif column == 'D' or column == 'Level 2':
                    self.name = '([calculated] item 5.a & 5.b) Level 2 Fair Value Measurement: Trading assets: derivative assets, (Column D)'
                    if name:
                        return self.name
                    return row['RCONG495'] + row['RCONG500']
                elif column == 'E' or column == 'Level 3':
                    self.name = '([calculated] item 5.a & 5.b) Level 3 Fair Value Measurement: Trading assets: derivative assets, (Column E)'
                    if name:
                        return self.name
                    return row['RCONG496'] + row['RCONG501']

            def Derivatives(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A':
                    self.name = 'Trading assets: derivative assets, (Column A) Reported on Schedule RC'
                    if name:
                        return self.name
                    return row['RCON3543']
                elif column == 'B':
                    self.name = 'Trading assets: derivative assets, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                    if name:
                        return self.name
                    return row['RCONG493']
                elif column == 'C' or column == 'Level 1':
                    self.name = 'Level 1 Fair Value Measurement: Trading assets: derivative assets, (Column C)'
                    if name:
                        return self.name
                    return row['RCONG494']
                elif column == 'D' or column == 'Level 2':
                    self.name = 'Level 2 Fair Value Measurement: Trading assets: derivative assets, (Column D)'
                    if name:
                        return self.name
                    return row['RCONG495']
                elif column == 'E' or column == 'Level 3':
                    self.name = 'Level 3 Fair Value Measurement: Trading assets: derivative assets, (Column E)'
                    if name:
                        return self.name
                    return row['RCONG496']

            def OtherAssets(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A':
                    self.name = 'Trading assets: other assets, (Column A) Reported on Schedule RC'
                    if name:
                        return self.name
                    return row['RCONG497']
                elif column == 'B':
                    self.name = 'Trading assets: other assets, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                    if name:
                        return self.name
                    return row['RCONG498']
                elif column == 'C' or column == 'Level 1':
                    self.name = 'Level 1 Fair Value Measurement: Trading assets: other assets, (Column C)'
                    if name:
                        return self.name
                    return row['RCONG499']
                elif column == 'D' or column == 'Level 2':
                    self.name = 'Level 2 Fair Value Measurement: Trading assets: other assets, (Column D)'
                    if name:
                        return self.name
                    return row['RCONG500']
                elif column == 'E' or column == 'Level 3':
                    self.name = 'Level 3 Fair Value Measurement: Trading assets: other assets, (Column E)'
                    if name:
                        return self.name
                    return row['RCONG501']

        def AllOtherAssets(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'All other assets, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCONG391']
            elif column == 'B':
                self.name = 'All other assets, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCONG392']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: All other assets, (Column C)'
                if name:
                    return self.name
                return row['RCONG395']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: All other assets, (Column D)'
                if name:
                    return self.name
                return row['RCONG396']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: All other assets, (Column E)'
                if name:
                    return self.name
                return row['RCONG804']

        def DepositLiabilities(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Deposit liabilities, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCONF252']
            elif column == 'B':
                self.name = 'Deposit liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCONF686']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Deposit liabilities, (Column C)'
                if name:
                    return self.name
                return row['RCONF694']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Deposit liabilities, (Column D)'
                if name:
                    return self.name
                return row['RCONF253']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Deposit liabilities, (Column E)'
                if name:
                    return self.name
                return row['RCONF254']

        def FederalFundsPurchased(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Federal funds purchased and securities sold with agreements to repurchase, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return float('nan')
            elif column == 'B':
                self.name = 'Federal funds purchased and securities sold with agreements to repurchase, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return float('nan')
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Federal funds purchased and securities sold with agreements to repurchase, (Column C)'
                if name:
                    return self.name
                return float('nan')
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Federal funds purchased and securities sold with agreements to repurchase, (Column D)'
                if name:
                    return self.name
                return float('nan')
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Federal funds purchased and securities sold with agreements to repurchase, (Column E)'
                if name:
                    return self.name
                return float('nan')

        class TradingLiabilities:

            def __init__(self, parent):
                self.parent = parent
                self.root = parent.root
                self.row = self.root.row
                self.flags = {}
                self.messages = {}

            def Total(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A':
                    self.name = '([calculated] item 10.a & 10.b) Trading liabilities: derivative liabilities, (Column A) Reported on Schedule RC'
                    if name:
                        return self.name
                    return row['RCON3547'] + row['RCONG516']
                elif column == 'B':
                    self.name = '([calculated] item 10.a & 10.b) Trading liabilities: derivative liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                    if name:
                        return self.name
                    return row['RCONG512'] + row['RCONG517']
                elif column == 'C' or column == 'Level 1':
                    self.name = '([calculated] item 10.a & 10.b) Level 1 Fair Value Measurement: Trading liabilities: derivative liabilities, (Column C)'
                    if name:
                        return self.name
                    return row['RCONG513'] + row['RCONG518']
                elif column == 'D' or column == 'Level 2':
                    self.name = '([calculated] item 10.a & 10.b) Level 2 Fair Value Measurement: Trading liabilities: derivative liabilities, (Column D)'
                    if name:
                        return self.name
                    return row['RCONG514'] + row['RCONG519']
                elif column == 'E' or column == 'Level 3':
                    self.name = '([calculated] item 10.a & 10.b) Level 3 Fair Value Measurement: Trading liabilities: derivative liabilities, (Column E)'
                    if name:
                        return self.name
                    return row['RCONG515'] + row['RCONG520']

            def Derivatives(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A':
                    self.name = 'Trading aliabilities: derivative liabilities, (Column A) Reported on Schedule RC'
                    if name:
                        return self.name
                    return row['RCON3547']
                elif column == 'B':
                    self.name = 'Trading liabilities: derivative liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                    if name:
                        return self.name
                    return row['RCONG512']
                elif column == 'C' or column == 'Level 1':
                    self.name = 'Level 1 Fair Value Measurement: Trading liabilities: derivative liabilities, (Column C)'
                    if name:
                        return self.name
                    return row['RCONG513']
                elif column == 'D' or column == 'Level 2':
                    self.name = 'Level 2 Fair Value Measurement: Trading liabilities: derivative liabilities, (Column D)'
                    if name:
                        return self.name
                    return row['RCONG514']
                elif column == 'E' or column == 'Level 3':
                    self.name = 'Level 3 Fair Value Measurement: Trading liabilities: derivative liabilities, (Column E)'
                    if name:
                        return self.name
                    return row['RCONG515']

            def OtherLiabilities(self, column, name=False, *args, date='P0', **kwargs):
                row = self.root.get_row(date)
                if column == 'A':
                    self.name = 'Trading liabilities: other liabilities, (Column A) Reported on Schedule RC'
                    if name:
                        return self.name
                    return row['RCONG516']
                elif column == 'B':
                    self.name = 'Trading liabilities: other liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                    if name:
                        return self.name
                    return row['RCONG517']
                elif column == 'C' or column == 'Level 1':
                    self.name = 'Level 1 Fair Value Measurement: Trading liabilities: other liabilities, (Column C)'
                    if name:
                        return self.name
                    return row['RCONG518']
                elif column == 'D' or column == 'Level 2':
                    self.name = 'Level 2 Fair Value Measurement: Trading liabilities: other liabilities, (Column D)'
                    if name:
                        return self.name
                    return row['RCONG519']
                elif column == 'E' or column == 'Level 3':
                    self.name = 'Level 3 Fair Value Measurement: Trading liabilities: other liabilities, (Column E)'
                    if name:
                        return self.name
                    return row['RCONG520']

        def SubordinatedNotes(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Subordinated notes and debentures, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return float('nan')
            elif column == 'B':
                self.name = 'Subordinated notes and debentures, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return float('nan')
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Subordinated notes and debentures, (Column C)'
                if name:
                    return self.name
                return float('nan')
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Subordinated notes and debentures, (Column D)'
                if name:
                    return self.name
                return float('nan')
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Subordinated notes and debentures, (Column E)'
                if name:
                    return self.name
                return float('nan')

        def OtherLiabilities(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'All other liabilities, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCONG805']
            elif column == 'B':
                self.name = 'All other liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCONG806']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: All other liabilities, (Column C)'
                if name:
                    return self.name
                return row['RCONG807']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: All other liabilities, (Column D)'
                if name:
                    return self.name
                return row['RCONG808']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: All other liabilities, (Column E)'
                if name:
                    return self.name
                return row['RCONG809']

        def TotalLiabilities(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Total liabilities, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCONG531']
            elif column == 'B':
                self.name = 'Total liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCONG532']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Total liabilities, (Column C)'
                if name:
                    return self.name
                return row['RCONG533']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Total liabilities, (Column D)'
                if name:
                    return self.name
                return row['RCONG534']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Total liabilities, (Column E)'
                if name:
                    return self.name
                return row['RCONG535']

        def MSAs(self, column, name=False, *args, date='P0', **kwargs):
            row = self.root.get_row(date)
            if column == 'A':
                self.name = 'Total liabilities, (Column A) Reported on Schedule RC'
                if name:
                    return self.name
                return row['RCONG536']
            elif column == 'B':
                self.name = 'Total liabilities, (Column B) LESS: Amounts netted in the Determination of Total Fair Value'
                if name:
                    return self.name
                return row['RCONG537']
            elif column == 'C' or column == 'Level 1':
                self.name = 'Level 1 Fair Value Measurement: Total liabilities, (Column C)'
                if name:
                    return self.name
                return row['RCONG538']
            elif column == 'D' or column == 'Level 2':
                self.name = 'Level 2 Fair Value Measurement: Total liabilities, (Column D)'
                if name:
                    return self.name
                return row['RCONG539']
            elif column == 'E' or column == 'Level 3':
                self.name = 'Level 3 Fair Value Measurement: Total liabilities, (Column E)'
                if name:
                    return self.name
                return row['RCONG540']
__all__ = ['CallReport_031', 'CallReport_051', 'DEFAULT_HISTORY', 'Global_uc', 'LagSupport', 'QuarterCache', 'safe_divide']
