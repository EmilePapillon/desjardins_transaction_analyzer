import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


def format_rows_for_detail(rows: pd.DataFrame) -> List[Dict]:
    """Convert rows into serializable dicts for Plotly customdata."""
    subset = rows[["transaction_date", "description", "amount"]].copy()
    subset["transaction_date"] = subset["transaction_date"].astype(str)
    subset["description"] = subset["description"].astype(str)
    return subset.to_dict(orient="records")


def wrap_html_with_detail(fig_html: str, title: str, chart_id: str, detail_id: str, back_link: Optional[str] = "index.html") -> str:
    """Embed a detail container and click handler alongside Plotly chart HTML."""
    style = """
    <style>
    body { font-family: Arial, sans-serif; margin: 0 auto; padding: 16px; max-width: 1100px; }
    .detail-box { margin-top: 12px; padding: 12px; border: 1px solid #ddd; border-radius: 6px; background: #fafafa; }
    .detail-box table { border-collapse: collapse; width: 100%; }
    .detail-box th, .detail-box td { text-align: left; padding: 6px; border-bottom: 1px solid #eee; }
    .detail-box th { cursor: pointer; user-select: none; }
    .detail-box tr:hover { background: #f2f2f2; }
    </style>
    """
    script = f"""
    <script>
    (function() {{
      const chart = document.getElementById('{chart_id}');
      const detail = document.getElementById('{detail_id}');
      if (!chart || !detail) return;
      const state = {{ rows: [], baseRows: [], sortKey: null, sortDir: 'none' }};
      const comparator = (a, b, key) => {{
        const va = a[key];
        const vb = b[key];
        if (key === 'amount') {{
          return (parseFloat(va) || 0) - (parseFloat(vb) || 0);
        }}
        return String(va || '').localeCompare(String(vb || ''), undefined, {{ numeric: true }});
      }};
      const cycleDir = (current) => current === 'none' ? 'asc' : current === 'asc' ? 'desc' : 'none';
      const applySort = () => {{
        if (state.sortDir === 'none' || !state.sortKey) return state.baseRows.slice();
        const sorted = state.baseRows.slice().sort((a,b) => comparator(a,b,state.sortKey));
        if (state.sortDir === 'desc') sorted.reverse();
        return sorted;
      }};
      const dirSymbol = (key) => {{
        if (state.sortKey !== key) return '';
        return state.sortDir === 'asc' ? ' ↑' : state.sortDir === 'desc' ? ' ↓' : '';
      }};
      const renderTable = () => {{
        if (!state.baseRows.length) {{
          detail.innerHTML = '<strong>No transactions for this selection.</strong>';
          return;
        }}
        const header = `<tr>
          <th data-sort="transaction_date">Date${{dirSymbol('transaction_date')}}</th>
          <th data-sort="description">Description${{dirSymbol('description')}}</th>
          <th data-sort="amount">Amount${{dirSymbol('amount')}}</th>
        </tr>`;
        const rows = applySort();
        const body = rows.map(r => {{
          const amt = typeof r.amount === 'number' ? r.amount.toFixed(2) : r.amount;
          return `<tr><td>${{r.transaction_date || ''}}</td><td>${{r.description || ''}}</td><td>${{amt}}</td></tr>`;
        }}).join('');
        const sortLabel = state.sortDir === 'none' ? '' : ' (sorted ' + state.sortDir + ' by ' + state.sortKey + ')';
        detail.innerHTML = `<h3>{title} — Transactions</h3><table>` + header + body + '</table><div>' + rows.length + ' transaction(s)' + sortLabel + '</div>';
      }};
      chart.on('plotly_click', function(ev) {{
        if (!ev.points || !ev.points.length) return;
        const rows = ev.points[0].customdata || [];
        state.baseRows = rows.slice();
        state.sortKey = null;
        state.sortDir = 'none';
        renderTable();
      }});
      detail.addEventListener('click', (ev) => {{
        const th = ev.target.closest('th[data-sort]');
        if (!th) return;
        const key = th.getAttribute('data-sort');
        state.sortDir = cycleDir(state.sortDir);
        state.sortKey = state.sortDir === 'none' ? null : key;
        renderTable();
      }});
    }})();
    </script>
    """
    back_html = ""
    if back_link:
        back_html = f"<p><a href='{back_link}'>&larr; Back to index</a></p>"
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title}</title>{style}</head><body>{back_html}{fig_html}<div id='{detail_id}' class='detail-box'>Click a bar/point to see transactions.</div>{script}</body></html>"


class PlotPage(ABC):
    title: str
    slug: str
    description: str = ""

    @property
    def filename(self) -> str:
        return f"{self.slug}.html"

    @abstractmethod
    def generate(self, df: pd.DataFrame, out_dir: str) -> str:
        """Generate the plot page and return the output file path."""
        raise NotImplementedError
