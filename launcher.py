#!/usr/bin/env python3
"""
Minimal GUI wrapper for the extractor + analyzer.
Steps:
1) User picks a ZIP of statements.
2) User picks an output directory for the charts/CSV.
3) We unzip to a temp dir, run main.py, then analyse.py.
"""
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox


def run_cmd(args, cwd):
    """Run a command and raise on failure."""
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed:\n{result.stderr or result.stdout}")
    return result


def choose_zip():
    return filedialog.askopenfilename(
        title="Select statements ZIP file",
        filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
    )


def choose_output_dir():
    return filedialog.askdirectory(title="Select output folder for analysis")


def on_run(status_label, root):
    zip_path = choose_zip()
    if not zip_path:
        return

    out_dir = choose_output_dir()
    if not out_dir:
        return

    try:
        status_label.config(text="Unzipping statements...")
        root.update()
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(temp_dir)

            repo_root = Path(__file__).resolve().parent
            main_py = repo_root / "main.py"
            analyse_py = repo_root / "analyse.py"
            csv_path = Path(out_dir) / "transactions.csv"

            status_label.config(text="Extracting transactions...")
            root.update()
            run_cmd(
                [sys.executable, str(main_py), "-i", temp_dir, "-o", str(csv_path)],
                cwd=str(repo_root),
            )

            status_label.config(text="Generating charts...")
            root.update()
            run_cmd(
                [sys.executable, str(analyse_py), "-i", str(csv_path), "-o", str(out_dir)],
                cwd=str(repo_root),
            )

        status_label.config(text="Done.")
        messagebox.showinfo("Finished", f"Analysis complete.\nOutputs in:\n{out_dir}")
        # Try to open the output directory
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", out_dir])
            elif sys.platform.startswith("win"):
                os.startfile(out_dir)  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", out_dir])
        except Exception:
            pass
    except Exception as exc:
        status_label.config(text="Error.")
        messagebox.showerror("Error", str(exc))


def main():
    root = tk.Tk()
    root.title("Desjardins Statement Analyzer")
    root.geometry("420x180")

    lbl = tk.Label(
        root,
        text="1) Pick your statements ZIP\n2) Pick output folder\n3) We extract and build charts for you.",
        justify="left",
        padx=10,
        pady=10,
    )
    lbl.pack(anchor="w")

    status_label = tk.Label(root, text="Ready", fg="gray")
    status_label.pack(anchor="w", padx=10)

    run_btn = tk.Button(root, text="Run analysis", command=lambda: on_run(status_label, root))
    run_btn.pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    main()
