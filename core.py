# -*- coding: utf-8 -*-
"""WinTweaks - tuning universal untuk CPU & GPU apa pun (Windows 10/11).

Semua tweak registry/service/power-plan disimpan nilai aslinya dan bisa
dikembalikan lewat tombol "Kembalikan (Undo)" / "Restore". Bersih-bersih
(hapus file temp/cache) tidak bisa di-undo karena filenya memang dihapus.

CATATAN KEAMANAN / SAFETY NOTES
--------------------------------
- Tidak ada fitur mematikan antivirus permanen. Defender real-time
  protection hanya bisa dimatikan SEMENTARA lewat API resmi Windows
  (Set-MpPreference), dan ditolak otomatis kalau Tamper Protection aktif.
- "Profil Game" mengganti RESOLUSI LAYAR SELURUH SISTEM sementara lewat
  Windows Display API (ChangeDisplaySettings) sebelum game dibuka, lalu
  mengembalikannya otomatis saat game ditutup. Ini BUKAN hook/injeksi ke
  proses game (teknik itu sama dengan cheat engine dan sengaja dihindari),
  jadi tidak bisa downscale satu window saja tanpa mengubah seluruh layar.
- Equalizer memakai Equalizer APO (open-source, sistem-wide) kalau sudah
  terpasang; aplikasi ini hanya menulis preset config, tidak memproses
  audio sendiri.
"""
import ctypes
from ctypes import wintypes
import json
import os
import platform
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

import winreg

APP = "WinTweaks"
EXE_DIR = os.path.dirname(os.path.abspath(
    sys.executable if getattr(sys, "frozen", False) else __file__))
BASE_DIR = getattr(sys, "_MEIPASS", EXE_DIR)
STATE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP)
STATE_FILE = os.path.join(STATE_DIR, "state.json")
NO_WINDOW = 0x08000000

# ---------------------------------------------------------------- tema
BG = "#0a0a0a"
BG2 = "#141414"
BG3 = "#1e1e1e"
BORDER = "#2a2a2a"
RED = "#ED1C24"
RED_HOVER = "#ff3b42"
RED_DIM = "#5a0e11"
FG = "#f2f2f2"
FG_DIM = "#9a9a9a"
F_TITLE = ("Segoe UI", 22, "bold")
F_SUB = ("Segoe UI", 10)
F_GROUP = ("Segoe UI", 10, "bold")
F_ITEM = ("Segoe UI", 9)
F_BTN = ("Segoe UI", 10, "bold")

D, S = winreg.REG_DWORD, winreg.REG_SZ
HIVES = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}

GUID_RE = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
ULTIMATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"
HIGH = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"

LANG = "id"  # diubah oleh App.set_lang()


