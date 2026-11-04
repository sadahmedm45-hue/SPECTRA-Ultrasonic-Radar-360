"""SPECTRA 360° Ultrasonic Radar — Arduino Uno + 28BYJ-48 + HC-SR04.

Run on Windows with: python radar_gui.py
Serial protocol is documented in README_AR.txt.
"""
from __future__ import annotations

import math
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

try:
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    Image = ImageTk = ImageDraw = None

try:
    import winsound
except ImportError:
    winsound = None

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(APP_DIR, "assets")
AVATAR_PATH = os.path.join(ASSET_DIR, "profile_avatar.png")
PORTRAIT_PATH = os.path.join(ASSET_DIR, "nexus_profile_dark.png")
BAUD_RATE = 115200

BG = "#050d16"
PANEL = "#0a1b2a"
PANEL_ALT = "#0e2638"
PANEL_DARK = "#03110c"
BORDER = "#1d4052"
CYAN = "#18c8f6"
GREEN = "#41f5a4"
GREEN_DIM = "#176a47"
RED = "#ff4058"
RED_DARK = "#39131d"
TEXT = "#e6f4fb"
MUTED = "#83a5b8"
AMBER = "#ffca71"
FONT = "Segoe UI"
MONO = "Consolas"


class RadarApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SPECTRA // 360° Ultrasonic Radar Control")
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        initial_w = min(1450, max(1080, screen_w - 24))
        initial_h = min(920, max(750, screen_h - 80))
        self.root.geometry(f"{initial_w}x{initial_h}")
        self.root.minsize(1120, 760)
        self.root.configure(bg=BG)
        try:
            if os.name == "nt":
                self.root.state("zoomed")
        except tk.TclError:
            pass

        self.ser = None
        self.connected = False
        self.reader_stop = threading.Event()
        self.reader_thread = None
        self.serial_lock = threading.Lock()
        self.inbox: queue.Queue[tuple[str, str]] = queue.Queue()
        self.closing = threading.Event()
        self.alarm_event = threading.Event()
        threading.Thread(target=self._alarm_worker, daemon=True).start()
        self._settings_after = None
        self._sync_after = None

        self.angle = 0.0
        self.direction = 1
        self.distance = -1.0
        self.detected = False
        self.user_paused = False
        self.hold_left = 0.0
        self.speed_level = 5
        self.detection_limit = 250
        self.hold_seconds = 3
        self.demo_angle = 0.0
        self.demo_direction = 1
        self.trail: list[tuple[float, float]] = []
        self.targets: list[tuple[float, float, float]] = []
        self.last_packet = "Waiting for Arduino telemetry..."
        self.last_packet_time = 0.0
        self.last_ui_alert = False

        self.port_var = tk.StringVar(value="")
        self.link_var = tk.StringVar(value="DEMO MODE")
        self.angle_var = tk.StringVar(value="000.0°")
        self.distance_var = tk.StringVar(value="---.- cm")
        self.speed_readout_var = tk.StringVar(value="5 / 10")
        self.limit_readout_var = tk.StringVar(value="250 cm")
        self.hold_readout_var = tk.StringVar(value="3 seconds")
        self.hold_left_var = tk.StringVar(value="—")
        self.state_var = tk.StringVar(value="DEMO SWEEP")
        self.pir_like_var = tk.StringVar(value="NO OBJECT IN RANGE")
        self.rx_var = tk.StringVar(value="RX: waiting for serial data")
        self.range_var = tk.IntVar(value=self.detection_limit)
        self.speed_var = tk.IntVar(value=self.speed_level)
        self.hold_var = tk.IntVar(value=self.hold_seconds)
        self.pause_text_var = tk.StringVar(value="PAUSE SCAN")

        self._load_images()
        self._build_style()
        self._build_ui()
        self.refresh_ports()
        self.log("SYSTEM READY  //  Select the Arduino COM port to connect.")
        self.log("HARDWARE  //  28BYJ-48 + ULN2003 + HC-SR04 + buzzer.")
        self.log("DEMO MODE  //  Sweep animation runs until a real serial connection is active.")

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(40, self.process_inbox)
        self.root.after(45, self.animate)

    # ---------- Images / theme ----------
    def _load_images(self):
        self.avatar_tk = None
        self.portrait_tk = None
        if Image is None:
            return
        try:
            if os.path.isfile(AVATAR_PATH):
                image = Image.open(AVATAR_PATH).convert("RGBA").resize((86, 86), Image.Resampling.LANCZOS)
                mask = Image.new("L", image.size, 0)
                ImageDraw.Draw(mask).ellipse((1, 1, 84, 84), fill=255)
                image.putalpha(mask)
                self.avatar_tk = ImageTk.PhotoImage(image)
            if os.path.isfile(PORTRAIT_PATH):
                image = Image.open(PORTRAIT_PATH).convert("RGBA")
                image.thumbnail((440, 300), Image.Resampling.LANCZOS)
                self.portrait_tk = ImageTk.PhotoImage(image)
        except Exception:
            self.avatar_tk = self.portrait_tk = None

    def _build_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Dark.TCombobox", fieldbackground=PANEL_ALT, background=PANEL_ALT,
                        foreground=TEXT, arrowcolor=CYAN, bordercolor=BORDER, padding=6)
        style.map("Dark.TCombobox", fieldbackground=[("readonly", PANEL_ALT)],
                  foreground=[("readonly", TEXT)], selectbackground=[("readonly", PANEL_ALT)],
                  selectforeground=[("readonly", TEXT)])
        style.configure("Dark.TSpinbox", fieldbackground=PANEL_ALT, background=PANEL_ALT,
                        foreground=TEXT, arrowcolor=CYAN, bordercolor=BORDER)

    def _build_ui(self):
        # Compact title bar: the operator portrait now lives in the right-hand
        # information column, leaving roughly two thirds of the window for radar.
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=18, pady=(12, 8))

        title_box = tk.Frame(header, bg=BG)
        title_box.pack(side="left", fill="y")
        tk.Label(title_box, text="SPECTRA  /  360°", bg=BG, fg=GREEN,
                 font=(MONO, 24, "bold")).pack(anchor="w")
        tk.Label(title_box, text="ULTRASONIC RADAR  •  LIVE SWEEP  •  REAL-TIME TRACKING",
                 bg=BG, fg=MUTED, font=(MONO, 9)).pack(anchor="w", pady=(3, 0))

        right_head = tk.Frame(header, bg=BG)
        right_head.pack(side="right", anchor="center")
        self.online_dot = tk.Label(right_head, text="●", bg=BG, fg=AMBER,
                                   font=(MONO, 16, "bold"))
        self.online_dot.pack(side="left", padx=(0, 7))
        self.online_label = tk.Label(right_head, textvariable=self.link_var, bg=BG, fg=AMBER,
                                     font=(MONO, 11, "bold"))
        self.online_label.pack(side="left")
        tk.Label(right_head, text="\nHC-SR04  •  28BYJ-48  •  115200 BAUD",
                 bg=BG, fg=MUTED, font=(MONO, 8), justify="right").pack(anchor="e")

        # Serial toolbar across the complete application width.
        link = tk.Frame(self.root, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        link.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(link, text="SERIAL LINK", bg=PANEL, fg=MUTED,
                 font=(MONO, 9, "bold")).pack(side="left", padx=(12, 8), pady=9)
        self.port_combo = ttk.Combobox(link, textvariable=self.port_var, style="Dark.TCombobox",
                                       state="readonly", width=30)
        self.port_combo.pack(side="left", padx=(0, 7), pady=6)
        self.button(link, "REFRESH PORTS", self.refresh_ports, compact=True).pack(side="left", padx=3)
        self.button(link, "CONNECT", self.connect, primary=True, compact=True).pack(side="left", padx=3)
        self.button(link, "DISCONNECT", self.disconnect, compact=True).pack(side="left", padx=3)
        tk.Label(link, text="USB  /  115200 BAUD", bg=PANEL, fg=MUTED,
                 font=(MONO, 8, "bold")).pack(side="right", padx=13)

        # Main composition: radar receives about 2/3 of the available width.
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        body.grid_columnconfigure(0, weight=2, minsize=650)
        body.grid_columnconfigure(1, weight=1, minsize=340)
        body.grid_rowconfigure(0, weight=1)

        radar_card = self.card(body, "360° RADAR DISPLAY  /  AZIMUTH + ULTRASONIC RANGE")
        radar_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.canvas = tk.Canvas(radar_card, bg=PANEL_DARK, highlightthickness=1,
                                highlightbackground="#1b6544", bd=0)
        self.canvas.pack(fill="both", expand=True, pady=(9, 0))
        legend = tk.Frame(radar_card, bg=PANEL)
        legend.pack(fill="x", pady=(7, 0))
        self.legend_dot(legend, GREEN, "LIVE SWEEP")
        self.legend_dot(legend, "#8fffc2", "TARGET RETURN")
        self.legend_dot(legend, RED, "OBJECT LOCK")
        self.legend_dot(legend, CYAN, "SERIAL / CONFIG")

        side = tk.Frame(body, bg=BG)
        side.grid(row=0, column=1, sticky="nsew")

        # Clickable operator identity card, positioned in the right third.
        profile = tk.Frame(side, bg=PANEL, padx=9, pady=8,
                           highlightthickness=1, highlightbackground=BORDER)
        profile.pack(fill="x", pady=(0, 8))
        profile_left = tk.Frame(profile, bg=PANEL)
        profile_left.pack(side="left", padx=(0, 10))
        if self.avatar_tk:
            portrait = tk.Label(profile_left, image=self.avatar_tk, bg=PANEL_ALT,
                                cursor="hand2", bd=0)
        else:
            portrait = tk.Label(profile_left, text="SA", bg=PANEL_ALT, fg=CYAN,
                                font=(MONO, 18, "bold"), width=4, height=2, cursor="hand2")
        portrait.pack()
        portrait.bind("<Button-1>", self.show_project_info)
        profile_left.bind("<Button-1>", self.show_project_info)
        profile_text = tk.Frame(profile, bg=PANEL)
        profile_text.pack(side="left", fill="both", expand=True)
        tk.Label(profile_text, text="RADAR OPERATOR", bg=PANEL, fg=CYAN,
                 font=(MONO, 8, "bold")).pack(anchor="w")
        tk.Label(profile_text, text="SAAD AHMED ALBOHAN", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(3, 1))
        tk.Label(profile_text, text="STUDENT ENGINEER  •  PROJECT OWNER",
                 bg=PANEL, fg=MUTED, font=(MONO, 7)).pack(anchor="w")
        info_link = tk.Label(profile_text, text="VIEW PROJECT INFORMATION  ↗", bg=PANEL,
                             fg=GREEN, font=(MONO, 7, "bold"), cursor="hand2")
        info_link.pack(anchor="w", pady=(5, 0))
        info_link.bind("<Button-1>", self.show_project_info)
        profile.bind("<Button-1>", self.show_project_info)

        # Live values.
        telemetry = self.card(side, "SYSTEM TELEMETRY  /  LIVE READINGS")
        telemetry.pack(fill="x", pady=(0, 8))
        metric_row = tk.Frame(telemetry, bg=PANEL)
        metric_row.pack(fill="x", pady=(8, 4))
        self._metric(metric_row, "SCAN ANGLE", self.angle_var, "left")
        self._metric(metric_row, "DISTANCE", self.distance_var, "left")
        second_row = tk.Frame(telemetry, bg=PANEL)
        second_row.pack(fill="x", pady=(3, 0))
        self.state_badge = tk.Label(second_row, textvariable=self.state_var, bg="#102d21", fg=GREEN,
                                    font=(MONO, 8, "bold"), padx=8, pady=6, anchor="w")
        self.state_badge.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.hold_left_badge = tk.Label(second_row, textvariable=self.hold_left_var, bg=PANEL_ALT,
                                        fg=AMBER, font=(MONO, 8, "bold"), padx=7, pady=6)
        self.hold_left_badge.pack(side="left")

        # Detection panel changes from green to red on a real target.
        alert = self.card(side, "OBJECT DETECTION  /  STOP + ALARM")
        alert.pack(fill="x", pady=(0, 8))
        self.alert_panel = tk.Frame(alert, bg="#102d21", padx=10, pady=8,
                                    highlightthickness=1, highlightbackground=GREEN_DIM)
        self.alert_panel.pack(fill="x", pady=(8, 0))
        self.alert_title = tk.Label(self.alert_panel, text="● RADAR CLEAR", bg="#102d21", fg=GREEN,
                                    font=(MONO, 11, "bold"))
        self.alert_title.pack(anchor="w")
        self.alert_detail = tk.Label(self.alert_panel,
            text="No object is inside the selected detection distance.", bg="#102d21", fg=TEXT,
            font=(FONT, 9), justify="left", wraplength=310)
        self.alert_detail.pack(anchor="w", pady=(4, 0))

        # Live-adjustable motor speed, detection range and minimum stop time.
        settings = self.card(side, "RADAR CONFIGURATION  /  LIVE CONTROL")
        settings.pack(fill="x", pady=(0, 8))
        self._scale_setting(settings, "STEPPER SPEED", self.speed_var, 1, 10,
                            self.speed_readout_var, "speed")
        self._scale_setting(settings, "DETECTION DISTANCE", self.range_var, 2, 400,
                            self.limit_readout_var, "range")
        self._scale_setting(settings, "MINIMUM STOP TIME", self.hold_var, 2, 30,
                            self.hold_readout_var, "hold")
        settings_btns = tk.Frame(settings, bg=PANEL)
        settings_btns.pack(fill="x", pady=(5, 0))
        self.button(settings_btns, "APPLY", self.apply_settings, primary=True,
                    compact=True).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.pause_button = self.button(settings_btns, "PAUSE SCAN", self.toggle_pause, compact=True)
        self.pause_button.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Serial output and event history remain visible in the right column.
        log_card = self.card(side, "SERIAL OUTPUT  /  EVENT LOG")
        log_card.pack(fill="both", expand=True)
        self.log_box = tk.Text(log_card, height=6, width=34, bg="#020b08", fg="#a6d8bd",
                               insertbackground=GREEN, relief="flat", wrap="word",
                               font=(MONO, 8), padx=8, pady=6, state="disabled")
        self.log_box.pack(fill="both", expand=True, pady=(8, 6))
        rx_frame = tk.Frame(log_card, bg=PANEL_ALT, padx=7, pady=5)
        rx_frame.pack(fill="x")
        tk.Label(rx_frame, text="LATEST RX", bg=PANEL_ALT, fg=CYAN,
                 font=(MONO, 7, "bold")).pack(side="left", padx=(0, 6))
        tk.Label(rx_frame, textvariable=self.rx_var, bg=PANEL_ALT, fg=TEXT,
                 font=(MONO, 7), justify="left", anchor="w", wraplength=260).pack(
                     side="left", fill="x", expand=True)

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=20, pady=(0, 7))
        tk.Label(footer, text="SPECTRA RADAR  //  HC-SR04 + 28BYJ-48 + ULN2003",
                 bg=BG, fg="#567267", font=(MONO, 8)).pack(side="left")
        tk.Label(footer, text="360° LIVE DISPLAY  •  CLICK OPERATOR PHOTO FOR PROJECT INFO",
                 bg=BG, fg="#567267", font=(MONO, 8)).pack(side="right")

    def card(self, parent, title):
        frame = tk.Frame(parent, bg=PANEL, padx=12, pady=10,
                         highlightthickness=1, highlightbackground=BORDER)
        tk.Label(frame, text=title, bg=PANEL, fg=CYAN,
                 font=(MONO, 8, "bold")).pack(anchor="w")
        return frame

    def button(self, parent, text, command, primary=False, compact=False):
        bg = "#123d30" if primary else "#122a3a"
        fg = GREEN if primary else TEXT
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground="#205846", activeforeground="#ffffff",
                         relief="flat", bd=0, padx=9 if compact else 12,
                         pady=6 if compact else 8, cursor="hand2",
                         font=(MONO, 8 if compact else 9, "bold"),
                         highlightthickness=1, highlightbackground="#2b5963")

    def legend_dot(self, parent, color, text):
        item = tk.Frame(parent, bg=PANEL)
        item.pack(side="left", padx=(0, 11))
        dot = tk.Canvas(item, width=11, height=11, bg=PANEL, highlightthickness=0)
        dot.pack(side="left", padx=(0, 5))
        dot.create_oval(1, 1, 10, 10, fill=color, outline="")
        tk.Label(item, text=text, bg=PANEL, fg=MUTED, font=(MONO, 7)).pack(side="left")

    def _metric(self, parent, title, variable, side="left"):
        box = tk.Frame(parent, bg=PANEL_ALT, padx=10, pady=7,
                       highlightthickness=1, highlightbackground=BORDER)
        box.pack(side=side, fill="both", expand=True, padx=(0, 5) if side == "left" else 0)
        tk.Label(box, text=title, bg=PANEL_ALT, fg=MUTED,
                 font=(MONO, 8, "bold")).pack(anchor="w")
        tk.Label(box, textvariable=variable, bg=PANEL_ALT, fg=GREEN,
                 font=(MONO, 19, "bold")).pack(anchor="w", pady=(3, 0))

    def _scale_setting(self, parent, title, variable, low, high, readout, kind):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=(7, 0))
        top = tk.Frame(row, bg=PANEL)
        top.pack(fill="x")
        tk.Label(top, text=title, bg=PANEL, fg=MUTED,
                 font=(MONO, 8, "bold")).pack(side="left")
        tk.Label(top, textvariable=readout, bg=PANEL, fg=GREEN,
                 font=(MONO, 8, "bold")).pack(side="right")
        command = {
            "speed": self._speed_changed,
            "range": self._range_changed,
            "hold": self._hold_changed,
        }[kind]
        scale = tk.Scale(row, from_=low, to=high, orient="horizontal", variable=variable,
                         command=command, showvalue=False, resolution=1, length=250,
                         bg=PANEL, fg=TEXT, troughcolor="#173548", activebackground=CYAN,
                         highlightthickness=0, bd=0, sliderrelief="flat")
        scale.pack(fill="x", pady=(0, 0))

    # ---------- Project information ----------
    def show_project_info(self, _event=None):
        win = tk.Toplevel(self.root)
        win.title("Project Information | SPECTRA RADAR")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self.root)
        outer = tk.Frame(win, bg=PANEL, padx=18, pady=17,
                         highlightthickness=1, highlightbackground=CYAN)
        outer.pack(fill="both", expand=True, padx=12, pady=12)
        if self.portrait_tk:
            tk.Label(outer, image=self.portrait_tk, bg=PANEL).pack(pady=(0, 10))
        else:
            tk.Label(outer, text="SPECTRA / 360°", bg=PANEL, fg=CYAN,
                     font=(MONO, 22, "bold")).pack(pady=15)
        tk.Label(outer, text="SPECTRA  /  360° ULTRASONIC RADAR", bg=PANEL, fg=CYAN,
                 font=(MONO, 13, "bold"), wraplength=410).pack(pady=(3, 9))
        tk.Label(outer, text="SAAD AHMED ALBOHAN", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack()
        tk.Label(outer, text="STUDENT PROJECT  •  ARDUINO UNO + PYTHON", bg=PANEL, fg=GREEN,
                 font=(MONO, 9, "bold")).pack(pady=(7, 10))
        tk.Label(outer,
                 text="Large circular 360° radar display, ultrasonic distance measurement,\n"
                      "stepper sweep, live serial telemetry and adjustable detection settings.",
                 bg=PANEL, fg=MUTED, font=(FONT, 10), justify="center", wraplength=410).pack(pady=(0, 12))
        self.button(outer, "CLOSE", win.destroy, primary=True).pack(fill="x")
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    # ---------- Serial port / connection ----------
    def refresh_ports(self):
        if list_ports is None:
            self.port_combo["values"] = []
            self.log("DEPENDENCY MISSING  //  Install pyserial to list serial ports.")
            return
        try:
            ports = list(list_ports.comports())
        except Exception as exc:
            self.log(f"PORT SCAN ERROR  //  {exc}")
            return
        values = [f"{port.device} — {port.description}" for port in ports]
        self.port_combo["values"] = values
        current = self.port_var.get().split(" — ")[0].strip()
        match = next((value for value in values if value.startswith(current + " —")), None)
        self.port_var.set(match or (values[0] if values else ""))
        if values:
            self.log(f"PORT SCAN  //  Found {len(values)} serial port(s).")
        else:
            self.log("PORT SCAN  //  No serial ports found; check USB cable and Arduino driver.")

    def connect(self):
        if serial is None:
            messagebox.showerror("Missing library", "Install pyserial first:\n\npython -m pip install pyserial")
            return
        if self.connected and self.ser and self.ser.is_open:
            return
        port = self.port_var.get().split(" — ")[0].strip()
        if not port:
            messagebox.showwarning("Serial port", "Choose the Arduino COM port first.")
            return
        self.disconnect(write_log=False)
        try:
            ser = serial.Serial(port, BAUD_RATE, timeout=0.2, write_timeout=0.5)
            self.ser = ser
            self.connected = True
            self.reader_stop = threading.Event()
            self.reader_thread = threading.Thread(target=self.reader_loop,
                                                  args=(ser, self.reader_stop), daemon=True)
            self.reader_thread.start()
            self.link_var.set(f"CONNECTING  {port}")
            self.online_dot.configure(fg=AMBER)
            self.online_label.configure(fg=AMBER)
            self.log(f"SERIAL LINK  //  Opening {port} at {BAUD_RATE} baud.")
            if self._sync_after:
                try:
                    self.root.after_cancel(self._sync_after)
                except tk.TclError:
                    pass
            self._sync_after = self.root.after(1800, self.apply_settings)
        except Exception as exc:
            self.ser = None
            self.connected = False
            self.link_var.set("CONNECTION FAILED")
            self.online_dot.configure(fg=RED)
            self.online_label.configure(fg=RED)
            messagebox.showerror("Connection failed",
                f"Could not open {port}.\n\n{exc}\n\nClose Arduino Serial Monitor and retry.")

    def disconnect(self, write_log=True):
        self.reader_stop.set()
        ser = self.ser
        self.ser = None
        self.connected = False
        if self._sync_after:
            try:
                self.root.after_cancel(self._sync_after)
            except tk.TclError:
                pass
            self._sync_after = None
        if ser:
            try:
                ser.close()
            except Exception:
                pass
        self.alarm_event.clear()
        self.detected = False
        self.hold_left = 0.0
        self.link_var.set("DEMO MODE" if not self.closing.is_set() else "OFFLINE")
        self.online_dot.configure(fg=AMBER)
        self.online_label.configure(fg=AMBER)
        self.state_var.set("DEMO SWEEP" if not self.closing.is_set() else "OFFLINE")
        self.pause_text_var.set("PAUSE SCAN")
        self.pause_button.configure(text="PAUSE SCAN")
        self.update_alert(False, -1.0, self.angle)
        if write_log and hasattr(self, "log_box"):
            self.log("SERIAL LINK  //  Disconnected; display returns to demo sweep.")

    def send_command(self, command: str, report_failure=True) -> bool:
        ser = self.ser
        if not self.connected or ser is None or not ser.is_open:
            if report_failure:
                self.log(f"COMMAND NOT SENT  //  {command}  (not connected)")
            return False
        try:
            with self.serial_lock:
                ser.write((command.strip() + "\n").encode("ascii"))
            return True
        except Exception as exc:
            self.log(f"SERIAL WRITE ERROR  //  {exc}")
            return False

    def reader_loop(self, ser, stop_event):
        while not stop_event.is_set():
            try:
                raw = ser.readline()
                if raw:
                    line = raw.decode("ascii", errors="replace").strip()
                    if line:
                        self.inbox.put(("line", line))
            except Exception as exc:
                if not stop_event.is_set():
                    self.inbox.put(("reader_error", str(exc)))
                break

    def process_inbox(self):
        try:
            while True:
                kind, payload = self.inbox.get_nowait()
                if kind == "line":
                    self.handle_line(payload)
                elif kind == "reader_error":
                    self.log(f"SERIAL READ ERROR  //  {payload}")
                    self.link_var.set("LINK ERROR")
                    self.online_dot.configure(fg=RED)
                    self.online_label.configure(fg=RED)
        except queue.Empty:
            pass
        if not self.closing.is_set():
            self.root.after(40, self.process_inbox)

    # ---------- Serial command settings ----------
    def _speed_changed(self, value):
        self.speed_level = max(1, min(10, int(float(value))))
        self.speed_readout_var.set(f"{self.speed_level} / 10")
        self._schedule_settings()

    def _range_changed(self, value):
        self.detection_limit = max(2, min(400, int(float(value))))
        self.limit_readout_var.set(f"{self.detection_limit} cm")
        self._schedule_settings()

    def _hold_changed(self, value):
        self.hold_seconds = max(2, min(30, int(float(value))))
        self.hold_readout_var.set(f"{self.hold_seconds} seconds")
        self._schedule_settings()

    def _schedule_settings(self):
        if self._settings_after:
            try:
                self.root.after_cancel(self._settings_after)
            except tk.TclError:
                pass
        self._settings_after = self.root.after(450, self._send_settings_if_connected)

    def _send_settings_if_connected(self):
        self._settings_after = None
        if self.connected:
            self.apply_settings(silent=True)

    def apply_settings(self, silent=False):
        try:
            self.speed_level = max(1, min(10, int(self.speed_var.get())))
            self.detection_limit = max(2, min(400, int(self.range_var.get())))
            self.hold_seconds = max(2, min(30, int(self.hold_var.get())))
        except (ValueError, tk.TclError):
            messagebox.showwarning("Invalid settings", "Check speed, distance limit, and stop-time values.")
            return
        self.speed_readout_var.set(f"{self.speed_level} / 10")
        self.limit_readout_var.set(f"{self.detection_limit} cm")
        self.hold_readout_var.set(f"{self.hold_seconds} seconds")
        if not self.connected:
            if not silent:
                self.log("SETTINGS STORED LOCALLY  //  Connect Arduino to apply them to hardware.")
            return
        ok = True
        for command in (f"SPEED,{self.speed_level}", f"LIMIT,{self.detection_limit}", f"HOLD,{self.hold_seconds}"):
            ok = self.send_command(command, report_failure=False) and ok
        if ok and not silent:
            self.log(f"SETTINGS SENT  //  speed={self.speed_level}/10, alert≤{self.detection_limit} cm, minimum stop={self.hold_seconds}s.")

    def toggle_pause(self):
        if not self.connected:
            self.log("SCAN CONTROL  //  Connect to Arduino to pause/resume the physical motor.")
            return
        command = "RESUME" if self.user_paused else "PAUSE"
        if self.send_command(command):
            self.log(f"SCAN CONTROL  //  {command} requested.")

    # ---------- Data parser ----------
    def handle_line(self, line: str):
        self.last_packet = line
        self.rx_var.set(line[:80])
        self.last_packet_time = time.monotonic()

        if line.startswith("RADAR,"):
            parts = line.split(",")
            if len(parts) < 10:
                self.log(f"SERIAL FORMAT WARNING  //  {line}")
                return
            try:
                angle = float(parts[1])
                distance = float(parts[2])
                detected = parts[3].strip() == "1"
                direction = int(parts[4])
                paused = parts[5].strip() == "1"
                speed = int(parts[6])
                hold_left = max(0.0, float(parts[7]) / 1000.0)
                limit = int(float(parts[8]))
                hold = int(parts[9])
            except (ValueError, IndexError):
                self.log(f"SERIAL PARSE ERROR  //  {line}")
                return

            old_detected = self.detected
            self.angle = max(0.0, min(360.0, angle))
            self.distance = distance if 2.0 <= distance <= 400.0 else -1.0
            self.detected = detected
            self.direction = direction
            self.user_paused = paused
            self.hold_left = hold_left
            self.speed_level = max(1, min(10, speed))
            self.detection_limit = max(2, min(400, limit))
            self.hold_seconds = max(2, min(30, hold))
            self.speed_var.set(self.speed_level)
            self.range_var.set(self.detection_limit)
            self.hold_var.set(self.hold_seconds)
            self.speed_readout_var.set(f"{self.speed_level} / 10")
            self.limit_readout_var.set(f"{self.detection_limit} cm")
            self.hold_readout_var.set(f"{self.hold_seconds} seconds")
            self.angle_var.set(f"{self.angle:05.1f}°")
            self.distance_var.set(f"{self.distance:05.1f} cm" if self.distance > 0 else "---.- cm")
            self.hold_left_var.set(f"HOLD {self.hold_left:.1f}s" if detected else "HOLD —")
            self.pause_button.configure(text="RESUME SCAN" if paused else "PAUSE SCAN")
            if paused:
                self.state_var.set("MANUAL PAUSE")
            elif detected:
                self.state_var.set("OBJECT LOCKED")
            else:
                self.state_var.set("SCANNING  →" if direction > 0 else "SCANNING  ←")
            self.link_var.set("ONLINE  /  TELEMETRY")
            self.online_dot.configure(fg=GREEN if not detected else RED)
            self.online_label.configure(fg=GREEN if not detected else RED)

            now = time.monotonic()
            self.trail.append((self.angle, now))
            self.trail = [(a, t) for a, t in self.trail if now - t < 2.2][-45:]
            if detected and self.distance > 0:
                self._remember_target(self.angle, self.distance, now)
            self.update_alert(detected, self.distance, self.angle)
            if detected != old_detected and not line.startswith("EVENT,"):
                self.log("ALERT  //  Object state changed from telemetry." if detected else "CLEAR  //  Radar scanning resumed.")

        elif line.startswith("EVENT,OBJECT_DETECTED"):
            parts = line.split(",")
            angle = parts[2] if len(parts) > 2 else "?"
            distance = parts[3] if len(parts) > 3 else "?"
            self.log(f"!!! OBJECT DETECTED  //  angle {angle}°  |  distance {distance} cm  |  motor held  |  buzzer ON")
        elif line.startswith("EVENT,OBJECT_CLEARED"):
            parts = line.split(",")
            angle = parts[2] if len(parts) > 2 else "?"
            self.log(f"AREA CLEAR  //  contact cleared near angle {angle}°; scan resumed if not manually paused.")
        elif line.startswith("CONFIG,"):
            self.log("ARDUINO ACK  //  " + line.replace(",", "  /  "))
        elif line.startswith("READY,"):
            self.log("ARDUINO ONLINE  //  " + line.split(",", 1)[1].replace("_", " "))
        elif line.startswith("INFO,"):
            self.log("ARDUINO INFO  //  " + line.split(",", 1)[1])
        elif line.startswith("STATE,PAUSED"):
            self.user_paused = True
            self.state_var.set("MANUAL PAUSE")
            self.pause_button.configure(text="RESUME SCAN")
            self.log("SCAN CONTROL  //  Arduino confirmed pause.")
        elif line.startswith("STATE,SCANNING"):
            self.user_paused = False
            self.pause_button.configure(text="PAUSE SCAN")
            self.log("SCAN CONTROL  //  Arduino confirmed resume.")
        elif line.startswith("ERROR,"):
            self.log("ARDUINO ERROR  //  " + line.split(",", 1)[1].replace("_", " "))
        elif line:
            self.log("SERIAL RX  //  " + line)

    def _remember_target(self, angle, distance, now):
        # Avoid adding the same contact to the radar map on every 65 ms packet.
        if not self.targets:
            add = True
        else:
            old_angle, old_dist, old_time = self.targets[-1]
            diff = abs((angle - old_angle + 180) % 360 - 180)
            add = diff > 3.0 or abs(distance - old_dist) > 8.0 or now - old_time > 1.0
        if add:
            self.targets.append((angle, distance, now))
        self.targets = [(a, d, t) for a, d, t in self.targets if now - t < 18.0][-30:]

    def update_alert(self, active: bool, distance: float, angle: float):
        if active:
            self.alarm_event.set()
            self.alert_panel.configure(bg=RED_DARK, highlightbackground=RED)
            self.alert_title.configure(bg=RED_DARK, fg=RED, text="!! OBJECT DETECTED !!")
            if distance > 0:
                if self.hold_left > 0:
                    detail = (f"Contact at {distance:.1f} cm  •  bearing {angle:.1f}°. "
                              f"Stepper stopped. Minimum hold: {self.hold_left:.1f}s. Buzzer active.")
                else:
                    detail = (f"Contact at {distance:.1f} cm  •  bearing {angle:.1f}°. "
                              "Minimum stop elapsed; still waiting for the area to clear.")
            else:
                detail = "Object state active. Waiting for a valid distance reading. Motor held."
            self.alert_detail.configure(bg=RED_DARK, fg="#ffc5cc", text=detail)
            self.state_badge.configure(bg=RED_DARK, fg=RED)
        else:
            self.alarm_event.clear()
            self.alert_panel.configure(bg="#102d21", highlightbackground=GREEN_DIM)
            self.alert_title.configure(bg="#102d21", fg=GREEN, text="● RADAR CLEAR")
            self.alert_detail.configure(bg="#102d21", fg=TEXT,
                text=f"No object within {self.detection_limit} cm. Radar is ready to scan.")
            self.state_badge.configure(bg="#102d21", fg=GREEN)

    # ---------- Radar drawing ----------
    @staticmethod
    def point(cx: float, cy: float, radius: float, angle: float):
        theta = math.radians(angle)
        return cx + math.sin(theta) * radius, cy - math.cos(theta) * radius

    def animate(self):
        if not self.connected:
            self.demo_angle += self.demo_direction * 1.35
            if self.demo_angle >= 360:
                self.demo_angle, self.demo_direction = 360.0, -1
            elif self.demo_angle <= 0:
                self.demo_angle, self.demo_direction = 0.0, 1
            self.angle = self.demo_angle
        self.draw_radar()
        if not self.closing.is_set():
            self.root.after(45, self.animate)

    def draw_radar(self):
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 420)
        h = max(c.winfo_height(), 420)
        active = self.detected

        bg = "#070d0b" if not active else "#16070b"
        grid = "#123c2a" if not active else "#4b1d29"
        grid_bright = "#245a3c" if not active else "#853047"
        neon = RED if active else "#61ffb2"
        neon_soft = "#a4ffd2" if not active else "#ff9aaa"
        c.configure(bg=bg)
        c.create_rectangle(0, 0, w, h, fill=bg, outline="")

        # Fine technical grid and framed instrument border.
        spacing = max(24, int(min(w, h) / 27))
        for x in range(0, w, spacing):
            major = (x // spacing) % 4 == 0
            c.create_line(x, 0, x, h, fill=grid_bright if major else grid,
                          width=1 if major else 1)
        for y in range(0, h, spacing):
            major = (y // spacing) % 4 == 0
            c.create_line(0, y, w, y, fill=grid_bright if major else grid,
                          width=1 if major else 1)
        margin = 12
        c.create_rectangle(margin, margin, w-margin, h-margin,
                           outline=grid_bright, width=2)
        c.create_rectangle(margin+6, margin+6, w-margin-6, h-margin-6,
                           outline=grid, width=1)

        # Small signal waveform panel in the upper-left corner.
        wave_x, wave_y, wave_w, wave_h = 34, 28, min(260, w * 0.29), 76
        c.create_rectangle(wave_x, wave_y, wave_x+wave_w, wave_y+wave_h,
                           outline=grid_bright, width=1)
        c.create_text(wave_x+8, wave_y+8, text="ULTRASONIC ECHO / SIGNAL",
                      anchor="nw", fill=neon_soft, font=(MONO, 7, "bold"))
        mid = wave_y + wave_h * 0.62
        c.create_line(wave_x+10, mid, wave_x+wave_w-10, mid,
                      fill=grid_bright, width=1)
        wave_points = []
        phase = math.radians(self.angle * 3.0)
        count = 100
        for i in range(count):
            xx = wave_x + 10 + i * (wave_w-20) / (count-1)
            envelope = 0.12 + 0.88 * (math.sin(i * 0.19 + phase) ** 8)
            signal = math.sin(i * 0.58 + phase) * envelope
            yy = mid - signal * (wave_h * 0.30)
            wave_points.extend((xx, yy))
        if len(wave_points) >= 4:
            c.create_line(*wave_points, fill=neon, width=1.4, smooth=True)

        # Stylized world map in the upper-right corner, drawn as schematic silhouettes.
        map_w = min(245, w * 0.25)
        map_h = 92
        map_x = w - map_w - 34
        map_y = 26
        continents = [
            [(0.02,.18),(.13,.08),(.23,.13),(.28,.27),(.24,.39),(.18,.43),(.19,.57),(.12,.63),(.08,.48),(.03,.39)],
            [(.25,.56),(.32,.62),(.34,.77),(.31,.96),(.27,.82),(.24,.68)],
            [(.43,.18),(.52,.12),(.57,.19),(.55,.30),(.48,.34),(.45,.28)],
            [(.48,.36),(.58,.32),(.62,.49),(.59,.75),(.53,.92),(.48,.70),(.45,.51)],
            [(.57,.15),(.68,.07),(.83,.11),(.97,.20),(.91,.35),(.82,.34),(.76,.48),(.67,.40),(.60,.29)],
            [(.82,.53),(.91,.51),(.96,.62),(.91,.76),(.85,.69)],
        ]
        for poly in continents:
            coords = []
            for px, py in poly:
                coords.extend((map_x + px*map_w, map_y + py*map_h))
            c.create_polygon(*coords, fill="#164b37" if not active else "#542132",
                             outline=grid_bright, width=1)

        # Decorative lower-left wireframe globe.
        gx, gy, gr = 86, h-92, 44
        c.create_oval(gx-gr, gy-gr, gx+gr, gy+gr, outline=grid_bright, width=1)
        c.create_oval(gx-gr*0.47, gy-gr, gx+gr*0.47, gy+gr, outline=grid, width=1)
        c.create_oval(gx-gr*0.78, gy-gr, gx+gr*0.78, gy+gr, outline=grid, width=1)
        for factor in (0.36, 0.70):
            yy = gy - gr*factor
            c.create_oval(gx-gr*0.92, yy-7, gx+gr*0.92, yy+7, outline=grid, width=1)
            yy = gy + gr*factor
            c.create_oval(gx-gr*0.92, yy-7, gx+gr*0.92, yy+7, outline=grid, width=1)
        c.create_line(gx, gy-gr, gx, gy+gr, fill=grid, width=1)

        # Signal-strength bars at the lower-right, animated by angle and range.
        bars_x = w - 174
        bars_y = h - 142
        for i in range(6):
            val = 0.25 + 0.72 * abs(math.sin(self.angle*0.045 + i*0.72))
            if self.distance > 0 and self.distance <= self.detection_limit:
                val = max(val, 0.76 if i % 2 else 0.92)
            bw = 34 + val * 118
            yy = bars_y + i*18
            c.create_rectangle(bars_x, yy, bars_x+bw, yy+9,
                               fill=neon if i >= 4 or active else "#168454",
                               outline="")
            c.create_rectangle(bars_x+bw+6, yy, bars_x+bw+11, yy+9,
                               fill=grid_bright, outline="")

        # Main circular radar: large and centered in the two-thirds display area.
        cx = w * 0.50
        cy = h * 0.535
        radius = max(120, min(w * 0.385, h * 0.385))
        outer = radius + 18

        # Soft concentric halo and outer perimeter.
        c.create_oval(cx-outer, cy-outer, cx+outer, cy+outer,
                      outline=grid_bright, width=2)
        c.create_oval(cx-radius-6, cy-radius-6, cx+radius+6, cy+radius+6,
                      outline=neon_soft, width=1)

        # Range rings and range marks.
        for ring in range(1, 6):
            rr = radius * ring / 5.0
            c.create_oval(cx-rr, cy-rr, cx+rr, cy+rr,
                          outline=grid_bright if ring == 5 else grid, width=1 if ring < 5 else 2)
            if ring < 5:
                cm = self.detection_limit * ring / 5.0
                c.create_text(cx+8, cy-rr+9, text=f"{cm:.0f}", anchor="w",
                              fill="#508968" if not active else "#a65c6f", font=(MONO, 7))

        # Main compass axes and diagonal bearings.
        for degree in range(0, 360, 45):
            x, y = self.point(cx, cy, radius, degree)
            c.create_line(cx, cy, x, y, fill=grid, width=1)
        for degree in (0, 90, 180, 270):
            x, y = self.point(cx, cy, radius, degree)
            c.create_line(cx, cy, x, y, fill=grid_bright, width=2)

        # Dense degree scale: 360 ticks, longer at 5°, 10° and 30° marks.
        for degree in range(360):
            if degree % 30 == 0:
                tick = 17
                tick_color = neon_soft
                width = 2
            elif degree % 10 == 0:
                tick = 11
                tick_color = grid_bright
                width = 1
            elif degree % 5 == 0:
                tick = 7
                tick_color = grid_bright
                width = 1
            else:
                tick = 3.5
                tick_color = grid
                width = 1
            x1, y1 = self.point(cx, cy, radius-tick, degree)
            x2, y2 = self.point(cx, cy, radius, degree)
            c.create_line(x1, y1, x2, y2, fill=tick_color, width=width)

        # Bearing labels around the outer ring.
        for degree, label in ((0,"000°"),(45,"045°"),(90,"090°"),(135,"135°"),
                              (180,"180°"),(225,"225°"),(270,"270°"),(315,"315°")):
            label_offset = 2 if degree == 180 else 15
            tx, ty = self.point(cx, cy, outer+label_offset, degree)
            c.create_text(tx, ty, text=label, fill=neon_soft if degree % 90 == 0 else MUTED,
                          font=(MONO, 8, "bold" if degree % 90 == 0 else "normal"))

        # Trailing sweep fan follows the physical scan direction.
        direction = 1 if self.direction >= 0 else -1
        for width_deg, fan_color in ((42, "#0b2f20" if not active else "#35111a"),
                                     (30, "#10452d" if not active else "#541a29"),
                                     (18, "#17653e" if not active else "#7a2639")):
            pts = [cx, cy]
            offsets = list(range(width_deg, -1, -2))
            for offset in offsets:
                aa = (self.angle - direction*offset) % 360.0
                px, py = self.point(cx, cy, radius*0.985, aa)
                pts.extend((px, py))
            c.create_polygon(*pts, fill=fan_color, outline="")

        # A few fading historical sweep lines create persistence like a scope.
        now = time.monotonic()
        self.trail = [(a, t) for a, t in self.trail if now-t < 2.0]
        for a, stamp in self.trail[-24:]:
            age = now-stamp
            line_r = radius * (0.52 + 0.46*(1.0-age/2.0))
            px, py = self.point(cx, cy, line_r, a)
            c.create_line(cx, cy, px, py, fill="#27784f" if not active else "#9b334e", width=1)

        # Persistent return points are positioned by measured distance.
        self.targets = [(a, d, t) for a, d, t in self.targets if now-t < 18.0]
        for a, d, stamp in self.targets:
            rr = min(radius*0.95, max(5, d/max(1, self.detection_limit)*radius))
            px, py = self.point(cx, cy, rr, a)
            c.create_oval(px-7, py-7, px+7, py+7, outline="#52d995", width=1)
            c.create_oval(px-3, py-3, px+3, py+3, fill="#aaffd0", outline="")

        # Bright sweep ray and center emitter.
        bx, by = self.point(cx, cy, radius*0.99, self.angle)
        c.create_line(cx, cy, bx, by, fill="#138a58" if not active else "#a72f4b", width=9)
        c.create_line(cx, cy, bx, by, fill=neon, width=3)
        c.create_oval(cx-9, cy-9, cx+9, cy+9, fill=neon, outline=neon_soft, width=2)

        # Detection marker with a range-scaled position.
        if active:
            rr = radius*0.72
            if self.distance > 0:
                rr = min(radius*0.96, max(12, self.distance/max(1,self.detection_limit)*radius))
            mx, my = self.point(cx, cy, rr, self.angle)
            c.create_oval(mx-17, my-17, mx+17, my+17, outline=RED, width=2)
            c.create_oval(mx-9, my-9, mx+9, my+9, outline="#ff9eac", width=2)
            c.create_oval(mx-4, my-4, mx+4, my+4, fill=RED, outline="")
            status_text = (f"OBJECT LOCK  •  {self.distance:.1f} cm  •  {self.angle:.1f}°"
                           if self.distance > 0 else f"OBJECT DETECTED  •  {self.angle:.1f}°")
            status_color = RED
        else:
            status_text = ("LIVE RADAR  /  360° SCANNING" if self.connected
                           else "RADAR SIMULATION  /  CONNECT ARDUINO")
            status_color = neon
        c.create_text(cx, max(16, cy-radius-12), text=status_text,
                      fill=status_color, font=(MONO, 11, "bold"))

        # Fixed instrument readouts along the lower edge of the scope.
        c.create_text(cx, h-24,
                      text=f"RANGE LIMIT  {self.detection_limit} cm     /     SPEED  {self.speed_level}/10     /     HOLD  {self.hold_seconds}s",
                      fill=neon_soft if active else MUTED, font=(MONO, 8, "bold"))

    # ---------- Logs / audio / shutdown ----------
    def _alarm_worker(self):
        while not self.closing.is_set():
            if self.alarm_event.is_set() and winsound:
                try:
                    winsound.Beep(1120, 130)
                    if self.alarm_event.is_set():
                        winsound.Beep(760, 150)
                except Exception:
                    pass
                self.closing.wait(0.08)
            else:
                self.closing.wait(0.10)

    def log(self, message: str):
        if not hasattr(self, "log_box"):
            return
        stamp = time.strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{stamp}] {message}\n")
        lines = int(self.log_box.index("end-1c").split(".")[0])
        if lines > 110:
            self.log_box.delete("1.0", "18.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def close(self):
        if self.closing.is_set():
            return
        self.closing.set()
        self.alarm_event.clear()
        self.disconnect(write_log=False)
        self.root.destroy()


def main():
    root = tk.Tk()
    RadarApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
