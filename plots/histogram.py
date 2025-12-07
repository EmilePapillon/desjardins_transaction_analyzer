import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .base import PlotPage, format_rows_for_detail, wrap_html_with_detail


class AmountHistogramPage(PlotPage):
    title = "Amount Distribution"
    slug = "amount_histogram"
    description = "Histogram of transaction amounts."

    def generate(self, df: pd.DataFrame, out_dir: str) -> str:
        positive = df[df["amount"] > 0].copy()
        if positive.empty:
            fig = go.Figure()
            fig.update_layout(title="Distribution of Transaction Amounts")
            custom = []
        else:
            positive["bin"] = pd.cut(positive["amount"], bins=40, include_lowest=True)
            bin_df = positive.groupby("bin")["amount"].agg(count="size").reset_index().sort_values("bin")
            bin_df["bin_label"] = bin_df["bin"].astype(str)
            custom = [format_rows_for_detail(positive[positive["bin"] == interval]) for interval in bin_df["bin"]]

            fig = px.bar(
                bin_df,
                x="bin_label",
                y="count",
                labels={"bin_label": "Amount range (CAD)", "count": "Transaction count"},
                title="Distribution of Transaction Amounts",
            )
            fig.update_layout(xaxis_tickangle=-45)
            fig.update_traces(customdata=custom, hovertemplate="Range: %{x}<br>Count: %{y}<extra></extra>")

        fig_html = fig.to_html(full_html=False, include_plotlyjs="cdn", div_id=f"chart-{self.slug}")
        html = wrap_html_with_detail(fig_html, self.title, f"chart-{self.slug}", f"detail-{self.slug}")

        out_path = os.path.join(out_dir, self.filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        return out_path
