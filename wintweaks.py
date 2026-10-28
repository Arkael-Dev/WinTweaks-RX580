# -*- coding: utf-8 -*-
"""WinTweaks - tuning untuk Intel i3 Gen 8 + AMD RX 580 (Windows 10/11).

Semua tweak registry/service/power-plan disimpan nilai aslinya dan bisa
dikembalikan lewat tombol "Kembalikan (Undo)". Bagian bersih-bersih
(hapus file temp/cache) tidak bisa di-undo karena filenya memang dihapus.

CATATAN KEAMANAN:
Aplikasi ini TIDAK menonaktifkan antivirus secara permanen. Yang tersedia
hanya mematikan real-time protection Windows Defender SEMENTARA (lewat API
resmi Set-MpPreference) untuk sesi gaming, dan bisa dinyalakan lagi kapan
saja lewat tombol Undo atau Windows Security. Jika Tamper Protection aktif,
Windows akan menolak perubahan ini sampai Tamper Protection dimatikan
manual lewat Windows Security.
"""
import ctypes
import json
import os
import platform
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

import winreg

APP = "WinTweaks"
EXE_DIR = os.path.dirname(os.path.abspath(
    sys.executable if getattr(sys, "frozen", False) else __file__))
# PyInstaller --onefile mengekstrak --add-data ke folder sementara ini saat
# runtime; fallback ke folder exe/skrip untuk menjalankan langsung dari repo.
BASE_DIR = getattr(sys, "_MEIPASS", EXE_DIR)
STATE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP)
STATE_FILE = os.path.join(STATE_DIR, "state.json")
NO_WINDOW = 0x08000000

# ---------------------------------------------------------------- warna tema
BG = "#0a0a0a"
BG2 = "#151515"
BG3 = "#1e1e1e"
RED = "#ED1C24"
RED_DIM = "#8f1216"
FG = "#f2f2f2"
FG_DIM = "#a0a0a0"

D, S = winreg.REG_DWORD, winreg.REG_SZ
HIVES = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}

GUID_RE = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
ULTIMATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"
HIGH = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"


# ======================================================== util dasar
def run(args):
    r = subprocess.run(args, capture_output=True, text=True, errors="ignore",
                       creationflags=NO_WINDOW)
    return r.returncode, (r.stdout + r.stderr).strip()


def run_ps(script):
    return run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-Command", script])


def windows_label():
    try:
        build = int(platform.version().split(".")[-1])
    except (ValueError, IndexError):
        build = 0
    if build >= 22000:
        return "Windows 11"
    if build >= 10240:
        return "Windows 10"
    return f"Windows (build {build})"


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    st.setdefault("reg", {})
    st.setdefault("power", {})
    st.setdefault("flags", {})
    return st


def save_state(st):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2)


