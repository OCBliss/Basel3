"""Compatibility import for the independently installed CallReports library.

Install Basel3 requirements, or install CallReports with ``pip install CallReports``.
New code should import from ``callreports``.
"""

from callreports import (
    CallReport_031, CallReport_051, DEFAULT_HISTORY, Global_uc,
    LagSupport, QuarterCache, safe_divide,
)

__all__ = [
    "CallReport_031", "CallReport_051", "DEFAULT_HISTORY", "Global_uc",
    "LagSupport", "QuarterCache", "safe_divide",
]
