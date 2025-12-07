import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .base import PlotPage, build_customdata


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
            custom = build_customdata(positive, bin_df["bin"], lambda frame, interval: frame[frame["bin"] == interval])

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
        return self.save_page(fig_html, out_dir)
