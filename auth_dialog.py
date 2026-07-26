from __future__ import annotations

import threading
import tkinter as tk
from typing import Callable, Optional


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
    "ok": "#3dba8b",
}

FONTS = {
    "title": ("Lato", 16, "bold"),
    "body": ("Lato", 11),
    "label": ("Lato", 10),
    "button": ("Lato", 12, "bold"),
}


class ConnectDriveDialog(tk.Toplevel):
    """Popup shown when Google Drive is not connected.

    Google does not allow apps to collect your Gmail password directly.
    Email is optional (hint); Sign in opens Google's secure browser login.
    """

    def __init__(
        self,
        parent: tk.Tk,
        on_connect: Callable[[], str],
        initial_email: str = "",
    ) -> None:
        super().__init__(parent)
        self.title("Connect Google Drive")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._on_connect = on_connect
        self.result_email: Optional[str] = None
        self._busy = False

        self.geometry("400x340")
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - 400) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - 340) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

        frame = tk.Frame(self, bg=COLORS["bg"], padx=24, pady=22)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            frame,
            text="Google Drive not connected",
            font=FONTS["title"],
            fg=COLORS["ink"],
            bg=COLORS["bg"],
            anchor="w",
        ).pack(fill=tk.X)

        tk.Label(
            frame,
            text=(
                "Sign in with your Google account to upload screenshots. "
                "Enter your email below, then continue — Google will ask for "
                "your password in the browser (apps cannot store Google passwords)."
            ),
            font=FONTS["body"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            wraplength=340,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(10, 18))

        tk.Label(
            frame,
            text="EMAIL",
            font=FONTS["label"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            anchor="w",
        ).pack(fill=tk.X)

        self.email_var = tk.StringVar(value=initial_email)
        self.email_entry = tk.Entry(
            frame,
            textvariable=self.email_var,
            font=FONTS["body"],
            bg=COLORS["bg_soft"],
            fg=COLORS["ink"],
            insertbackground=COLORS["ink"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
        )
        self.email_entry.pack(fill=tk.X, ipady=8, pady=(4, 14))

        tk.Label(
            frame,
            text="PASSWORD",
            font=FONTS["label"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            anchor="w",
        ).pack(fill=tk.X)

        self.pass_var = tk.StringVar()
        self.pass_entry = tk.Entry(
            frame,
            textvariable=self.pass_var,
            show="•",
            font=FONTS["body"],
            bg=COLORS["bg_soft"],
            fg=COLORS["muted"],
            insertbackground=COLORS["ink"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
            state="readonly",
        )
        self.pass_entry.pack(fill=tk.X, ipady=8, pady=(4, 4))

        tk.Label(
            frame,
            text="Password is entered on Google’s secure page after you click Sign in.",
            font=FONTS["label"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            wraplength=340,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 14))

        self.message_var = tk.StringVar(value="")
        self.message_label = tk.Label(
            frame,
            textvariable=self.message_var,
            font=FONTS["label"],
            fg=COLORS["error"],
            bg=COLORS["bg"],
            wraplength=340,
            justify=tk.LEFT,
            anchor="w",
        )
        self.message_label.pack(fill=tk.X, pady=(0, 10))

        actions = tk.Frame(frame, bg=COLORS["bg"])
        actions.pack(fill=tk.X)

        self.connect_btn = tk.Button(
            actions,
            text="Sign in with Google",
            command=self._start_connect,
            font=FONTS["button"],
            bg=COLORS["accent"],
            fg=COLORS["accent_text"],
            activebackground=COLORS["accent_dim"],
            activeforeground=COLORS["accent_text"],
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=10,
            cursor="hand2",
            highlightthickness=0,
        )
        self.connect_btn.pack(side=tk.LEFT)

        cancel_btn = tk.Button(
            actions,
            text="Cancel",
            command=self._cancel,
            font=FONTS["button"],
            bg=COLORS["bg_soft"],
            fg=COLORS["ink"],
            activebackground=COLORS["line"],
            activeforeground=COLORS["ink"],
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=10,
            cursor="hand2",
            highlightthickness=0,
        )
        cancel_btn.pack(side=tk.LEFT, padx=(10, 0))

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.email_entry.focus_set()

    def _set_message(self, text: str, ok: bool = False) -> None:
        self.message_var.set(text)
        self.message_label.configure(fg=COLORS["ok"] if ok else COLORS["error"])

    def _start_connect(self) -> None:
        if self._busy:
            return
        email = self.email_var.get().strip()
        if email and "@" not in email:
            self._set_message("Enter a valid email, or leave it blank.")
            return

        self._busy = True
        self.connect_btn.configure(state=tk.DISABLED, text="Opening browser…")
        self._set_message("Complete sign-in in your browser…", ok=True)

        def worker() -> None:
            try:
                connected = self._on_connect()
                self.after(0, lambda: self._on_success(connected))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda m=message: self._on_failure(m))

        threading.Thread(target=worker, daemon=True).start()

    def _on_success(self, email: str) -> None:
        self.result_email = email
        self._busy = False
        self.destroy()

    def _on_failure(self, message: str) -> None:
        self._busy = False
        self.connect_btn.configure(state=tk.NORMAL, text="Sign in with Google")
        self._set_message(message)

    def _cancel(self) -> None:
        if self._busy:
            return
        self.result_email = None
        self.destroy()
