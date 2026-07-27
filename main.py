from __future__ import annotations

import json
import math
import subprocess
import threading
import tkinter as tk
from typing import Optional

from PIL import Image, ImageTk

from config import ASSETS_DIR, CAPTURES_DIR, DATA_DIR, ICON_PATH, SCREENSHOT_INTERVAL_SECONDS
from lap_dialog import LapNameDialog
from laps import LapStore
from screenshot import cleanup_old_day_folders, list_captures, take_screenshot
from share_dialog import ShareLinkDialog
from time_tracker import TimeTracker, format_duration
from todos import TodoStore
from uploader import DriveUploader


COLORS = {
    "bg": "#1a2332",
    "bg_mid": "#243044",
    "bg_soft": "#2c3b52",
    "ink": "#e8eef6",
    "muted": "#8fa3bc",
    "line": "#3a4d66",
    "accent": "#e8a54b",
    "accent_dim": "#c4842f",
    "accent_text": "#1a2332",
    "idle": "#5c6f88",
    "live": "#3dba8b",
    "error": "#e07a6a",
    "ok": "#3dba8b",
}

FONTS = {
    "brand": ("Lato", 20, "bold"),
    "label": ("Lato", 9),
    "value": ("DejaVu Sans Mono", 18),
    "session": ("DejaVu Sans Mono", 13),
    "status": ("Lato", 9),
    "button": ("Lato", 10, "bold"),
    "lap_name": ("Lato", 10),
    "lap_meta": ("DejaVu Sans Mono", 9),
    "lap_index": ("DejaVu Sans Mono", 9, "bold"),
    "empty": ("Lato", 9),
}


class TrackerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tracker")
        self.root.geometry("360x770")
        self.root.minsize(340, 710)
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg"])
        self._icon_images: list[ImageTk.PhotoImage] = []
        self._preview_image: Optional[ImageTk.PhotoImage] = None
        self._apply_window_icon()

        self.tracker = TimeTracker()
        self.uploader = DriveUploader()
        self.laps = LapStore()
        self.todos = TodoStore()

        self._running = False
        self._capture_job: Optional[str] = None
        self._tick_job: Optional[str] = None
        self._pulse_job: Optional[str] = None
        self._pulse_phase = 0.0
        self._upload_lock = threading.Lock()
        self._sharing = False
        self._screenshots_enabled = True

        self._build_ui()
        self._refresh_labels()
        self._refresh_share_status()
        self._refresh_todos_list()
        self._refresh_laps_list()
        removed = cleanup_old_day_folders()
        self._load_latest_preview()
        self._schedule_tick()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # Re-apply after map — GNOME/X11 often ignore icons set too early
        self.root.after_idle(self._apply_window_icon)
        self.root.bind("<Map>", lambda _e: self.root.after(10, self._apply_window_icon), add="+")
        if removed:
            self.root.after(
                0,
                lambda n=len(removed): self._set_status(
                    f"Removed {n} screenshot folder(s) older than 15 days",
                    "muted",
                ),
            )

    def _apply_window_icon(self) -> None:
        """Set the OS window / taskbar icon only (not drawn inside the UI)."""
        images: list[ImageTk.PhotoImage] = []
        for size in (16, 32, 48, 64, 128, 256):
            path = ASSETS_DIR / f"icon-{size}.png"
            source = path if path.exists() else ICON_PATH
            if not source.exists():
                continue
            try:
                image = Image.open(source).convert("RGBA")
                if image.size != (size, size):
                    image = image.resize((size, size), Image.Resampling.LANCZOS)
                images.append(ImageTk.PhotoImage(image))
            except Exception:
                continue

        if images:
            self._icon_images = images
            try:
                self.root.iconphoto(True, *self._icon_images)
            except tk.TclError:
                pass

        ico = ASSETS_DIR / "icon.ico"
        if ico.exists():
            try:
                # Fallback used by some window managers
                self.root.iconbitmap(default=str(ico))
            except tk.TclError:
                try:
                    self.root.iconbitmap(str(ico))
                except tk.TclError:
                    pass

        self.root.iconname("Tracker")

    def _build_ui(self) -> None:
        body = tk.Frame(self.root, bg=COLORS["bg"], padx=18, pady=4)
        body.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        indicator_row = tk.Frame(body, bg=COLORS["bg"])
        # Hidden for now — Idle / Tracking indicator
        # indicator_row.pack(fill=tk.X, pady=(0, 8))

        self.pulse_canvas = tk.Canvas(
            indicator_row,
            width=12,
            height=12,
            bg=COLORS["bg"],
            highlightthickness=0,
            bd=0,
        )
        # self.pulse_canvas.pack(side=tk.LEFT)
        self._pulse_dot = self.pulse_canvas.create_oval(2, 2, 10, 10, fill=COLORS["idle"], outline="")

        self.state_label = tk.Label(
            indicator_row,
            text="Idle",
            font=FONTS["label"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
        )
        # self.state_label.pack(side=tk.LEFT, padx=(6, 0))

        self.drive_var = tk.StringVar(value="Share: off — local only")
        self.drive_label = tk.Label(
            body,
            textvariable=self.drive_var,
            font=FONTS["label"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            anchor="w",
        )
        # Hidden for now with share UI
        # self.drive_label.pack(fill=tk.X, pady=(0, 4))

        self.public_link_var = tk.StringVar(value="Public link: —")
        self.public_link_label = tk.Label(
            body,
            textvariable=self.public_link_var,
            font=FONTS["label"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            anchor="w",
            wraplength=310,
            justify=tk.LEFT,
        )
        # self.public_link_label.pack(fill=tk.X, pady=(0, 4))

        link_actions = tk.Frame(body, bg=COLORS["bg"])
        # link_actions.pack(fill=tk.X, pady=(0, 8))

        self.copy_link_btn = tk.Button(
            link_actions,
            text="Copy link",
            command=self._copy_public_link,
            font=FONTS["button"],
            bg=COLORS["bg_soft"],
            fg=COLORS["ink"],
            activebackground=COLORS["line"],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor="hand2",
            state=tk.DISABLED,
        )
        # self.copy_link_btn.pack(side=tk.LEFT)

        self.open_link_btn = tk.Button(
            link_actions,
            text="Open link",
            command=self._open_public_link,
            font=FONTS["button"],
            bg=COLORS["bg_soft"],
            fg=COLORS["ink"],
            activebackground=COLORS["line"],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor="hand2",
            state=tk.DISABLED,
        )
        # self.open_link_btn.pack(side=tk.LEFT, padx=(6, 0))

        tk.Label(
            body,
            text="TIME TODAY",
            font=FONTS["label"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            anchor="w",
        ).pack(fill=tk.X)

        self.today_var = tk.StringVar(value="0h 00m 00s")
        tk.Label(
            body,
            textvariable=self.today_var,
            font=FONTS["value"],
            fg=COLORS["ink"],
            bg=COLORS["bg"],
            anchor="w",
        ).pack(fill=tk.X, pady=(1, 10))

        tk.Frame(body, height=1, bg=COLORS["line"]).pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            body,
            text="SESSION",
            font=FONTS["label"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            anchor="w",
        ).pack(fill=tk.X)

        self.session_var = tk.StringVar(value="0h 00m 00s")
        tk.Label(
            body,
            textvariable=self.session_var,
            font=FONTS["session"],
            fg=COLORS["accent"],
            bg=COLORS["bg"],
            anchor="w",
        ).pack(fill=tk.X, pady=(1, 12))

        actions = tk.Frame(body, bg=COLORS["bg"])
        actions.pack(fill=tk.X)

        self.start_btn = tk.Button(
            actions,
            text="Start",
            command=self.start_tracking,
            font=FONTS["button"],
            bg=COLORS["accent"],
            fg=COLORS["accent_text"],
            activebackground=COLORS["accent_dim"],
            activeforeground=COLORS["accent_text"],
            disabledforeground="#6b5a3a",
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            highlightthickness=0,
        )
        self.start_btn.pack(side=tk.LEFT)

        self.stop_btn = tk.Button(
            actions,
            text="Stop",
            command=self.stop_tracking,
            font=FONTS["button"],
            bg=COLORS["bg_soft"],
            fg=COLORS["ink"],
            activebackground=COLORS["line"],
            activeforeground=COLORS["ink"],
            disabledforeground=COLORS["idle"],
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            highlightthickness=0,
            state=tk.DISABLED,
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.pause_btn = tk.Button(
            actions,
            text="Pause",
            command=self.toggle_pause,
            font=FONTS["button"],
            bg=COLORS["bg_soft"],
            fg=COLORS["ink"],
            activebackground=COLORS["line"],
            activeforeground=COLORS["ink"],
            disabledforeground=COLORS["idle"],
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            highlightthickness=0,
            state=tk.DISABLED,
        )
        self.pause_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.lap_btn = tk.Button(
            actions,
            text="Lap",
            command=self.save_lap,
            font=FONTS["button"],
            bg=COLORS["bg_soft"],
            fg=COLORS["ink"],
            activebackground=COLORS["line"],
            activeforeground=COLORS["ink"],
            disabledforeground=COLORS["idle"],
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            highlightthickness=0,
            state=tk.DISABLED,
        )
        self.lap_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.shots_btn = tk.Button(
            actions,
            text="Shots on",
            command=self.toggle_screenshots,
            font=FONTS["button"],
            bg=COLORS["live"],
            fg=COLORS["accent_text"],
            activebackground=COLORS["ok"],
            activeforeground=COLORS["accent_text"],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=6,
            cursor="hand2",
            highlightthickness=0,
        )
        self.shots_btn.pack(side=tk.RIGHT)

        self.share_btn = tk.Button(
            actions,
            text="Share session",
            command=self._toggle_share_session,
            font=FONTS["button"],
            bg=COLORS["bg_soft"],
            fg=COLORS["ink"],
            activebackground=COLORS["line"],
            activeforeground=COLORS["ink"],
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            highlightthickness=0,
        )
        # Hidden for now — keep widget for later re-enable
        # self.share_btn.pack(side=tk.RIGHT)

        self._bind_button_hover(self.start_btn, COLORS["accent"], COLORS["accent_dim"])
        self._bind_button_hover(self.stop_btn, COLORS["bg_soft"], COLORS["line"])
        self._bind_button_hover(self.pause_btn, COLORS["bg_soft"], COLORS["line"])
        self._bind_button_hover(self.lap_btn, COLORS["bg_soft"], COLORS["line"])

        self.status_var = tk.StringVar(value="Ready to track")
        self.status_label = tk.Label(
            body,
            textvariable=self.status_var,
            font=FONTS["status"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            wraplength=310,
            justify=tk.LEFT,
            anchor="w",
        )
        self.status_label.pack(fill=tk.X, pady=(14, 0))

        tk.Frame(body, height=1, bg=COLORS["line"]).pack(fill=tk.X, pady=(12, 8))

        todos_header = tk.Frame(body, bg=COLORS["bg"])
        todos_header.pack(fill=tk.X)

        tk.Label(
            todos_header,
            text="TODOS",
            font=FONTS["label"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            anchor="w",
        ).pack(side=tk.LEFT)

        self.todos_count_var = tk.StringVar(value="0")
        tk.Label(
            todos_header,
            textvariable=self.todos_count_var,
            font=FONTS["lap_meta"],
            fg=COLORS["accent"],
            bg=COLORS["bg"],
            anchor="e",
        ).pack(side=tk.RIGHT)

        todo_add = tk.Frame(body, bg=COLORS["bg"])
        todo_add.pack(fill=tk.X, pady=(6, 0))

        self.todo_entry_var = tk.StringVar()
        self.todo_entry = tk.Entry(
            todo_add,
            textvariable=self.todo_entry_var,
            font=FONTS["lap_name"],
            bg=COLORS["bg_soft"],
            fg=COLORS["ink"],
            insertbackground=COLORS["ink"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
        )
        self.todo_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        self.todo_entry.bind("<Return>", lambda _e: self.add_todo())

        tk.Button(
            todo_add,
            text="Add",
            command=self.add_todo,
            font=FONTS["button"],
            bg=COLORS["accent"],
            fg=COLORS["accent_text"],
            activebackground=COLORS["accent_dim"],
            activeforeground=COLORS["accent_text"],
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            highlightthickness=0,
        ).pack(side=tk.RIGHT, padx=(8, 0))

        todos_shell = tk.Frame(
            body,
            bg=COLORS["bg_mid"],
            highlightthickness=1,
            highlightbackground=COLORS["line"],
        )
        todos_shell.pack(fill=tk.X, pady=(6, 0))

        self.todos_canvas = tk.Canvas(
            todos_shell,
            height=96,
            bg=COLORS["bg_mid"],
            highlightthickness=0,
            bd=0,
        )
        self.todos_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        todos_scroll = tk.Scrollbar(
            todos_shell,
            orient=tk.VERTICAL,
            command=self.todos_canvas.yview,
            troughcolor=COLORS["bg"],
            bg=COLORS["bg_soft"],
            activebackground=COLORS["line"],
            highlightthickness=0,
            bd=0,
            width=8,
        )
        todos_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.todos_canvas.configure(yscrollcommand=todos_scroll.set)

        self.todos_inner = tk.Frame(self.todos_canvas, bg=COLORS["bg_mid"])
        self._todos_window = self.todos_canvas.create_window((0, 0), window=self.todos_inner, anchor="nw")

        self.todos_inner.bind("<Configure>", self._on_todos_inner_configure)
        self.todos_canvas.bind("<Configure>", self._on_todos_canvas_configure)
        self._bind_todos_scroll()

        tk.Frame(body, height=1, bg=COLORS["line"]).pack(fill=tk.X, pady=(12, 8))

        laps_header = tk.Frame(body, bg=COLORS["bg"])
        laps_header.pack(fill=tk.X)

        tk.Label(
            laps_header,
            text="TODAY'S LAPS",
            font=FONTS["label"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            anchor="w",
        ).pack(side=tk.LEFT)

        self.laps_count_var = tk.StringVar(value="0")
        tk.Label(
            laps_header,
            textvariable=self.laps_count_var,
            font=FONTS["lap_meta"],
            fg=COLORS["accent"],
            bg=COLORS["bg"],
            anchor="e",
        ).pack(side=tk.RIGHT)

        laps_shell = tk.Frame(
            body,
            bg=COLORS["bg_mid"],
            highlightthickness=1,
            highlightbackground=COLORS["line"],
        )
        laps_shell.pack(fill=tk.X, pady=(6, 0))

        self.laps_canvas = tk.Canvas(
            laps_shell,
            height=96,
            bg=COLORS["bg_mid"],
            highlightthickness=0,
            bd=0,
        )
        self.laps_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        laps_scroll = tk.Scrollbar(
            laps_shell,
            orient=tk.VERTICAL,
            command=self.laps_canvas.yview,
            troughcolor=COLORS["bg"],
            bg=COLORS["bg_soft"],
            activebackground=COLORS["line"],
            highlightthickness=0,
            bd=0,
            width=8,
        )
        laps_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.laps_canvas.configure(yscrollcommand=laps_scroll.set)

        self.laps_inner = tk.Frame(self.laps_canvas, bg=COLORS["bg_mid"])
        self._laps_window = self.laps_canvas.create_window((0, 0), window=self.laps_inner, anchor="nw")

        self.laps_inner.bind("<Configure>", self._on_laps_inner_configure)
        self.laps_canvas.bind("<Configure>", self._on_laps_canvas_configure)
        self._bind_laps_scroll()

        tk.Frame(body, height=1, bg=COLORS["line"]).pack(fill=tk.X, pady=(10, 6))

        tk.Label(
            body,
            text="LAST SCREENSHOT",
            font=FONTS["label"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            anchor="w",
        ).pack(fill=tk.X)

        self.preview_name_var = tk.StringVar(value="No screenshots yet")
        tk.Label(
            body,
            textvariable=self.preview_name_var,
            font=FONTS["label"],
            fg=COLORS["ink"],
            bg=COLORS["bg"],
            anchor="w",
        ).pack(fill=tk.X, pady=(1, 4))

        self.preview_frame = tk.Frame(body, bg=COLORS["bg_soft"], height=170)
        self.preview_frame.pack(fill=tk.BOTH, expand=True)
        self.preview_frame.pack_propagate(False)

        self.preview_label = tk.Label(
            self.preview_frame,
            text="Capture will show here",
            font=FONTS["status"],
            fg=COLORS["muted"],
            bg=COLORS["bg_soft"],
        )
        self.preview_label.pack(expand=True, fill=tk.BOTH)

    def _bind_button_hover(self, button: tk.Button, normal: str, hover: str) -> None:
        def on_enter(_: object) -> None:
            if str(button["state"]) == "disabled":
                return
            button.configure(bg=hover)

        def on_leave(_: object) -> None:
            if str(button["state"]) == "disabled":
                return
            button.configure(bg=normal)

        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)

    def _set_status(self, message: str, tone: str = "muted") -> None:
        color = {
            "muted": COLORS["muted"],
            "ok": COLORS["ok"],
            "error": COLORS["error"],
            "live": COLORS["live"],
        }.get(tone, COLORS["muted"])
        self.status_var.set(message)
        self.status_label.configure(fg=color)

    def _refresh_share_status(self) -> None:
        public = self.uploader.public_share_link
        if public:
            short = public if len(public) < 42 else public[:39] + "…"
            self.public_link_var.set(f"Public link: {short}")
            self.public_link_label.configure(fg=COLORS["ok"])
            self.copy_link_btn.configure(state=tk.NORMAL)
            self.open_link_btn.configure(state=tk.NORMAL)
        else:
            self.public_link_var.set("Public link: —")
            self.public_link_label.configure(fg=COLORS["muted"])
            self.copy_link_btn.configure(state=tk.DISABLED)
            self.open_link_btn.configure(state=tk.DISABLED)

        if self._sharing and self.uploader.has_folder():
            self.drive_var.set("Share: on — uploading + anyone-with-link")
            self.drive_label.configure(fg=COLORS["ok"])
            self.share_btn.configure(text="Stop sharing", bg=COLORS["live"], fg=COLORS["accent_text"])
        elif self.uploader.has_folder():
            self.drive_var.set("Share: off — endpoint saved")
            self.drive_label.configure(fg=COLORS["muted"])
            self.share_btn.configure(text="Share session", bg=COLORS["bg_soft"], fg=COLORS["ink"])
        else:
            self.drive_var.set("Share: off — paste /exec upload link")
            self.drive_label.configure(fg=COLORS["muted"])
            self.share_btn.configure(text="Share session", bg=COLORS["bg_soft"], fg=COLORS["ink"])

    def _copy_public_link(self) -> None:
        link = self.uploader.public_share_link
        if not link:
            self._set_status("No public link yet", "error")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(link)
        self.root.update()
        self._set_status("Public Drive link copied — share it with anyone", "ok")

    def _open_public_link(self) -> None:
        link = self.uploader.public_share_link
        if not link:
            self._set_status("No public link yet", "error")
            return
        try:
            subprocess.Popen(
                ["xdg-open", link],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            self._set_status(f"Could not open link — {exc}", "error")

    def _toggle_share_session(self) -> None:
        if self._sharing:
            self._sharing = False
            self._refresh_share_status()
            self._set_status("Sharing stopped — screenshots stay local", "muted")
            return

        dialog = ShareLinkDialog(self.root, initial_link=self.uploader.folder_link)
        self.root.wait_window(dialog)
        if not dialog.result_link:
            self._set_status("Share cancelled", "muted")
            return

        try:
            self.uploader.save_share_link(dialog.result_link)
        except Exception as exc:
            self._set_status(f"Invalid link — {exc}", "error")
            return

        self._sharing = True
        self._refresh_share_status()
        self._set_status("Sharing on — fetching public anyone-with-link…", "live")
        self._prepare_public_link_async()

    def _prepare_public_link_async(self) -> None:
        def worker() -> None:
            try:
                link = self.uploader.fetch_public_share_link()
                self.root.after(0, lambda: self._on_public_link_ready(link))
                self._sync_local_to_drive_async()
            except Exception as exc:
                message = str(exc)
                self.root.after(
                    0,
                    lambda m=message: self._set_status(f"Share setup error — {m}", "error"),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_public_link_ready(self, link: str) -> None:
        self._refresh_share_status()
        self._set_status("Public link ready — Copy link to share with anyone", "ok")

    def _sync_local_to_drive_async(self) -> None:
        """Upload any local captures not yet synced when sharing is enabled."""

        def worker() -> None:
            if not self._upload_lock.acquire(blocking=False):
                self.root.after(0, lambda: self._set_status("Sync waiting — upload in progress", "muted"))
                return
            try:
                marker = DATA_DIR / "uploaded.json"
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                uploaded: set[str] = set()
                if marker.exists():
                    try:
                        uploaded = set(json.loads(marker.read_text(encoding="utf-8")))
                    except Exception:
                        uploaded = set()

                CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
                pending = sorted(
                    p for p in list_captures() if p.name not in uploaded
                )
                if not pending:
                    self.root.after(0, lambda: self._set_status("Sharing on — nothing new to sync", "ok"))
                    return

                self.root.after(
                    0,
                    lambda n=len(pending): self._set_status(f"Syncing {n} local screenshot(s)…", "live"),
                )
                last_share = ""
                for path in pending:
                    result = self.uploader.upload_png(path)
                    last_share = result.get("share_link") or last_share
                    uploaded.add(path.name)
                    marker.write_text(json.dumps(sorted(uploaded), indent=2), encoding="utf-8")
                self.root.after(0, self._refresh_share_status)
                self.root.after(
                    0,
                    lambda n=len(pending): self._set_status(
                        f"Synced {n} screenshot(s). Copy link to share.",
                        "ok",
                    ),
                )
            except Exception as exc:
                message = str(exc)
                self.root.after(0, lambda m=message: self._set_status(f"Sync error — {m}", "error"))
            finally:
                self._upload_lock.release()

        threading.Thread(target=worker, daemon=True).start()

    def _load_latest_preview(self) -> None:
        CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
        files = list_captures()
        if files:
            self._show_last_screenshot(files[-1])

    def _show_last_screenshot(self, path) -> None:
        try:
            image = Image.open(path).convert("RGB")
            max_w, max_h = 312, 160
            image.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self._preview_image = photo
            self.preview_label.configure(image=photo, text="", bg=COLORS["bg_soft"])
            self.preview_name_var.set(path.name)
        except Exception:
            self.preview_name_var.set("Could not load preview")
            self.preview_label.configure(image="", text="Preview unavailable", bg=COLORS["bg_soft"])

    def _refresh_labels(self) -> None:
        self.today_var.set(format_duration(self.tracker.today_total_seconds()))
        if self.tracker.is_running:
            self.session_var.set(format_duration(self.tracker.session_elapsed_seconds()))
        else:
            self.session_var.set("0h 00m 00s")

    def _schedule_tick(self) -> None:
        self._refresh_labels()
        self._tick_job = self.root.after(1000, self._schedule_tick)

    def _start_pulse(self) -> None:
        self.state_label.configure(text="Tracking", fg=COLORS["live"])
        self._animate_pulse()

    def _stop_pulse(self) -> None:
        if self._pulse_job is not None:
            self.root.after_cancel(self._pulse_job)
            self._pulse_job = None
        self.pulse_canvas.itemconfigure(self._pulse_dot, fill=COLORS["idle"])
        self.state_label.configure(text="Idle", fg=COLORS["muted"])

    def _animate_pulse(self) -> None:
        if not self._running or self.tracker.is_paused:
            return
        self._pulse_phase += 0.18
        t = (math.sin(self._pulse_phase) + 1) / 2
        r = int(0x5c + (0x3d - 0x5c) * t)
        g = int(0x6f + (0xba - 0x6f) * t)
        b = int(0x88 + (0x8b - 0x88) * t)
        color = f"#{r:02x}{g:02x}{b:02x}"
        self.pulse_canvas.itemconfigure(self._pulse_dot, fill=color)
        self._pulse_job = self.root.after(40, self._animate_pulse)

    def _set_pause_button(self, paused: bool) -> None:
        if paused:
            self.pause_btn.configure(text="Resume", state=tk.NORMAL, bg=COLORS["accent"], fg=COLORS["accent_text"])
        else:
            self.pause_btn.configure(text="Pause", state=tk.NORMAL, bg=COLORS["bg_soft"], fg=COLORS["ink"])

    def toggle_pause(self) -> None:
        if not self._running or not self.tracker.is_running:
            return

        if self.tracker.is_paused:
            self.tracker.resume()
            self._set_pause_button(False)
            self.lap_btn.configure(state=tk.NORMAL)
            self._start_pulse()
            self._set_status("Resumed", "live")
            if self._screenshots_enabled:
                self._schedule_next_capture()
        else:
            self.tracker.pause()
            if self._capture_job is not None:
                self.root.after_cancel(self._capture_job)
                self._capture_job = None
            self._set_pause_button(True)
            self.lap_btn.configure(state=tk.DISABLED)
            self._stop_pulse()
            self.state_label.configure(text="Paused", fg=COLORS["accent"])
            self._set_status("Paused — timer frozen", "muted")
        self._refresh_labels()

    def _set_shots_button(self) -> None:
        if self._screenshots_enabled:
            self.shots_btn.configure(
                text="Shots on",
                bg=COLORS["live"],
                fg=COLORS["accent_text"],
                activebackground=COLORS["ok"],
            )
        else:
            self.shots_btn.configure(
                text="Shots off",
                bg=COLORS["bg_soft"],
                fg=COLORS["ink"],
                activebackground=COLORS["line"],
            )

    def toggle_screenshots(self) -> None:
        self._screenshots_enabled = not self._screenshots_enabled
        self._set_shots_button()

        if not self._screenshots_enabled:
            if self._capture_job is not None:
                self.root.after_cancel(self._capture_job)
                self._capture_job = None
            self._set_status("Screenshots off — timer still runs", "muted")
            return

        self._set_status("Screenshots on", "ok")
        if self._running and not self.tracker.is_paused:
            self._run_capture_async()
            self._schedule_next_capture()

    def _bind_todos_scroll(self) -> None:
        def _enter(_event=None) -> None:
            self.todos_canvas.bind_all("<MouseWheel>", self._on_todos_mousewheel)
            self.todos_canvas.bind_all("<Button-4>", self._on_todos_linux_scroll)
            self.todos_canvas.bind_all("<Button-5>", self._on_todos_linux_scroll)

        def _leave(_event=None) -> None:
            self.todos_canvas.unbind_all("<MouseWheel>")
            self.todos_canvas.unbind_all("<Button-4>")
            self.todos_canvas.unbind_all("<Button-5>")

        self.todos_canvas.bind("<Enter>", _enter)
        self.todos_canvas.bind("<Leave>", _leave)

    def _on_todos_inner_configure(self, _event=None) -> None:
        self.todos_canvas.configure(scrollregion=self.todos_canvas.bbox("all"))

    def _on_todos_canvas_configure(self, event) -> None:
        self.todos_canvas.itemconfigure(self._todos_window, width=event.width)

    def _on_todos_mousewheel(self, event) -> None:
        delta = -1 if event.delta > 0 else 1
        self.todos_canvas.yview_scroll(delta, "units")

    def _on_todos_linux_scroll(self, event) -> None:
        self.todos_canvas.yview_scroll(-1 if event.num == 4 else 1, "units")

    def add_todo(self) -> None:
        text = self.todo_entry_var.get().strip()
        if not text:
            self._set_status("Enter a todo first", "error")
            return
        self.todos.add(text)
        self.todo_entry_var.set("")
        self._refresh_todos_list()
        self.todos_canvas.yview_moveto(0)
        self._set_status(f"Todo added: {text}", "ok")

    def _toggle_todo(self, todo_id: str) -> None:
        item = self.todos.toggle(todo_id)
        if item is None:
            self._set_status("Could not update todo", "error")
            return
        self._refresh_todos_list()
        label = "done" if item.get("done") else "reopened"
        self._set_status(f"Marked {label}: {item.get('text')}", "muted")

    def _delete_todo(self, todo_id: str, text: str) -> None:
        removed = self.todos.delete(todo_id)
        if removed is None:
            self._set_status("Could not delete todo", "error")
            return
        self._refresh_todos_list()
        self._set_status(f"Deleted todo: {text}", "muted")

    def _refresh_todos_list(self) -> None:
        for child in self.todos_inner.winfo_children():
            child.destroy()

        items = self.todos.all()
        self.todos_count_var.set(str(len(items)))

        if not items:
            empty = tk.Frame(self.todos_inner, bg=COLORS["bg_mid"])
            empty.pack(fill=tk.BOTH, expand=True, padx=14, pady=28)
            tk.Label(
                empty,
                text="No todos yet",
                font=FONTS["lap_name"],
                fg=COLORS["ink"],
                bg=COLORS["bg_mid"],
            ).pack(anchor="w")
            tk.Label(
                empty,
                text="Add a task above, then track it with Start / Lap.",
                font=FONTS["empty"],
                fg=COLORS["muted"],
                bg=COLORS["bg_mid"],
            ).pack(anchor="w", pady=(4, 0))
            self.todos_canvas.yview_moveto(0)
            return

        for i, item in enumerate(items, start=1):
            todo_id = str(item.get("id") or "")
            text = str(item.get("text") or "Untitled")
            done = bool(item.get("done"))
            row_bg = COLORS["bg_soft"] if i % 2 else COLORS["bg_mid"]
            name_fg = COLORS["muted"] if done else COLORS["ink"]
            status = "Done" if done else "Open"
            status_fg = COLORS["ok"] if done else COLORS["accent"]

            first_open = next((j for j, it in enumerate(items, start=1) if not it.get("done")), None)
            if first_open is not None:
                bar = COLORS["accent"] if first_open == i else COLORS["line"]
            else:
                bar = COLORS["accent"] if i == len(items) else COLORS["line"]

            row = tk.Frame(self.todos_inner, bg=row_bg)
            row.pack(fill=tk.X)

            accent = tk.Frame(row, width=3, bg=bar)
            accent.pack(side=tk.LEFT, fill=tk.Y)
            accent.pack_propagate(False)

            content = tk.Frame(row, bg=row_bg)
            content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 12), pady=8)

            top = tk.Frame(content, bg=row_bg)
            top.pack(fill=tk.X)

            tk.Label(
                top,
                text=f"{i:02d}",
                font=FONTS["lap_index"],
                fg=COLORS["accent"],
                bg=row_bg,
                width=3,
                anchor="w",
            ).pack(side=tk.LEFT)

            tk.Label(
                top,
                text=text,
                font=FONTS["lap_name"],
                fg=name_fg,
                bg=row_bg,
                anchor="w",
            ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 6))

            delete_btn = tk.Button(
                top,
                text="✕",
                command=lambda tid=todo_id, t=text: self._delete_todo(tid, t),
                font=("Lato", 10, "bold"),
                bg=row_bg,
                fg=COLORS["muted"],
                activebackground=COLORS["line"],
                activeforeground=COLORS["error"],
                disabledforeground=COLORS["idle"],
                relief=tk.FLAT,
                bd=0,
                padx=6,
                pady=0,
                cursor="hand2",
                highlightthickness=0,
            )
            delete_btn.pack(side=tk.RIGHT)
            delete_btn.bind(
                "<Enter>",
                lambda _e, b=delete_btn: b.configure(fg=COLORS["error"]),
            )
            delete_btn.bind(
                "<Leave>",
                lambda _e, b=delete_btn: b.configure(fg=COLORS["muted"]),
            )

            status_btn = tk.Button(
                top,
                text=status,
                command=lambda tid=todo_id: self._toggle_todo(tid),
                font=FONTS["lap_meta"],
                bg=row_bg,
                fg=status_fg,
                activebackground=COLORS["line"],
                activeforeground=COLORS["accent"],
                relief=tk.FLAT,
                bd=0,
                padx=4,
                pady=0,
                cursor="hand2",
                highlightthickness=0,
            )
            status_btn.pack(side=tk.RIGHT, padx=(0, 4))

        self.todos_canvas.update_idletasks()
        self.todos_canvas.configure(scrollregion=self.todos_canvas.bbox("all"))

    def _bind_laps_scroll(self) -> None:
        def _enter(_event=None) -> None:
            self.laps_canvas.bind_all("<MouseWheel>", self._on_laps_mousewheel)
            self.laps_canvas.bind_all("<Button-4>", self._on_laps_linux_scroll)
            self.laps_canvas.bind_all("<Button-5>", self._on_laps_linux_scroll)

        def _leave(_event=None) -> None:
            self.laps_canvas.unbind_all("<MouseWheel>")
            self.laps_canvas.unbind_all("<Button-4>")
            self.laps_canvas.unbind_all("<Button-5>")

        self.laps_canvas.bind("<Enter>", _enter)
        self.laps_canvas.bind("<Leave>", _leave)

    def _on_laps_inner_configure(self, _event=None) -> None:
        self.laps_canvas.configure(scrollregion=self.laps_canvas.bbox("all"))

    def _on_laps_canvas_configure(self, event) -> None:
        self.laps_canvas.itemconfigure(self._laps_window, width=event.width)

    def _on_laps_mousewheel(self, event) -> None:
        delta = -1 if event.delta > 0 else 1
        self.laps_canvas.yview_scroll(delta, "units")

    def _on_laps_linux_scroll(self, event) -> None:
        self.laps_canvas.yview_scroll(-1 if event.num == 4 else 1, "units")

    @staticmethod
    def _format_lap_duration(seconds: int) -> str:
        seconds = max(0, int(seconds))
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours}h {minutes:02d}m"
        return f"{minutes}m {secs:02d}s"

    def _refresh_laps_list(self) -> None:
        for child in self.laps_inner.winfo_children():
            child.destroy()

        laps = self.laps.laps_for()
        self.laps_count_var.set(str(len(laps)))

        if not laps:
            empty = tk.Frame(self.laps_inner, bg=COLORS["bg_mid"])
            empty.pack(fill=tk.BOTH, expand=True, padx=14, pady=28)
            tk.Label(
                empty,
                text="No laps yet",
                font=FONTS["lap_name"],
                fg=COLORS["ink"],
                bg=COLORS["bg_mid"],
            ).pack(anchor="w")
            tk.Label(
                empty,
                text="Start tracking, then hit Lap to name a task.",
                font=FONTS["empty"],
                fg=COLORS["muted"],
                bg=COLORS["bg_mid"],
            ).pack(anchor="w", pady=(4, 0))
            self.laps_canvas.yview_moveto(0)
            return

        for i, lap in enumerate(laps, start=1):
            name = str(lap.get("name") or "Untitled")
            seconds = int(lap.get("seconds") or 0)
            row_bg = COLORS["bg_soft"] if i % 2 else COLORS["bg_mid"]

            row = tk.Frame(self.laps_inner, bg=row_bg)
            row.pack(fill=tk.X)

            accent = tk.Frame(row, width=3, bg=COLORS["accent"] if i == len(laps) else COLORS["line"])
            accent.pack(side=tk.LEFT, fill=tk.Y)
            accent.pack_propagate(False)

            content = tk.Frame(row, bg=row_bg)
            content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 12), pady=8)

            top = tk.Frame(content, bg=row_bg)
            top.pack(fill=tk.X)

            tk.Label(
                top,
                text=f"{i:02d}",
                font=FONTS["lap_index"],
                fg=COLORS["accent"],
                bg=row_bg,
                width=3,
                anchor="w",
            ).pack(side=tk.LEFT)

            tk.Label(
                top,
                text=name,
                font=FONTS["lap_name"],
                fg=COLORS["ink"],
                bg=row_bg,
                anchor="w",
            ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 6))

            delete_btn = tk.Button(
                top,
                text="✕",
                command=lambda idx=i - 1, n=name: self._delete_lap(idx, n),
                font=("Lato", 10, "bold"),
                bg=row_bg,
                fg=COLORS["muted"],
                activebackground=COLORS["line"],
                activeforeground=COLORS["error"],
                disabledforeground=COLORS["idle"],
                relief=tk.FLAT,
                bd=0,
                padx=6,
                pady=0,
                cursor="hand2",
                highlightthickness=0,
            )
            delete_btn.pack(side=tk.RIGHT)
            delete_btn.bind(
                "<Enter>",
                lambda _e, b=delete_btn: b.configure(fg=COLORS["error"]),
            )
            delete_btn.bind(
                "<Leave>",
                lambda _e, b=delete_btn: b.configure(fg=COLORS["muted"]),
            )

            tk.Label(
                top,
                text=self._format_lap_duration(seconds),
                font=FONTS["lap_meta"],
                fg=COLORS["muted"],
                bg=row_bg,
                anchor="e",
            ).pack(side=tk.RIGHT, padx=(0, 4))

        self.laps_canvas.update_idletasks()
        self.laps_canvas.configure(scrollregion=self.laps_canvas.bbox("all"))

    def _delete_lap(self, index: int, name: str) -> None:
        removed = self.laps.delete_lap(index)
        if removed is None:
            self._set_status("Could not delete lap", "error")
            return
        self._refresh_laps_list()
        self._set_status(f"Deleted lap: {name}", "muted")

    def save_lap(self) -> None:
        if not self._running or not self.tracker.is_running:
            self._set_status("Start tracking before saving a lap", "error")
            return
        if self.tracker.is_paused:
            self._set_status("Resume before saving a lap", "error")
            return

        elapsed = format_duration(self.tracker.session_elapsed_seconds())
        dialog = LapNameDialog(self.root, elapsed_label=elapsed)
        self.root.wait_window(dialog)
        if not dialog.result_name:
            self._set_status("Lap cancelled", "muted")
            return

        seconds, name = self.tracker.lap(dialog.result_name)
        self.laps.add_lap(name, seconds)
        self._set_pause_button(False)
        self._refresh_labels()
        self._refresh_laps_list()
        self.laps_canvas.yview_moveto(1.0)
        self._set_status(f"Lap saved: {name} ({format_duration(seconds)}) — next task started", "ok")

    def start_tracking(self) -> None:
        if self._running:
            return
        self._running = True
        self.tracker.start()
        self.start_btn.configure(state=tk.DISABLED, bg=COLORS["bg_soft"])
        self.stop_btn.configure(state=tk.NORMAL, bg=COLORS["bg_soft"])
        self.lap_btn.configure(state=tk.NORMAL, bg=COLORS["bg_soft"])
        self._set_pause_button(False)
        self._start_pulse()
        self._refresh_labels()
        if self._screenshots_enabled:
            mode = "and Drive" if self._sharing else "locally"
            self._set_status(f"Capturing first screenshot ({mode})…", "live")
            self._run_capture_async()
            self._schedule_next_capture()
        else:
            self._set_status("Tracking — screenshots off", "live")

    def stop_tracking(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._capture_job is not None:
            self.root.after_cancel(self._capture_job)
            self._capture_job = None
        self.tracker.stop()
        self.start_btn.configure(state=tk.NORMAL, bg=COLORS["accent"])
        self.stop_btn.configure(state=tk.DISABLED, bg=COLORS["bg_soft"])
        self.pause_btn.configure(text="Pause", state=tk.DISABLED, bg=COLORS["bg_soft"], fg=COLORS["ink"])
        self.lap_btn.configure(state=tk.DISABLED, bg=COLORS["bg_soft"])
        self._stop_pulse()
        self._set_status("Stopped", "muted")
        self._refresh_labels()
        self._refresh_laps_list()

    def _schedule_next_capture(self) -> None:
        if not self._running or self.tracker.is_paused or not self._screenshots_enabled:
            return
        interval_ms = max(1, SCREENSHOT_INTERVAL_SECONDS) * 1000
        self._capture_job = self.root.after(interval_ms, self._on_capture_due)

    def _on_capture_due(self) -> None:
        self._capture_job = None
        if not self._running or self.tracker.is_paused or not self._screenshots_enabled:
            return
        self._run_capture_async()
        self._schedule_next_capture()

    def _run_capture_async(self) -> None:
        if not self._screenshots_enabled:
            return
        def worker() -> None:
            if not self._upload_lock.acquire(blocking=False):
                self.root.after(0, lambda: self._set_status("Previous capture still in progress", "muted"))
                return
            try:
                path = take_screenshot()
                self.root.after(0, lambda p=path: self._show_last_screenshot(p))
                if not self._sharing:
                    self.root.after(
                        0,
                        lambda: self._set_status(f"Saved locally: {path.name}", "ok"),
                    )
                    return

                self.root.after(
                    0,
                    lambda: self._set_status(f"Saved {path.name} — uploading to Drive…", "live"),
                )
                result = self.uploader.upload_png(path)
                file_id = result.get("id", "ok")
                marker = DATA_DIR / "uploaded.json"
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                uploaded: set[str] = set()
                if marker.exists():
                    try:
                        uploaded = set(json.loads(marker.read_text(encoding="utf-8")))
                    except Exception:
                        uploaded = set()
                uploaded.add(path.name)
                marker.write_text(json.dumps(sorted(uploaded), indent=2), encoding="utf-8")
                self.root.after(0, self._refresh_share_status)
                self.root.after(
                    0,
                    lambda: self._set_status(
                        f"Uploaded {path.name} — public link ready to copy",
                        "ok",
                    ),
                )
            except Exception as exc:
                message = str(exc)
                self.root.after(0, lambda m=message: self._set_status(f"Error — {m}", "error"))
            finally:
                self._upload_lock.release()

        threading.Thread(target=worker, daemon=True).start()

    def _on_close(self) -> None:
        if self._running:
            self.stop_tracking()
        if self._tick_job is not None:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None
        if self._pulse_job is not None:
            self.root.after_cancel(self._pulse_job)
            self._pulse_job = None
        self.root.destroy()


def main() -> None:
    # className must match StartupWMClass in the .desktop file for dock icon
    root = tk.Tk(className="Tracker")
    TrackerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