# ======================================================== bahasa / i18n
STR = {
    "id": {
        "subtitle": "Tuning universal - CPU & GPU terdeteksi otomatis",
        "detected": "Terdeteksi: {0}",
        "tab_tweaks": "Tweaks",
        "tab_clean": "Bersih-bersih",
        "tab_profiles": "Profil Game",
        "tab_audio": "Audio",
        "grp_perf": "Performa & Power Plan",
        "grp_game": "Gaming / Game Mode",
        "grp_sys": "Sistem (bisa di-undo)",
        "grp_clean": "Bersih-bersih (tidak bisa di-undo)",
        "t_power": "Power plan Ultimate Performance",
        "t_visual": "Kurangi efek visual (transparansi, delay menu)",
        "t_startdelay": "Hilangkan delay startup aplikasi",
        "t_gamemode": "Aktifkan Game Mode",
        "t_gamedvr": "Matikan Xbox Game DVR / perekaman latar",
        "t_mmcss": "Prioritas CPU/GPU untuk game (MMCSS)",
        "t_mouse": "Matikan akselerasi mouse (aktif setelah logout/restart)",
        "t_wu_off": "Matikan Windows Update",
        "t_defender_off": "Matikan Defender real-time protection SEMENTARA",
        "warn_defender": "Ini mematikan proteksi real-time Windows Defender "
                         "sementara untuk sesi gaming. Nyalakan lagi lewat "
                         "Undo setelah selesai. Jangan browsing/download "
                         "file saat ini mati.\n\nLanjutkan?",
        "t_c_temp": "Temp user (%TEMP%)",
        "t_c_wtemp": "Temp Windows",
        "t_c_shader": "Shader cache (DirectX + AMD)",
        "t_c_recycle": "Kosongkan Recycle Bin",
        "t_c_wu": "Cache download Windows Update",
        "restore_point": "Buat restore point sebelum menerapkan",
        "btn_apply": "TERAPKAN",
        "btn_undo": "KEMBALIKAN (UNDO)",
        "clean_confirm": "Bersih-bersih menghapus file temp/cache dan tidak "
                         "bisa di-undo. Lanjutkan?",
        "pick_min_one": "Pilih minimal satu tweak.",
        "undo_confirm": "Kembalikan semua tweak (registry, power plan, "
                        "Windows Update, Defender, resolusi layar) ke "
                        "nilai awal?",
        "profiles_title": "Profil resolusi per game",
        "profiles_desc": "Ganti resolusi layar SELURUH sistem otomatis "
                         "saat game ini dibuka, lalu kembali ke resolusi "
                         "semula saat game ditutup. Ringankan beban GPU "
                         "tanpa masuk ke dalam proses game.",
        "profiles_name": "Nama",
        "profiles_exe": "File .exe game",
        "profiles_browse": "Pilih...",
        "profiles_w": "Lebar",
        "profiles_h": "Tinggi",
        "profiles_add": "Tambah Profil",
        "profiles_run": "Jalankan",
        "profiles_remove": "Hapus",
        "profiles_running": "Game berjalan dengan resolusi {0}x{1}. "
                            "Resolusi akan kembali otomatis saat game "
                            "ditutup.",
        "profiles_restored": "Resolusi layar dikembalikan ke semula.",
        "profiles_need_fields": "Isi nama, file exe, lebar, dan tinggi "
                                "dengan benar.",
        "profiles_res_fail": "Resolusi {0}x{1} tidak didukung layar, "
                             "game dijalankan tanpa downscale.",
        "profiles_prio": "  Prioritas CPU game: High.",
        "audio_title": "Equalizer (Equalizer APO)",
        "audio_desc": "WinTweaks tidak memproses audio sendiri - memakai "
                      "Equalizer APO (gratis, open-source, system-wide) "
                      "lalu menulis preset. Kalau belum terpasang, klik "
                      "tombol unduh di bawah dulu (perlu restart setelah "
                      "instal).",
        "audio_installed": "Equalizer APO terdeteksi terpasang.",
        "audio_not_installed": "Equalizer APO belum terpasang.",
        "audio_download": "Buka halaman unduh Equalizer APO",
        "audio_flat": "Flat (matikan semua efek)",
        "audio_bass": "Bass Boost",
        "audio_vocal": "Vocal Clarity",
        "audio_gaming": "Gaming (jejak langkah lebih jelas)",
        "audio_applied": "Preset '{0}' diterapkan ke Equalizer APO.",
        "audio_panel": "Buka panel Sound Windows",
        "log_restore_creating": "Membuat restore point (bisa lama)...",
        "log_restore_ok": "  Restore point dibuat.",
        "log_restore_skip": "  Restore point dilewati (System Protection "
                            "mati, atau sudah ada dalam 24 jam terakhir).",
        "log_done": "Selesai. Restart PC agar semua tweak aktif penuh.",
        "log_fail": "  Gagal: {0}",
        "log_power_ok": "  Power plan aktif.",
        "log_power_fail": "  Gagal set power plan: {0}",
        "log_power_fallback": "  Ultimate Performance tidak tersedia, "
                              "pakai High Performance.",
        "log_power_restored": "  Power plan dikembalikan.",
        "log_power_restore_fail": "  Gagal mengembalikan power plan.",
        "log_wu_off": "  Windows Update dihentikan dan dinonaktifkan.",
        "log_wu_off2": "  (Bisa dinyalakan lagi lewat Undo kapan saja.)",
        "log_wu_on": "  Windows Update diaktifkan kembali.",
        "log_def_off_ok": "  Real-time protection Defender dimatikan "
                          "SEMENTARA.",
        "log_def_off_ok2": "  Nyalakan lagi setelah selesai gaming lewat "
                           "tombol Undo.",
        "log_def_off_fail": "  Gagal: kemungkinan Tamper Protection aktif. "
                            "Matikan dulu manual lewat Windows Security > "
                            "Virus & threat protection settings.",
        "log_def_on_ok": "  Real-time protection Defender diaktifkan "
                         "kembali.",
        "log_def_on_fail": "  Gagal mengaktifkan ulang otomatis. Nyalakan "
                           "manual lewat Windows Security jika perlu.",
        "log_cleaned": "  Dibersihkan: {0}",
        "log_recycle": "  Recycle Bin dikosongkan.",
        "log_all_restored": "Semua tweak dikembalikan ke nilai awal. "
                            "Restart PC.",
    },
    "en": {
        "subtitle": "Universal tuning - CPU & GPU auto-detected",
        "detected": "Detected: {0}",
        "tab_tweaks": "Tweaks",
        "tab_clean": "Cleanup",
        "tab_profiles": "Game Profiles",
        "tab_audio": "Audio",
        "grp_perf": "Performance & Power Plan",
        "grp_game": "Gaming / Game Mode",
        "grp_sys": "System (undoable)",
        "grp_clean": "Cleanup (cannot be undone)",
        "t_power": "Ultimate Performance power plan",
        "t_visual": "Reduce visual effects (transparency, menu delay)",
        "t_startdelay": "Remove app startup delay",
        "t_gamemode": "Enable Game Mode",
        "t_gamedvr": "Disable Xbox Game DVR / background recording",
        "t_mmcss": "CPU/GPU priority for games (MMCSS)",
        "t_mouse": "Disable mouse acceleration (active after logout/restart)",
        "t_wu_off": "Disable Windows Update",
        "t_defender_off": "Disable Defender real-time protection TEMPORARILY",
        "warn_defender": "This disables Windows Defender real-time "
                         "protection temporarily for gaming sessions. "
                         "Turn it back on via Undo when done. Avoid "
                         "browsing/downloading files while it's off.\n\n"
                         "Continue?",
        "t_c_temp": "User temp (%TEMP%)",
        "t_c_wtemp": "Windows temp",
        "t_c_shader": "Shader cache (DirectX + AMD)",
        "t_c_recycle": "Empty Recycle Bin",
        "t_c_wu": "Windows Update download cache",
        "restore_point": "Create a restore point before applying",
        "btn_apply": "APPLY",
        "btn_undo": "RESTORE (UNDO)",
        "clean_confirm": "Cleanup deletes temp/cache files and cannot be "
                         "undone. Continue?",
        "pick_min_one": "Select at least one tweak.",
        "undo_confirm": "Restore all tweaks (registry, power plan, "
                        "Windows Update, Defender, screen resolution) to "
                        "their original values?",
        "profiles_title": "Per-game resolution profiles",
        "profiles_desc": "Automatically switches the WHOLE system's "
                         "resolution when this game launches, then "
                         "restores it on exit. Lightens the load on the "
                         "GPU without touching the game's process.",
        "profiles_name": "Name",
        "profiles_exe": "Game .exe file",
        "profiles_browse": "Browse...",
        "profiles_w": "Width",
        "profiles_h": "Height",
        "profiles_add": "Add Profile",
        "profiles_run": "Launch",
        "profiles_remove": "Remove",
        "profiles_running": "Game running at {0}x{1}. Resolution restores "
                            "automatically when the game closes.",
        "profiles_restored": "Screen resolution restored.",
        "profiles_need_fields": "Fill in name, exe file, width and height "
                                "correctly.",
        "profiles_res_fail": "Resolution {0}x{1} is not supported, "
                             "launching without downscale.",
        "profiles_prio": "  Game CPU priority: High.",
        "audio_title": "Equalizer (Equalizer APO)",
        "audio_desc": "WinTweaks doesn't process audio itself - it drives "
                      "Equalizer APO (free, open-source, system-wide) and "
                      "writes presets to it. If it's not installed yet, "
                      "click the download button below first (restart "
                      "needed after install).",
        "audio_installed": "Equalizer APO detected.",
        "audio_not_installed": "Equalizer APO is not installed.",
        "audio_download": "Open Equalizer APO download page",
        "audio_flat": "Flat (disable all effects)",
        "audio_bass": "Bass Boost",
        "audio_vocal": "Vocal Clarity",
        "audio_gaming": "Gaming (clearer footsteps)",
        "audio_applied": "Preset '{0}' applied to Equalizer APO.",
        "audio_panel": "Open Windows Sound panel",
        "log_restore_creating": "Creating restore point (may take a "
                                "while)...",
        "log_restore_ok": "  Restore point created.",
        "log_restore_skip": "  Restore point skipped (System Protection "
                            "is off, or one was made in the last 24h).",
        "log_done": "Done. Restart your PC for all tweaks to fully apply.",
        "log_fail": "  Failed: {0}",
        "log_power_ok": "  Power plan active.",
        "log_power_fail": "  Failed to set power plan: {0}",
        "log_power_fallback": "  Ultimate Performance unavailable, using "
                              "High Performance.",
        "log_power_restored": "  Power plan restored.",
        "log_power_restore_fail": "  Failed to restore power plan.",
        "log_wu_off": "  Windows Update stopped and disabled.",
        "log_wu_off2": "  (Can be re-enabled via Undo anytime.)",
        "log_wu_on": "  Windows Update re-enabled.",
        "log_def_off_ok": "  Defender real-time protection disabled "
                          "TEMPORARILY.",
        "log_def_off_ok2": "  Turn it back on via Undo when done gaming.",
        "log_def_off_fail": "  Failed: Tamper Protection is likely on. "
                            "Disable it manually in Windows Security > "
                            "Virus & threat protection settings first.",
        "log_def_on_ok": "  Defender real-time protection re-enabled.",
        "log_def_on_fail": "  Could not re-enable automatically. Turn it "
                           "on manually in Windows Security if needed.",
        "log_cleaned": "  Cleaned: {0}",
        "log_recycle": "  Recycle Bin emptied.",
        "log_all_restored": "All tweaks restored to original values. "
                            "Restart your PC.",
    },
}


