from __future__ import annotations

import tkinter as tk
from typing import Optional


COLORS = {
    "bg": "#1a2332",
    "bg_soft": "#2c3b52",
    "ink": "#e8eef6",
    "muted": "#8fa3bc",
    "line": "#3a4d66",
    "accent": "#e8a54b",
    "accent_dim": "#c4842f",
    "accent_text": "#1a2332",
    "error": "#e07a6a",
}

FONTS = {
    "title": ("Lato", 14, "bold"),
    "body": ("Lato", 10),
    "label": ("Lato", 9),
    "button": ("Lato", 10, "bold"),
}


class ShareLinkDialog(tk.Toplevel):
    """Paste the Apps Script web-app /exec URL (no Google credentials in Tracker)."""

    def __init__(self, parent: tk.Tk, initial_link: str = "") -> None:
        super().__init__(parent)
        self.title("Share session")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result_link: Optional[str] = None
        self.geometry("440x250")
        self.update_idletasks()
        px = parent.winfo_rootx() + max(0, (parent.winfo_width() - 440) // 2)
        py = parent.winfo_rooty() + max(0, (parent.winfo_height() - 250) // 2)
        self.geometry(f"+{px}+{py}")

        frame = tk.Frame(self, bg=COLORS["bg"], padx=20, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            frame,
            text="Drive upload link",
            font=FONTS["title"],
            fg=COLORS["ink"],
            bg=COLORS["bg"],
            anchor="w",
        ).pack(fill=tk.X)

        tk.Label(
            frame,
            text=(
                "Paste your Apps Script web-app URL (ends with /exec). "
                "No Google login in this app — see drive_upload/README.md."
            ),
            font=FONTS["body"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            wraplength=390,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(8, 12))

        self.link_var = tk.StringVar(value=initial_link)
        entry = tk.Entry(
            frame,
            textvariable=self.link_var,
            font=FONTS["body"],
            bg=COLORS["bg_soft"],
            fg=COLORS["ink"],
            insertbackground=COLORS["ink"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
        )
        entry.pack(fill=tk.X, ipady=8)
        entry.focus_set()
        entry.bind("<Return>", lambda _e: self._save())

        self.message_var = tk.StringVar(value="")
        tk.Label(
            frame,
            textvariable=self.message_var,
            font=FONTS["label"],
            fg=COLORS["error"],
            bg=COLORS["bg"],
            wraplength=390,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(8, 10))

        actions = tk.Frame(frame, bg=COLORS["bg"])
        actions.pack(fill=tk.X)

        tk.Button(
            actions,
            text="Share session",
            command=self._save,
            font=FONTS["button"],
            bg=COLORS["accent"],
            fg=COLORS["accent_text"],
            activebackground=COLORS["accent_dim"],
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.LEFT)

        tk.Button(
            actions,
            text="Cancel",
            command=self._cancel,
            font=FONTS["button"],
            bg=COLORS["bg_soft"],
            fg=COLORS["ink"],
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(8, 0))

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _save(self) -> None:
        link = self.link_var.get().strip()
        if not link:
            self.message_var.set("Paste the /exec web-app link first.")
            return
        self.result_link = link
        self.destroy()

    def _cancel(self) -> None:
        self.result_link = None
        self.destroy()