def reg_get(hive, path, name):
    try:
        with winreg.OpenKey(HIVES[hive], path, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            value, typ = winreg.QueryValueEx(k, name)
            return {"value": value, "type": typ}
    except OSError:
        return None


def reg_set(hive, path, name, value, typ):
    with winreg.CreateKeyEx(HIVES[hive], path, 0,
                            winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as k:
        winreg.SetValueEx(k, name, 0, typ, value)


def reg_delete(hive, path, name):
    try:
        with winreg.OpenKey(HIVES[hive], path, 0,
                            winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as k:
            winreg.DeleteValue(k, name)
    except OSError:
        pass


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ======================================================== power plan
def power_apply(st, log):
    p = st["power"]
    if "prev" not in p:
        _, out = run(["powercfg", "/getactivescheme"])
        m = GUID_RE.search(out)
        p["prev"] = m.group(0) if m else BALANCED

    _, listing = run(["powercfg", "/list"])
    target = p.get("new")
    if not target or target.lower() not in listing.lower():
        _, out = run(["powercfg", "-duplicatescheme", ULTIMATE])
        m = GUID_RE.search(out)
        target = m.group(0) if m else None
        p["new"] = target
    if not target:
        target = HIGH
        log("  Ultimate Performance tidak tersedia, pakai High Performance.")

    code, out = run(["powercfg", "/setactive", target])
    log("  Power plan aktif." if code == 0 else f"  Gagal set power plan: {out}")


def power_undo(st, log):
    p = st.get("power", {})
    if p.get("prev"):
        code, _ = run(["powercfg", "/setactive", p["prev"]])
        log("  Power plan dikembalikan." if code == 0
            else "  Gagal mengembalikan power plan.")
    if p.get("new"):
        run(["powercfg", "/delete", p["new"]])


# ======================================================== windows update
WU_POLICY = r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"


def wu_off(st, log):
    st["reg"].setdefault(f"HKLM|{WU_POLICY}|NoAutoUpdate",
                         reg_get("HKLM", WU_POLICY, "NoAutoUpdate"))
    reg_set("HKLM", WU_POLICY, "NoAutoUpdate", 1, D)
    run(["sc", "config", "wuauserv", "start=", "disabled"])
    run(["net", "stop", "wuauserv"])
    st["flags"]["wu_off"] = True
    log("  Windows Update dihentikan dan dinonaktifkan.")
    log("  (Bisa dinyalakan lagi lewat Undo kapan saja.)")


def wu_on(st, log):
    run(["sc", "config", "wuauserv", "start=", "demand"])
    run(["net", "start", "wuauserv"])
    st["flags"]["wu_off"] = False
    log("  Windows Update diaktifkan kembali.")


# ======================================================== defender (sementara)
def defender_off(st, log):
    code, out = run_ps("Set-MpPreference -DisableRealtimeMonitoring $true")
    if code == 0:
        st["flags"]["defender_off"] = True
        log("  Real-time protection Defender dimatikan SEMENTARA.")
        log("  Nyalakan lagi setelah selesai gaming lewat tombol Undo.")
    else:
        log("  Gagal: kemungkinan Tamper Protection aktif. Matikan dulu "
            "manual lewat Windows Security > Virus & threat protection "
            "settings, baru coba lagi.")


def defender_on(st, log):
    code, out = run_ps("Set-MpPreference -DisableRealtimeMonitoring $false")
    if code == 0:
        st["flags"]["defender_off"] = False
        log("  Real-time protection Defender diaktifkan kembali.")
    else:
        log("  Gagal mengaktifkan ulang otomatis. Nyalakan manual lewat "
            "Windows Security jika perlu.")


# ======================================================== AMD panel & audio
def open_amd_panel(st, log):
    candidates = [
        r"C:\Program Files\AMD\CNext\CNext\RadeonSoftware.exe",
        r"C:\Program Files\AMD\CNext\RadeonSoftware.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            subprocess.Popen([c])
            log("  AMD Software: Adrenalin Edition dibuka. Atur GPU Scaling "
                "/ Image Sharpening per-game di tab Gaming.")
            return
    run(["cmd", "/c", "start", "", "https://www.amd.com/en/support"])
    log("  AMD Software tidak terdeteksi terinstal. Halaman download "
        "dibuka di browser - install dulu untuk GPU Scaling / Image "
        "Sharpening per-game (RX 580 tidak mendukung RSR).")


def open_audio_panel(st, log):
    run(["control.exe", "mmsys.cpl", "sounds"])
    log("  Panel Sound dibuka. Klik kanan perangkat output > Properties > "
        "tab Enhancements > centang 'Loudness Equalization' untuk efek "
        "mirip equalizer otomatis yang stabil di semua aplikasi.")


# ======================================================== bersih-bersih
def clean_paths(paths):
    freed = 0
    for base in paths:
        if not base or not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base, topdown=False):
            for fname in files:
                fp = os.path.join(root, fname)
                try:
                    size = os.path.getsize(fp)
                    os.remove(fp)
                    freed += size
                except OSError:
                    pass
            for dname in dirs:
                try:
                    os.rmdir(os.path.join(root, dname))
                except OSError:
                    pass
    return freed


def make_cleaner(paths_fn):
    def _apply(st, log):
        log(f"  Dibersihkan: {fmt_size(clean_paths(paths_fn()))}")
    return _apply


def clean_recycle(st, log):
    run_ps("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
    log("  Recycle Bin dikosongkan.")


def clean_wu(st, log):
    run(["net", "stop", "wuauserv"])
    root = os.environ.get("SystemRoot", r"C:\Windows")
    freed = clean_paths([os.path.join(root, "SoftwareDistribution", "Download")])
    run(["net", "start", "wuauserv"])
    log(f"  Dibersihkan: {fmt_size(freed)}")


LOCAL = os.environ.get("LOCALAPPDATA", "")
WINROOT = os.environ.get("SystemRoot", r"C:\Windows")

GRP_PERF = "Performa & Power Plan"
GRP_GAME = "Gaming (RX 580 / Game Mode)"
GRP_SYS = "Sistem (bisa di-undo)"
GRP_CLEAN = "Bersih-bersih (tidak bisa di-undo)"

MM = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"

TWEAKS = [
    dict(id="power", group=GRP_PERF, default=True,
         label="Power plan Ultimate Performance",
         regs=[], apply=power_apply),
    dict(id="visual", group=GRP_PERF, default=True,
         label="Kurangi efek visual (transparansi, delay menu)",
         regs=[
             ("HKCU", r"Control Panel\Desktop", "MenuShowDelay", "0", S),
             ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
              "EnableTransparency", 0, D),
         ]),
    dict(id="startdelay", group=GRP_PERF, default=True,
         label="Hilangkan delay startup aplikasi",
         regs=[("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize",
                "StartupDelayInMSec", 0, D)]),

    dict(id="gamemode", group=GRP_GAME, default=True,
         label="Aktifkan Game Mode",
         regs=[
             ("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 1, D),
             ("HKCU", r"Software\Microsoft\GameBar", "AllowAutoGameMode", 1, D),
         ]),
    dict(id="gamedvr", group=GRP_GAME, default=True,
         label="Matikan Xbox Game DVR / perekaman latar",
         regs=[
             ("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", 0, D),
             ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR",
              "AppCaptureEnabled", 0, D),
         ]),
    dict(id="mmcss", group=GRP_GAME, default=True,
         label="Prioritas CPU/GPU untuk game (MMCSS)",
         regs=[
             ("HKLM", MM, "SystemResponsiveness", 10, D),
             ("HKLM", MM + r"\Tasks\Games", "GPU Priority", 8, D),
             ("HKLM", MM + r"\Tasks\Games", "Priority", 6, D),
             ("HKLM", MM + r"\Tasks\Games", "Scheduling Category", "High", S),
             ("HKLM", MM + r"\Tasks\Games", "SFIO Priority", "High", S),
         ]),
    dict(id="mouse", group=GRP_GAME, default=False,
         label="Matikan akselerasi mouse (aktif setelah logout/restart)",
         regs=[
             ("HKCU", r"Control Panel\Mouse", "MouseSpeed", "0", S),
             ("HKCU", r"Control Panel\Mouse", "MouseThreshold1", "0", S),
             ("HKCU", r"Control Panel\Mouse", "MouseThreshold2", "0", S),
         ]),
    dict(id="amd_panel", group=GRP_GAME, default=False,
         label="Buka AMD Software (GPU Scaling / Image Sharpening per-game)",
         regs=[], apply=open_amd_panel, no_undo_action=True),
    dict(id="audio_panel", group=GRP_GAME, default=False,
         label="Buka panel Audio Enhancement (Loudness Equalization)",
         regs=[], apply=open_audio_panel, no_undo_action=True),

    dict(id="wu_off", group=GRP_SYS, default=False,
         label="Matikan Windows Update",
         regs=[], apply=wu_off, undo=wu_on),
    dict(id="defender_off", group=GRP_SYS, default=False,
         label="Matikan Defender real-time protection SEMENTARA (gaming)",
         regs=[], apply=defender_off, undo=defender_on,
         warn="Ini mematikan proteksi real-time Windows Defender. Hanya "
              "untuk sesi gaming - nyalakan lagi lewat Undo setelah selesai. "
              "Jangan browsing/download file saat ini mati."),

    dict(id="c_temp", group=GRP_CLEAN, default=True, label="Temp user (%TEMP%)",
         regs=[], apply=make_cleaner(lambda: [os.environ.get("TEMP")])),
    dict(id="c_wtemp", group=GRP_CLEAN, default=True, label="Temp Windows",
         regs=[], apply=make_cleaner(lambda: [os.path.join(WINROOT, "Temp")])),
    dict(id="c_shader", group=GRP_CLEAN, default=True,
         label="Shader cache (DirectX + AMD)",
         regs=[], apply=make_cleaner(lambda: [
             os.path.join(LOCAL, "D3DSCache"),
             os.path.join(LOCAL, "AMD", "DxCache"),
             os.path.join(LOCAL, "AMD", "GLCache"),
             os.path.join(LOCAL, "AMD", "VkCache"),
         ])),
    dict(id="c_recycle", group=GRP_CLEAN, default=False,
         label="Kosongkan Recycle Bin", regs=[], apply=clean_recycle),
    dict(id="c_wu", group=GRP_CLEAN, default=False,
         label="Cache download Windows Update", regs=[], apply=clean_wu),
]


# ======================================================== aksi inti
def make_restore_point(log):
    log("Membuat restore point (bisa lama)...")
    code, out = run_ps("Checkpoint-Computer -Description 'WinTweaks' "
                       "-RestorePointType MODIFY_SETTINGS")
    if code == 0:
        log("  Restore point dibuat.")
    else:
        log("  Restore point dilewati (System Protection mati, atau sudah "
            "ada dalam 24 jam terakhir).")


def apply_tweaks(selected, restore_point, log):
    st = load_state()
    if restore_point:
        make_restore_point(log)
    for t in selected:
        log(f"-> {t['label']}")
        try:
            for hive, path, name, value, typ in t["regs"]:
                key = f"{hive}|{path}|{name}"
                if key not in st["reg"]:
                    st["reg"][key] = reg_get(hive, path, name)
                reg_set(hive, path, name, value, typ)
            if t["regs"]:
                log("  OK.")
            if "apply" in t:
                t["apply"](st, log)
        except Exception as e:  # noqa: BLE001
            log(f"  Gagal: {e}")
        save_state(st)
    log("Selesai. Restart PC agar semua tweak aktif penuh.")


def undo_all(log):
    st = load_state()
    for key, orig in st["reg"].items():
        hive, path, name = key.split("|", 2)
        try:
            if orig is None:
                reg_delete(hive, path, name)
            else:
                reg_set(hive, path, name, orig["value"], orig["type"])
        except Exception as e:  # noqa: BLE001
            log(f"  Gagal {name}: {e}")
    power_undo(st, log)
    if st["flags"].get("wu_off"):
        wu_on(st, log)
    if st["flags"].get("defender_off"):
        defender_on(st, log)
    save_state({"reg": {}, "power": {}, "flags": {}})
    log("Semua tweak dikembalikan ke nilai awal. Restart PC.")


# ======================================================== GUI
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP} - i3 Gen 8 + RX 580")
        self.root.geometry("600x760")
        self.root.configure(bg=BG)
        self.q = queue.Queue()
        self.vars = {}
        self.busy = False
        self._pulse_step = 0

        self._set_icon()
        self._style()

        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x")
        self._banner(header)

        sub = tk.Frame(self.root, bg=BG)
        sub.pack(fill="x", padx=14, pady=(2, 8))
        tk.Label(sub, text=f"Terdeteksi: {windows_label()}", bg=BG,
                 fg=FG_DIM, font=("Segoe UI", 9)).pack(anchor="w")

        canvas_wrap = tk.Frame(self.root, bg=BG)
        canvas_wrap.pack(fill="both", expand=True, padx=12)
        canvas = tk.Canvas(canvas_wrap, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(canvas_wrap, orient="vertical",
                               command=canvas.yview)
        main = tk.Frame(canvas, bg=BG)
        main.bind("<Configure>",
                 lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=main, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for group in (GRP_PERF, GRP_GAME, GRP_SYS, GRP_CLEAN):
            box = tk.LabelFrame(main, text=f"  {group}  ", bg=BG2, fg=RED,
                                font=("Segoe UI", 10, "bold"),
                                labelanchor="nw", bd=1,
                                highlightbackground=RED_DIM)
            box.pack(fill="x", pady=6, ipady=4)
            for t in TWEAKS:
                if t["group"] != group:
                    continue
                v = tk.BooleanVar(value=t["default"])
                self.vars[t["id"]] = v
                row = tk.Frame(box, bg=BG2)
                row.pack(fill="x", padx=8, pady=2)
                cb = tk.Checkbutton(
                    row, text=t["label"], variable=v, bg=BG2, fg=FG,
                    selectcolor=BG3, activebackground=BG2,
                    activeforeground=RED, font=("Segoe UI", 9),
                    anchor="w", highlightthickness=0, bd=0)
                cb.pack(side="left", anchor="w")
                if t.get("warn"):
                    tk.Label(row, text="!", bg=BG2, fg=RED,
                             font=("Segoe UI", 9, "bold")).pack(side="left",
                                                                padx=4)

        self.rp = tk.BooleanVar(value=True)
        rp_row = tk.Frame(main, bg=BG)
        rp_row.pack(fill="x", pady=(6, 2))
        tk.Checkbutton(rp_row, text="Buat restore point sebelum menerapkan",
                       variable=self.rp, bg=BG, fg=FG, selectcolor=BG3,
                       activebackground=BG, activeforeground=RED,
                       font=("Segoe UI", 9)).pack(anchor="w")

        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=12, pady=8)
        self.btn_apply = self._make_button(bar, "TERAPKAN", self.on_apply,
                                           accent=True)
        self.btn_apply.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.btn_undo = self._make_button(bar, "KEMBALIKAN (UNDO)",
                                          self.on_undo, accent=False)
        self.btn_undo.pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.logbox = ScrolledText(self.root, height=11, bg="#050505",
                                   fg="#d8d8d8", insertbackground=FG,
                                   font=("Consolas", 9), bd=0,
                                   highlightthickness=1,
                                   highlightbackground=RED_DIM)
        self.logbox.pack(fill="both", expand=False, padx=12, pady=(0, 10))
        self.logbox.configure(state="disabled")

        self.root.after(100, self.pump)
        self._fade_in()
        self._pulse(self.btn_apply)

    # ---------- tampilan ----------
    def _set_icon(self):
        ico = os.path.join(BASE_DIR, "assets", "icon.ico")
        if os.path.exists(ico):
            try:
                self.root.iconbitmap(ico)
            except tk.TclError:
                pass

    def _style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Vertical.TScrollbar", background=BG3,
                        troughcolor=BG, bordercolor=BG, arrowcolor=FG)

    def _banner(self, parent):
        png = os.path.join(BASE_DIR, "assets", "banner.png")
        if os.path.exists(png):
            try:
                self._banner_img = tk.PhotoImage(file=png)
                tk.Label(parent, image=self._banner_img, bg=BG).pack(fill="x")
                return
            except tk.TclError:
                pass
        tk.Label(parent, text="WinTweaks", bg=BG, fg=RED,
                 font=("Segoe UI", 28, "bold")).pack(anchor="w", padx=16,
                                                      pady=10)

    def _make_button(self, parent, text, command, accent):
        b = tk.Button(parent, text=text, command=command,
                      bg=RED if accent else BG3,
                      fg="#ffffff" if accent else FG,
                      activebackground=RED_DIM if accent else BG2,
                      activeforeground="#ffffff", bd=0, relief="flat",
                      font=("Segoe UI", 10, "bold"), padx=10, pady=10,
                      cursor="hand2")
        return b

    def _fade_in(self, alpha=0.0):
        # animasi fade-in jendela saat start
        try:
            alpha = min(1.0, alpha + 0.08)
            self.root.attributes("-alpha", alpha)
            if alpha < 1.0:
                self.root.after(15, lambda: self._fade_in(alpha))
        except tk.TclError:
            pass  # platform tidak mendukung -alpha

    def _pulse(self, widget):
        # animasi pulsing ringan pada tombol Terapkan (nuansa AMD glow)
        colors = ["#ED1C24", "#ff4a50", "#ED1C24", "#c4151b"]
        self._pulse_step = (self._pulse_step + 1) % len(colors)
        try:
            if not self.busy:
                widget.configure(bg=colors[self._pulse_step])
        except tk.TclError:
            return
        self.root.after(700, lambda: self._pulse(widget))

    # ---------- threading / log ----------
    def log(self, msg):
        self.q.put(msg)

    def pump(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg is None:
                    self.busy = False
                    self.btn_apply.configure(state="normal")
                    self.btn_undo.configure(state="normal")
                    continue
                self.logbox.configure(state="normal")
                self.logbox.insert("end", msg + "\n")
                self.logbox.see("end")
                self.logbox.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self.pump)

    def start(self, fn):
        if self.busy:
            return
        self.busy = True
        self.btn_apply.configure(state="disabled")
        self.btn_undo.configure(state="disabled")

        def worker():
            try:
                fn()
            finally:
                self.q.put(None)

        threading.Thread(target=worker, daemon=True).start()

    # ---------- aksi ----------
    def on_apply(self):
        selected = [t for t in TWEAKS if self.vars[t["id"]].get()]
        if not selected:
            messagebox.showinfo(APP, "Pilih minimal satu tweak.")
            return
        if any(t["group"] == GRP_CLEAN for t in selected):
            if not messagebox.askyesno(
                    APP, "Bersih-bersih menghapus file temp/cache dan tidak "
                         "bisa di-undo. Lanjutkan?"):
                return
        for t in selected:
            if t.get("warn") and not messagebox.askyesno(APP, t["warn"]):
                return
        rp = self.rp.get()
        self.start(lambda: apply_tweaks(selected, rp, self.log))

    def on_undo(self):
        if messagebox.askyesno(APP, "Kembalikan semua tweak (registry, "
                                    "power plan, Windows Update, Defender) "
                                    "ke nilai awal?"):
            self.start(lambda: undo_all(self.log))

    def run(self):
        self.root.mainloop()


def ensure_admin():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True
    args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
    params = " ".join(f'"{a}"' for a in args)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params,
                                        None, 1)
    return False


if __name__ == "__main__":
    if ensure_admin():
        App().run()