def t(key, *args):
    s = STR[LANG].get(key, key)
    return s.format(*args) if args else s


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
    st.setdefault("profiles", [])
    st.setdefault("lang", "id")
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
        log(t("log_power_fallback"))

    code, out = run(["powercfg", "/setactive", target])
    log(t("log_power_ok") if code == 0 else t("log_power_fail", out))


def power_undo(st, log):
    p = st.get("power", {})
    if p.get("prev"):
        code, _ = run(["powercfg", "/setactive", p["prev"]])
        log(t("log_power_restored") if code == 0
            else t("log_power_restore_fail"))
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
    log(t("log_wu_off"))
    log(t("log_wu_off2"))


def wu_on(st, log):
    run(["sc", "config", "wuauserv", "start=", "demand"])
    run(["net", "start", "wuauserv"])
    st["flags"]["wu_off"] = False
    log(t("log_wu_on"))


# ======================================================== defender (sementara)
def defender_off(st, log):
    code, out = run_ps("Set-MpPreference -DisableRealtimeMonitoring $true")
    if code == 0:
        st["flags"]["defender_off"] = True
        log(t("log_def_off_ok"))
        log(t("log_def_off_ok2"))
    else:
        log(t("log_def_off_fail"))


def defender_on(st, log):
    code, out = run_ps("Set-MpPreference -DisableRealtimeMonitoring $false")
    if code == 0:
        st["flags"]["defender_off"] = False
        log(t("log_def_on_ok"))
    else:
        log(t("log_def_on_fail"))


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
        log(t("log_cleaned", fmt_size(clean_paths(paths_fn()))))
    return _apply


