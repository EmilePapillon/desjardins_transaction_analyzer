import os

import pandas as pd
import plotly.express as px

from .base import PlotPage, format_rows_for_detail, wrap_html_with_detail


class MonthlySpendingPage(PlotPage):
    title = "Monthly Spending"
    slug = "monthly_spending"
    description = "Total spend per month."

    def generate(self, df: pd.DataFrame, out_dir: str) -> str:
        monthly = (
            df.groupby("year_month")["amount"].agg(total="sum", count="size").reset_index().sort_values("year_month")
        )
        custom = [format_rows_for_detail(df[df["year_month"] == ym]) for ym in monthly["year_month"]]

        fig = px.bar(
            monthly,
            x="year_month",
            y="total",
            labels={"year_month": "Month", "total": "Total spending (CAD)"},
            title=self.title,
            hover_data={"count": True},
        )
        fig.update_layout(xaxis_tickangle=-45)
        fig.update_traces(customdata=custom)

        fig_html = fig.to_html(full_html=False, include_plotlyjs="cdn", div_id=f"chart-{self.slug}")
        html = wrap_html_with_detail(fig_html, self.title, f"chart-{self.slug}", f"detail-{self.slug}")

        out_path = os.path.join(out_dir, self.filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        return out_path
