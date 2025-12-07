import os

import pandas as pd
import plotly.express as px

from .base import PlotPage, format_rows_for_detail, wrap_html_with_detail


class DailySpendingPage(PlotPage):
    title = "Daily Spending"
    slug = "daily_spending"
    description = "Daily totals with rolling average."

    def __init__(self, window: int = 7):
        self.window = window

    def generate(self, df: pd.DataFrame, out_dir: str) -> str:
        daily = (
            df.groupby(df["transaction_date"].dt.date)["amount"]
            .sum()
            .reset_index()
            .rename(columns={"transaction_date": "date"})
            .sort_values("date")
        )
        daily["rolling_mean"] = daily["amount"].rolling(window=self.window, min_periods=1, center=False).mean()

        custom = [format_rows_for_detail(df[df["transaction_date"].dt.date == d]) for d in daily["date"]]

        fig = px.line(
            daily,
            x="date",
            y=["amount", "rolling_mean"],
            labels={"value": "Spending (CAD)", "date": "Date"},
            title=f"{self.title} (with {self.window}-day rolling average)",
        )
        fig.update_layout(legend_title_text="Series")
        if fig.data:
            fig.data[0].customdata = custom  # amount series
            fig.data[0].hovertemplate = "Date: %{x}<br>Amount: %{y:.2f}<extra></extra>"
        if len(fig.data) > 1:
            fig.data[1].hovertemplate = "Date: %{x}<br>Rolling mean: %{y:.2f}<extra></extra>"

        fig_html = fig.to_html(full_html=False, include_plotlyjs="cdn", div_id=f"chart-{self.slug}")
        html = wrap_html_with_detail(fig_html, self.title, f"chart-{self.slug}", f"detail-{self.slug}")

        out_path = os.path.join(out_dir, self.filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        return out_path
