import pandas as pd
import plotly.express as px

from .base import PlotPage, build_customdata


class MonthlySpendingPage(PlotPage):
    title = "Monthly Spending"
    slug = "monthly_spending"
    description = "Total spend per month."

    def generate(self, df: pd.DataFrame, out_dir: str) -> str:
        monthly = (
            df.groupby("year_month")["amount"].agg(total="sum", count="size").reset_index().sort_values("year_month")
        )
        custom = build_customdata(df, monthly["year_month"], lambda frame, ym: frame[frame["year_month"] == ym])

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
        return self.save_page(fig_html, out_dir)
