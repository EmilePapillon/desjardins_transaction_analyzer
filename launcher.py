#!/usr/bin/env python3
"""
Minimal GUI wrapper for the analyzer.
Steps:
1) User picks a ZIP of statements.
2) User picks an output directory for the charts/CSV.
3) We unzip to a temp dir, then run analyse.py once (which parses + plots).
"""
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
import importlib

import tkinter as tk
from tkinter import filedialog, messagebox

# Ensure PyInstaller bundles these modules
try:
    import main as extractor  # noqa: F401
    import analyse as analyzer  # noqa: F401
except Exception:
    pass


def run_cmd(args, cwd):
    """
    Run a command and raise on failure.
    In PyInstaller-frozen mode, avoid spawning another instance of the launcher by running the
    target scripts in-process via runpy.
    """
    if getattr(sys, "frozen", False):
        # args like [sys.executable, script_path, ...]
        script_path = Path(args[1])
        module_name = script_path.stem
        argv = args[2:]
        old_cwd = os.getcwd()
        old_argv = sys.argv
        try:
            os.chdir(cwd)
            sys.argv = [f"{module_name}.py"] + argv
            mod = importlib.import_module(module_name)
            cmd = getattr(mod, "main", None)
            if cmd is None:
                raise RuntimeError(f"Module {module_name} has no main")
            if hasattr(cmd, "main"):
                cmd.main(args=argv, standalone_mode=False)
            else:
                cmd(args=argv, standalone_mode=False)
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)
        return None
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
    frozen = getattr(sys, "frozen", False)
    messagebox.showinfo(
        "Step 1",
        "Pick the ZIP file you downloaded from Desjardins (Last 12 months).",
    )
    zip_path = choose_zip()
    if not zip_path:
        return

    if frozen:
        out_dir = Path(tempfile.mkdtemp(prefix="desj-analysis-"))
    else:
        messagebox.showinfo(
            "Step 2",
            "Choose where to save the results (transactions.csv and charts).",
        )
        chosen = choose_output_dir()
        if not chosen:
            return
        out_dir = Path(chosen)

    try:
        status_label.config(text="Unzipping statements...")
        root.update()
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(temp_dir)

            repo_root = Path(__file__).resolve().parent
            analyse_py = repo_root / "analyse.py"
            csv_path = Path(out_dir) / "transactions.csv"

            status_label.config(text="Parsing and generating charts...")
            root.update()
            run_cmd(
                [
                    sys.executable,
                    str(analyse_py),
                    "-i",
                    temp_dir,
                    "-o",
                    str(out_dir),
                    "--csv-output",
                    str(csv_path),
                ],
                cwd=str(repo_root),
            )

        # Open index.html
        index_path = Path(out_dir) / "index.html"
        if index_path.exists():
            try:
                if sys.platform == "darwin":
                    subprocess.run(["open", str(index_path)])
                elif sys.platform.startswith("win"):
                    os.startfile(index_path)  # type: ignore[attr-defined]
                else:
                    subprocess.run(["xdg-open", str(index_path)])
            except Exception:
                pass

        status_label.config(text="Done.")
        # messagebox.showinfo("Finished", f"Analysis complete.\nOutputs in:\n{out_dir}")
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
