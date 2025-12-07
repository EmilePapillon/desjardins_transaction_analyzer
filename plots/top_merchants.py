import os

import pandas as pd
import plotly.express as px

from .base import PlotPage, format_rows_for_detail, wrap_html_with_detail


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

        custom = [format_rows_for_detail(df[df["merchant"] == m]) for m in by_merchant["merchant"]]

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
        html = wrap_html_with_detail(fig_html, self.title, f"chart-{self.slug}", f"detail-{self.slug}")

        out_path = os.path.join(out_dir, self.filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        return out_path