def clean_recycle(st, log):
    run_ps("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
    log(t("log_recycle"))


def clean_wu(st, log):
    run(["net", "stop", "wuauserv"])
    root = os.environ.get("SystemRoot", r"C:\Windows")
    freed = clean_paths([os.path.join(root, "SoftwareDistribution", "Download")])
    run(["net", "start", "wuauserv"])
    log(t("log_cleaned", fmt_size(freed)))


LOCAL = os.environ.get("LOCALAPPDATA", "")
WINROOT = os.environ.get("SystemRoot", r"C:\Windows")

GRP_PERF, GRP_GAME, GRP_SYS, GRP_CLEAN = "grp_perf", "grp_game", "grp_sys", "grp_clean"

MM = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"

TWEAKS = [
    dict(id="power", group=GRP_PERF, default=True, key="t_power",
         regs=[], apply=power_apply),
    dict(id="visual", group=GRP_PERF, default=True, key="t_visual",
         regs=[
             ("HKCU", r"Control Panel\Desktop", "MenuShowDelay", "0", S),
             ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
              "EnableTransparency", 0, D),
         ]),
    dict(id="startdelay", group=GRP_PERF, default=True, key="t_startdelay",
         regs=[("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize",
                "StartupDelayInMSec", 0, D)]),

    dict(id="gamemode", group=GRP_GAME, default=True, key="t_gamemode",
         regs=[
             ("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 1, D),
             ("HKCU", r"Software\Microsoft\GameBar", "AllowAutoGameMode", 1, D),
         ]),
    dict(id="gamedvr", group=GRP_GAME, default=True, key="t_gamedvr",
         regs=[
             ("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", 0, D),
             ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR",
              "AppCaptureEnabled", 0, D),
         ]),
    dict(id="mmcss", group=GRP_GAME, default=True, key="t_mmcss",
         regs=[
             ("HKLM", MM, "SystemResponsiveness", 10, D),
             ("HKLM", MM + r"\Tasks\Games", "GPU Priority", 8, D),
             ("HKLM", MM + r"\Tasks\Games", "Priority", 6, D),
             ("HKLM", MM + r"\Tasks\Games", "Scheduling Category", "High", S),
             ("HKLM", MM + r"\Tasks\Games", "SFIO Priority", "High", S),
         ]),
    dict(id="mouse", group=GRP_GAME, default=False, key="t_mouse",
         regs=[
             ("HKCU", r"Control Panel\Mouse", "MouseSpeed", "0", S),
             ("HKCU", r"Control Panel\Mouse", "MouseThreshold1", "0", S),
             ("HKCU", r"Control Panel\Mouse", "MouseThreshold2", "0", S),
         ]),

    dict(id="wu_off", group=GRP_SYS, default=False, key="t_wu_off",
         regs=[], apply=wu_off, undo=wu_on),
    dict(id="defender_off", group=GRP_SYS, default=False, key="t_defender_off",
         regs=[], apply=defender_off, undo=defender_on, warn="warn_defender"),

    dict(id="c_temp", group=GRP_CLEAN, default=True, key="t_c_temp",
         regs=[], apply=make_cleaner(lambda: [os.environ.get("TEMP")])),
    dict(id="c_wtemp", group=GRP_CLEAN, default=True, key="t_c_wtemp",
         regs=[], apply=make_cleaner(lambda: [os.path.join(WINROOT, "Temp")])),
    dict(id="c_shader", group=GRP_CLEAN, default=True, key="t_c_shader",
         regs=[], apply=make_cleaner(lambda: [
             os.path.join(LOCAL, "D3DSCache"),
             os.path.join(LOCAL, "AMD", "DxCache"),
             os.path.join(LOCAL, "AMD", "GLCache"),
             os.path.join(LOCAL, "AMD", "VkCache"),
         ])),
    dict(id="c_recycle", group=GRP_CLEAN, default=False, key="t_c_recycle",
         regs=[], apply=clean_recycle),
    dict(id="c_wu", group=GRP_CLEAN, default=False, key="t_c_wu",
         regs=[], apply=clean_wu),
]


