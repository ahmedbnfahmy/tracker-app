from __future__ import annotations

import json
import math
import subprocess
import threading
import tkinter as tk
from typing import Optional

from PIL import Image, ImageTk

from config import ASSETS_DIR, CAPTURES_DIR, DATA_DIR, ICON_PATH, SCREENSHOT_INTERVAL_SECONDS
from screenshot import cleanup_old_day_folders, list_captures, take_screenshot
from share_dialog import ShareLinkDialog
from time_tracker import TimeTracker, format_duration
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
}


class TrackerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tracker")
        self.root.geometry("360x680")
        self.root.minsize(340, 640)
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg"])
        self._icon_images: list[ImageTk.PhotoImage] = []
        self._preview_image: Optional[ImageTk.PhotoImage] = None
        self._apply_window_icon()

        self.tracker = TimeTracker()
        self.uploader = DriveUploader()

        self._running = False
        self._capture_job: Optional[str] = None
        self._tick_job: Optional[str] = None
        self._pulse_job: Optional[str] = None
        self._pulse_phase = 0.0
        self._upload_lock = threading.Lock()
        self._sharing = False

        self._build_ui()
        self._refresh_labels()
        self._refresh_share_status()
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
        header = tk.Canvas(self.root, height=88, highlightthickness=0, bd=0)
        header.pack(fill=tk.X)
        self._draw_header(header)

        body = tk.Frame(self.root, bg=COLORS["bg"], padx=18, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        indicator_row = tk.Frame(body, bg=COLORS["bg"])
        indicator_row.pack(fill=tk.X, pady=(0, 8))

        self.pulse_canvas = tk.Canvas(
            indicator_row,
            width=12,
            height=12,
            bg=COLORS["bg"],
            highlightthickness=0,
            bd=0,
        )
        self.pulse_canvas.pack(side=tk.LEFT)
        self._pulse_dot = self.pulse_canvas.create_oval(2, 2, 10, 10, fill=COLORS["idle"], outline="")

        self.state_label = tk.Label(
            indicator_row,
            text="Idle",
            font=FONTS["label"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
        )
        self.state_label.pack(side=tk.LEFT, padx=(6, 0))

        self.drive_var = tk.StringVar(value="Share: off — local only")
        self.drive_label = tk.Label(
            body,
            textvariable=self.drive_var,
            font=FONTS["label"],
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            anchor="w",
        )
        self.drive_label.pack(fill=tk.X, pady=(0, 4))

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
        self.public_link_label.pack(fill=tk.X, pady=(0, 4))

        link_actions = tk.Frame(body, bg=COLORS["bg"])
        link_actions.pack(fill=tk.X, pady=(0, 8))

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
        self.copy_link_btn.pack(side=tk.LEFT)

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
        self.open_link_btn.pack(side=tk.LEFT, padx=(6, 0))

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
            padx=14,
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
            padx=14,
            pady=6,
            cursor="hand2",
            highlightthickness=0,
            state=tk.DISABLED,
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

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
        ).pack(fill=tk.X, pady=(1, 6))

        self.preview_frame = tk.Frame(body, bg=COLORS["bg_soft"], height=190)
        self.preview_frame.pack(fill=tk.X)
        self.preview_frame.pack_propagate(False)

        self.preview_label = tk.Label(
            self.preview_frame,
            text="Capture will show here",
            font=FONTS["status"],
            fg=COLORS["muted"],
            bg=COLORS["bg_soft"],
        )
        self.preview_label.pack(expand=True, fill=tk.BOTH)

    def _draw_header(self, canvas: tk.Canvas) -> None:
        width = 360
        height = 88
        bands = ("#15202e", "#1a2332", "#1f2a3d", "#243044")
        band_h = height // len(bands)
        for i, color in enumerate(bands):
            canvas.create_rectangle(0, i * band_h, width, (i + 1) * band_h + 2, fill=color, outline="")
        canvas.create_text(
            18,
            32,
            text="Tracker",
            anchor="w",
            fill=COLORS["ink"],
            font=FONTS["brand"],
        )
        canvas.create_text(
            18,
            58,
            text="Time · screen · Drive",
            anchor="w",
            fill=COLORS["muted"],
            font=FONTS["label"],
        )
        canvas.create_rectangle(18, 72, 88, 74, fill=COLORS["accent"], outline="")

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
            max_w, max_h = 312, 180
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
        if not self._running:
            return
        self._pulse_phase += 0.18
        t = (math.sin(self._pulse_phase) + 1) / 2
        r = int(0x5c + (0x3d - 0x5c) * t)
        g = int(0x6f + (0xba - 0x6f) * t)
        b = int(0x88 + (0x8b - 0x88) * t)
        color = f"#{r:02x}{g:02x}{b:02x}"
        self.pulse_canvas.itemconfigure(self._pulse_dot, fill=color)
        self._pulse_job = self.root.after(40, self._animate_pulse)

    def start_tracking(self) -> None:
        if self._running:
            return
        self._running = True
        self.tracker.start()
        self.start_btn.configure(state=tk.DISABLED, bg=COLORS["bg_soft"])
        self.stop_btn.configure(state=tk.NORMAL, bg=COLORS["bg_soft"])
        mode = "and Drive" if self._sharing else "locally"
        self._set_status(f"Capturing first screenshot ({mode})…", "live")
        self._start_pulse()
        self._refresh_labels()
        self._run_capture_async()
        self._schedule_next_capture()

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
        self._stop_pulse()
        self._set_status("Stopped", "muted")
        self._refresh_labels()

    def _schedule_next_capture(self) -> None:
        if not self._running:
            return
        interval_ms = max(1, SCREENSHOT_INTERVAL_SECONDS) * 1000
        self._capture_job = self.root.after(interval_ms, self._on_capture_due)

    def _on_capture_due(self) -> None:
        self._capture_job = None
        if not self._running:
            return
        self._run_capture_async()
        self._schedule_next_capture()

    def _run_capture_async(self) -> None:
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
