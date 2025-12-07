import pandas as pd
import plotly.express as px

from .base import PlotPage, build_customdata


class TopMerchantsPage(PlotPage):
    title = "Top Merchants"
    slug = "top_merchants"
    description = "Spend by merchant (top 15)."

    def __init__(self, top_n: int = 15):
        self.top_n = top_n

    def generate(self, df: pd.DataFrame, out_dir: str) -> str:
        by_merchant = (
            df.groupby("merchant")["amount"].sum().sort_values(ascending=False).head(self.top_n).reset_index()
        )

        custom = build_customdata(df, by_merchant["merchant"], lambda frame, m: frame[frame["merchant"] == m])

        fig = px.bar(
            by_merchant,
            x="amount",
            y="merchant",
            orientation="h",
            labels={"amount": "Total spending (CAD)", "merchant": "Merchant"},
            title=f"Top {self.top_n} Merchants by Spend",
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        fig.update_traces(customdata=custom, hovertemplate="Merchant: %{y}<br>Spend: %{x:.2f}<extra></extra>")

        fig_html = fig.to_html(full_html=False, include_plotlyjs="cdn", div_id=f"chart-{self.slug}")
        return self.save_page(fig_html, out_dir)