# ======================================================== aksi inti
def make_restore_point(log):
    log(t("log_restore_creating"))
    code, out = run_ps("Checkpoint-Computer -Description 'WinTweaks' "
                       "-RestorePointType MODIFY_SETTINGS")
    log(t("log_restore_ok") if code == 0 else t("log_restore_skip"))


def apply_tweaks(selected, restore_point, log, done=True):
    st = load_state()
    if restore_point:
        make_restore_point(log)
    for item in selected:
        log(f"-> {t(item['key'])}")
        try:
            for hive, path, name, value, typ in item["regs"]:
                key = f"{hive}|{path}|{name}"
                if key not in st["reg"]:
                    st["reg"][key] = reg_get(hive, path, name)
                reg_set(hive, path, name, value, typ)
            if "apply" in item:
                item["apply"](st, log)
        except Exception as e:  # noqa: BLE001
            log(t("log_fail", e))
        save_state(st)
    if done:
        log(t("log_done"))


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
            log(t("log_fail", f"{name}: {e}"))
    power_undo(st, log)
    if st["flags"].get("wu_off"):
        wu_on(st, log)
    if st["flags"].get("defender_off"):
        defender_on(st, log)
    lang = st.get("lang", "id")
    save_state({"reg": {}, "power": {}, "flags": {}, "profiles": st.get("profiles", []),
               "lang": lang})
    log(t("log_all_restored"))


