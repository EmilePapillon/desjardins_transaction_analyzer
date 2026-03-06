import os
from abc import ABC, abstractmethod

import pandas as pd

from ui.detail import wrap_html_with_detail


class PlotPage(ABC):
    title: str
    slug: str
    description: str = ""

    @property
    def filename(self) -> str:
        return f"{self.slug}.html"

    def save_page(self, fig_html: str, out_dir: str) -> str:
        """Wrap the chart HTML with detail UI and write to disk."""
        html = wrap_html_with_detail(fig_html, self.title, f"chart-{self.slug}", f"detail-{self.slug}")
        out_path = os.path.join(out_dir, self.filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        return out_path

    @abstractmethod
    def generate(self, df: pd.DataFrame, out_dir: str) -> str:
        """Generate the plot page and return the output file path."""
        raise NotImplementedError
