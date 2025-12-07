from typing import List

from .daily import DailySpendingPage
from .histogram import AmountHistogramPage
from .monthly import MonthlySpendingPage
from .top_merchants import TopMerchantsPage


def get_plot_pages(rolling_window: int = 7) -> List:
    return [
        MonthlySpendingPage(),
        DailySpendingPage(window=rolling_window),
        AmountHistogramPage(),
        TopMerchantsPage(),
    ]
