# BuildExe.pyw — Double-click to rebuild SheetTool.exe from SheetTool.spec
# Shows a small window with build progress.
import sys
import os
import subprocess
import shutil
import threading
import tkinter as tk
from tkinter import scrolledtext

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SPEC_FILE = os.path.join(SCRIPT_DIR, "SheetTool.spec")
DIST_EXE = os.path.join(SCRIPT_DIR, "dist", "SheetTool.exe")
ROOT_EXE = os.path.join(SCRIPT_DIR, "SheetTool.exe")


def build(text_widget, status_var, btn):
    """Run pyinstaller and stream output into the text widget."""
    status_var.set("Building...")

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "PyInstaller", SPEC_FILE],
            cwd=SCRIPT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        for line in proc.stdout:
            text_widget.insert(tk.END, line)
            text_widget.see(tk.END)

        proc.wait()

        if proc.returncode != 0:
            status_var.set(f"Build FAILED (exit code {proc.returncode})")
            btn.configure(state="normal")
            return

        # Copy the new exe to the project root
        if os.path.isfile(DIST_EXE):
            shutil.copy2(DIST_EXE, ROOT_EXE)
            text_widget.insert(tk.END, f"\nCopied exe to {ROOT_EXE}\n")
            text_widget.see(tk.END)

        status_var.set("Build complete!")

    except FileNotFoundError:
        status_var.set("ERROR: PyInstaller not found")
        text_widget.insert(tk.END, "\nPyInstaller is not installed.\n")
        text_widget.insert(tk.END, "Run:  pip install pyinstaller\n")
        text_widget.see(tk.END)
    except Exception as e:
        status_var.set(f"ERROR: {e}")
        text_widget.insert(tk.END, f"\n{e}\n")
        text_widget.see(tk.END)

    btn.configure(state="normal")


def main():
    root = tk.Tk()
    root.title("Build SheetTool.exe")
    root.geometry("700x420")

    status_var = tk.StringVar(value="Ready — click Build to start")
    tk.Label(root, textvariable=status_var, font=("Segoe UI", 11, "bold")).pack(
        padx=10, pady=(10, 4), anchor="w"
    )

    log = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=20, font=("Consolas", 9))
    log.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

    btn = tk.Button(
        root, text="Build", font=("Segoe UI", 10),
        command=lambda: start_build(log, status_var, btn),
    )
    btn.pack(pady=(4, 10))

    def start_build(tw, sv, b):
        b.configure(state="disabled")
        tw.delete("1.0", tk.END)
        threading.Thread(target=build, args=(tw, sv, b), daemon=True).start()

    root.mainloop()


if __name__ == "__main__":
    main()