# ======================================================== resolusi layar (ctypes)
class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmPositionX", wintypes.LONG),
        ("dmPositionY", wintypes.LONG),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
    ]


ENUM_CURRENT_SETTINGS = -1
DM_PELSWIDTH = 0x00080000
DM_PELSHEIGHT = 0x00100000


def get_current_resolution():
    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    ctypes.windll.user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS,
                                              ctypes.byref(dm))
    return dm.dmPelsWidth, dm.dmPelsHeight


def set_resolution(width, height):
    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    ctypes.windll.user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS,
                                              ctypes.byref(dm))
    dm.dmPelsWidth = int(width)
    dm.dmPelsHeight = int(height)
    dm.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT
    return ctypes.windll.user32.ChangeDisplaySettingsW(ctypes.byref(dm), 0)


PROFILE_TWEAKS = ("gamemode", "gamedvr", "mmcss")


def launch_profile(p, log):
    """Jalankan game dari profil: downscale resolusi, tweak, prioritas CPU.
    Semua yang sifatnya sementara (resolusi, power plan) dikembalikan saat
    game ditutup."""
    exe = p["exe"]
    orig = get_current_resolution()
    res_changed = power_temp = False
    try:
        w, h = int(p.get("w", 0)), int(p.get("h", 0))
        if p.get("downscale", True) and w > 0 and h > 0 and (w, h) != orig:
            if set_resolution(w, h) == 0:
                res_changed = True
                log(t("profiles_running", w, h))
            else:
                log(t("profiles_res_fail", w, h))
        if p.get("tweak"):
            sel = [it for it in TWEAKS if it["id"] in PROFILE_TWEAKS]
            apply_tweaks(sel, False, log, done=False)
            st = load_state()
            if "prev" not in st["power"]:
                power_apply(st, log)
                save_state(st)
                power_temp = True
        proc = subprocess.Popen([exe], cwd=os.path.dirname(exe) or None)
        if p.get("prio"):
            try:
                import psutil
                psutil.Process(proc.pid).nice(psutil.HIGH_PRIORITY_CLASS)
                log(t("profiles_prio"))
            except Exception:  # noqa: BLE001
                pass
        proc.wait()
    except Exception as e:  # noqa: BLE001
        log(t("log_fail", e))
    finally:
        if res_changed:
            set_resolution(*orig)
            log(t("profiles_restored"))
        if power_temp:
            st = load_state()
            power_undo(st, log)
            st["power"] = {}
            save_state(st)
