# -*- coding: utf-8 -*-
"""WinTweaks CPU GPU Universal - tweak, power, record, overlay, audio FX."""
import ctypes, glob, math, os, queue, shutil, subprocess, sys, threading
import time, urllib.request, zipfile
import tkinter as tk
from tkinter import messagebox

import psutil
from PIL import ImageGrab

import core
from core import (run, run_ps, t, TWEAKS, apply_tweaks, undo_all,
                  get_current_resolution, EXE_DIR, BASE_DIR, NO_WINDOW)

try:
    import numpy as np
    from scipy.signal import sosfilt
    import pyaudiowpatch as pyaudio
except Exception:  # audio FX opsional
    pyaudio = None

THEMES = {"Radeon Red": ("#ff2d3a", "#ff8a3d"), "Cyber Cyan": ("#19e6ff", "#7b5cff"),
          "Neon Purple": ("#b45cff", "#ff4fd8"), "Matrix Green": ("#2dff8a", "#d4ff3d")}
BG, SIDE, CARD, CARD2, FG, DIM = "#0b0c10", "#101218", "#171a22", "#1f232d", "#f1f3f8", "#8b92a5"
FONT = "Segoe UI"
PICS = os.path.join(os.path.expanduser("~"), "Pictures", "WinTweaks")
FF_DIR = os.path.join(os.environ.get("APPDATA", EXE_DIR), "WinTweaks", "ffmpeg")
FF_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
BANDS = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
PRESETS = {"Flat": [0] * 10, "Bass Boost": [7, 6, 4, 2, 0, 0, 0, 0, 0, 0],
           "Vocal Jernih": [-2, -1, 0, 2, 4, 4, 3, 1, 0, -1],
           "Gaming FPS": [-3, -2, 0, 0, 1, 3, 5, 5, 3, 1],
           "Cinema 3D": [5, 4, 2, 0, -1, 0, 2, 4, 5, 4]}


def mix(c1, c2, f):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * f) for x, y in zip(a, b))


# ------------------------------------------------------------ stats
class Stats:
    def __init__(self):
        self.cpu = self.gpu = self.ram = 0.0
        self.fps = None
        self.gpu_name = "Mendeteksi..."
        self.amd = False
        self.on = True
        for fn in (self._gpu_info, self._loop, self._gpu_loop, self._fps_loop):
            threading.Thread(target=fn, daemon=True).start()

    def _gpu_info(self):
        _, out = run_ps("(Get-CimInstance Win32_VideoController).Name -join '|'")
        names = [n for n in out.split("|") if n]
        pick = next((n for n in names if "AMD" in n or "Radeon" in n), None)
        self.amd = pick is not None
        self.gpu_name = pick or (names[0] if names else "GPU tidak terdeteksi")

    def _loop(self):
        while self.on:
            self.cpu = psutil.cpu_percent(interval=1)
            self.ram = psutil.virtual_memory().percent

    def _gpu_loop(self):  # counter bawaan Windows, jalan untuk semua GPU
        while self.on:
            _, out = run(["typeperf", r"\GPU Engine(*engtype_3D)\Utilization Percentage",
                          "-sc", "1"])
            try:
                row = [l for l in out.splitlines() if l.startswith('"')][1]
                self.gpu = min(100.0, sum(float(x.strip('"')) for x in row.split('","')[1:]))
            except Exception:
                pass
            time.sleep(0.5)

    def _fps_loop(self):  # FPS butuh PresentMon.exe di folder app (opsional)
        pm = (glob.glob(os.path.join(EXE_DIR, "PresentMon*.exe")) +
              glob.glob(os.path.join(BASE_DIR, "PresentMon*.exe")))
        if not pm:
            return
        hdr = []
        for flag in ("--output_stdout", "-output_stdout"):
            p = subprocess.Popen([pm[0], flag, "--stop_existing_session"],
                                 stdout=subprocess.PIPE, text=True,
                                 creationflags=NO_WINDOW, errors="ignore")
            hdr = (p.stdout.readline() or "").strip().lower().split(",")
            if "processname" in hdr or "application" in hdr:
                break
        try:
            ip = hdr.index("processname") if "processname" in hdr else hdr.index("application")
            im = hdr.index("msbetweenpresents")
        except ValueError:
            return
        win, last = {}, time.time()
        for line in p.stdout:
            c = line.strip().split(",")
            try:
                if c[ip].lower() not in ("dwm.exe", "explorer.exe"):
                    win.setdefault(c[ip], []).append(float(c[im]))
            except Exception:
                continue
            if time.time() - last >= 1:
                best = max(win.values(), key=len, default=[])
                self.fps = round(1000 / (sum(best) / len(best))) if best else None
                win, last = {}, time.time()


# ------------------------------------------------------------ widgets
class Ring(tk.Canvas):
    def __init__(self, master, label, size, acc, getter, bg=CARD):
        super().__init__(master, width=size, height=size, bg=bg, highlightthickness=0)
        self.s, self.acc, self.get, self.label = size, acc, getter, label
        self.cur, self.ang, self.bgc = 0.0, 0.0, bg
        self._tick()

    def _tick(self):
        try:
            self.cur += (self.get() - self.cur) * 0.15
            self.ang = (self.ang + 4) % 360
            s, pad = self.s, self.s * 0.1
            w = max(4, s * 0.075)
            col = mix(self.acc[0], self.acc[1], min(1, self.cur / 100))
            self.delete("all")
            self.create_oval(pad, pad, s - pad, s - pad, outline=CARD2, width=w)
            self.create_arc(pad, pad, s - pad, s - pad, start=90, extent=-3.59 * self.cur,
                            style="arc", outline=mix(self.bgc, col, .35), width=w + 6)
            self.create_arc(pad, pad, s - pad, s - pad, start=90, extent=-3.59 * self.cur,
                            style="arc", outline=col, width=w)
            r, a = s / 2 - pad, math.radians(self.ang)  # titik berputar = "hidup"
            x, y = s / 2 + r * math.cos(a), s / 2 + r * math.sin(a)
            self.create_oval(x - 3, y - 3, x + 3, y + 3, fill=FG, outline="")
            self.create_text(s / 2, s / 2 - s * .04, text=f"{self.cur:.0f}%", fill=FG,
                             font=(FONT, int(s * .17), "bold"))
            self.create_text(s / 2, s / 2 + s * .17, text=self.label, fill=DIM,
                             font=(FONT, int(s * .08)))
        except tk.TclError:
            return
        self.after(33, self._tick)


class Btn(tk.Label):
    def __init__(self, master, text, cmd, app, primary=True):
        super().__init__(master, text=text, font=(FONT, 10, "bold"), cursor="hand2",
                         padx=16, pady=8, fg=FG)
        self.app, self.pri, self.f = app, primary, 0.0
        self._col()
        self.bind("<Enter>", lambda e: self._anim(1))
        self.bind("<Leave>", lambda e: self._anim(0))
        self.bind("<Button-1>", lambda e: cmd())

    def _col(self):
        a = self.app.acc[0]
        self.config(bg=mix(a, "#ffffff", .18 * self.f) if self.pri else mix(CARD2, a, .35 * self.f))

    def _anim(self, to):
        self.f = max(0, min(1, self.f + (.25 if to > self.f else -.25)))
        try:
            self._col()
            if self.f not in (0, 1):
                self.after(20, lambda: self._anim(to))
        except tk.TclError:
            pass


# ------------------------------------------------------------ audio fx
class AudioFX:
    def __init__(self):
        self.gains, self.pre, self.run_, self.err = [0.0] * 10, 0.0, False, ""

    def _sos(self, fs):
        out = []
        for f, g in zip(BANDS, self.gains):
            A, w0 = 10 ** (g / 40), 2 * math.pi * f / fs
            al = math.sin(w0) / 2.2
            b0, b1, b2 = 1 + al * A, -2 * math.cos(w0), 1 - al * A
            a0, a1, a2 = 1 + al / A, -2 * math.cos(w0), 1 - al / A
            out.append([b0 / a0, b1 / a0, b2 / a0, 1, a1 / a0, a2 / a0])
        return np.array(out)

    def outputs(self):
        if not pyaudio:
            return []
        p = pyaudio.PyAudio()
        res = [d["name"] for d in (p.get_device_info_by_index(i) for i in range(p.get_device_count()))
               if d["maxOutputChannels"] > 0 and not d.get("isLoopbackDevice")]
        p.terminate()
        return list(dict.fromkeys(res))

    def start(self, out_name):
        if not pyaudio:
            self.err = "Modul audio tidak ada di build ini."
            return
        self.run_ = True
        threading.Thread(target=self._work, args=(out_name,), daemon=True).start()

    def stop(self):
        self.run_ = False

    def _work(self, out_name):
        p = pyaudio.PyAudio()
        try:
            lb = p.get_default_wasapi_loopback()
            out = next(d for d in (p.get_device_info_by_index(i) for i in range(p.get_device_count()))
                       if out_name in d["name"] and d["maxOutputChannels"] > 0
                       and not d.get("isLoopbackDevice"))
            fs, ch = int(lb["defaultSampleRate"]), lb["maxInputChannels"]
            ins = p.open(format=pyaudio.paInt16, channels=ch, rate=fs, input=True,
                         input_device_index=lb["index"], frames_per_buffer=1024)
            outs = p.open(format=pyaudio.paInt16, channels=ch, rate=fs, output=True,
                          output_device_index=out["index"])
            sos, zi = self._sos(fs), None
            zi = np.zeros((sos.shape[0], 2, ch))
            while self.run_:
                x = np.frombuffer(ins.read(1024, exception_on_overflow=False), np.int16)
                x = x.reshape(-1, ch).astype(np.float32)
                sos = self._sos(fs)
                y, zi = sosfilt(sos, x, axis=0, zi=zi)
                y *= 10 ** (self.pre / 20)
                outs.write(np.clip(y, -32768, 32767).astype(np.int16).tobytes())
        except Exception as e:
            self.err = f"Audio FX gagal: {e}"
        finally:
            self.run_ = False
            p.terminate()


# ------------------------------------------------------------ app
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("WinTweaks CPU GPU Universal")
        self.root.geometry("1040x680")
        self.root.minsize(960, 620)
        self.root.configure(bg=BG)
        ico = os.path.join(BASE_DIR, "assets", "icon.ico")
        if os.path.exists(ico):
            self.root.iconbitmap(ico)
        self.theme, self.cur_page = "Radeon Red", "Dashboard"
        self.acc = THEMES[self.theme]
        self.stats, self.fx, self.q = Stats(), AudioFX(), queue.Queue()
        self.rec = self.ov = self.logbox = None
        self.checks = {}
        self.build()
        self.root.after(100, self.poll)

    def run(self):
        self.root.mainloop()
        self.stats.on = False
        self.stop_rec()

    def build(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.acc = THEMES[self.theme]
        side = tk.Frame(self.root, bg=SIDE, width=210)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="WinTweaks", bg=SIDE, fg=FG, font=(FONT, 20, "bold")).pack(
            anchor="w", padx=22, pady=(24, 0))
        tk.Label(side, text="CPU · GPU · Universal", bg=SIDE, fg=self.acc[0],
                 font=(FONT, 9, "bold")).pack(anchor="w", padx=22, pady=(0, 22))
        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)
        self.pages = {"Dashboard": self.p_dash, "Tweaks": self.p_tweaks,
                      "Power CPU/GPU": self.p_power, "Audio FX": self.p_audio,
                      "Rekam & Screenshot": self.p_rec, "Overlay FPS": self.p_over,
                      "Tema": self.p_theme}
        self.navs = {}
        for name in self.pages:
            f = tk.Frame(side, bg=SIDE, cursor="hand2")
            bar = tk.Frame(f, bg=SIDE, width=4)
            bar.pack(side="left", fill="y")
            lb = tk.Label(f, text=name, bg=SIDE, fg=DIM, font=(FONT, 11), anchor="w",
                          padx=18, pady=11)
            lb.pack(fill="x")
            f.pack(fill="x")
            for w in (f, lb):
                w.bind("<Button-1>", lambda e, n=name: self.go(n))
                w.bind("<Enter>", lambda e, n=name: self.navs[n][2].config(
                    fg=FG) if n != self.cur_page else None)
                w.bind("<Leave>", lambda e, n=name: self.navs[n][2].config(
                    fg=DIM) if n != self.cur_page else None)
            self.navs[name] = (f, bar, lb)
        self.go(self.cur_page)

    def go(self, name):
        self.cur_page = name
        for n, (f, bar, lb) in self.navs.items():
            sel = n == name
            bg = mix(SIDE, self.acc[0], .14) if sel else SIDE
            bar.config(bg=self.acc[0] if sel else SIDE)
            lb.config(fg=FG if sel else DIM, bg=bg)
            f.config(bg=bg)
        for w in self.main.winfo_children():
            w.destroy()
        self.logbox = None
        page = tk.Frame(self.main, bg=BG)
        tk.Label(page, text=name, bg=BG, fg=FG, font=(FONT, 20, "bold")).pack(
            anchor="w", padx=30, pady=(24, 12))
        body = tk.Frame(page, bg=BG)
        body.pack(fill="both", expand=True, padx=30, pady=(0, 20))
        self.pages[name](body)
        self.slide(page, 40)

    def slide(self, page, off):  # animasi masuk halaman
        try:
            page.place(x=off, y=0, relwidth=1, relheight=1)
            if off > 0:
                self.root.after(12, lambda: self.slide(page, int(off * .7)))
        except tk.TclError:
            pass

    def card(self, p):
        return tk.Frame(p, bg=CARD, padx=18, pady=16)

    def lab(self, p, text, dim=False, size=10, bold=False, **kw):
        return tk.Label(p, text=text, bg=p["bg"], fg=DIM if dim else FG, justify="left",
                        font=(FONT, size, "bold" if bold else "normal"), **kw)

    def chk(self, p, text, var):
        return tk.Checkbutton(p, text=text, variable=var, bg=CARD, fg=FG, selectcolor=CARD2,
                              activebackground=CARD, activeforeground=self.acc[0],
                              font=(FONT, 9), anchor="w")

    def menu(self, p, var, *opts):
        m = tk.OptionMenu(p, var, *opts)
        m.config(bg=CARD2, fg=FG, bd=0, highlightthickness=0, activebackground=CARD2)
        return m

    def scale(self, p, var=None, **kw):
        return tk.Scale(p, bg=CARD, fg=FG, troughcolor=CARD2, highlightthickness=0, bd=0,
                        activebackground=self.acc[0], variable=var, **kw)

    # ---- pages
    def p_dash(self, b):
        c = self.card(b)
        c.pack(fill="x")
        row = tk.Frame(c, bg=CARD)
        row.pack()
        for lbl, fn in (("CPU", lambda: self.stats.cpu), ("GPU", lambda: self.stats.gpu),
                        ("RAM", lambda: self.stats.ram)):
            Ring(row, lbl, 170, self.acc, fn).pack(side="left", padx=26)
        self.gpu_lbl = self.lab(b, "", dim=True)
        self.gpu_lbl.pack(anchor="w", pady=12)
        self.lab(b, f"CPU: {psutil.cpu_count(False)} core / {psutil.cpu_count()} thread  ·  "
                    f"{core.windows_label()}", dim=True).pack(anchor="w")
        self.lab(b, "Mode universal: tweak, power plan, rekam & overlay jalan di semua PC. "
                    "Fitur khusus GPU (Adrenalin, encoder AMF) hanya aktif di AMD.",
                 dim=True, wraplength=700).pack(anchor="w", pady=14)

    def p_tweaks(self, b):
        grid = tk.Frame(b, bg=BG)
        grid.pack(fill="x")
        groups = {}
        for it in TWEAKS:
            groups.setdefault(it["group"], []).append(it)
        self.checks = {}
        for i, (g, items) in enumerate(groups.items()):
            c = self.card(grid)
            c.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            grid.columnconfigure(i % 2, weight=1)
            self.lab(c, t(g), bold=True).pack(anchor="w", pady=(0, 6))
            for it in items:
                v = tk.BooleanVar(value=it["default"])
                self.checks[it["id"]] = (v, it)
                self.chk(c, t(it["key"]), v).pack(fill="x")
        bar = tk.Frame(b, bg=BG)
        bar.pack(fill="x", pady=8)
        Btn(bar, "Terapkan", self.do_apply, self).pack(side="left")
        Btn(bar, "Kembalikan (Undo)", self.do_undo, self, False).pack(side="left", padx=8)
        self.logbox = tk.Text(b, height=5, bg=CARD, fg=DIM, bd=0, font=("Consolas", 9))
        self.logbox.pack(fill="x")

    def log(self, s):
        self.q.put(s)

    def do_apply(self):
        sel = [it for v, it in self.checks.values() if v.get()]
        for it in sel:
            if it.get("warn") and not messagebox.askyesno("Peringatan", t(it["warn"])):
                return
        threading.Thread(target=apply_tweaks, args=(sel, True, self.log), daemon=True).start()

    def do_undo(self):
        threading.Thread(target=undo_all, args=(self.log,), daemon=True).start()

    def p_power(self, b):
        c = self.card(b)
        c.pack(fill="x", pady=(0, 10))
        self.lab(c, "CPU Power (lewat power plan Windows, aman & bisa diubah lagi)",
                 bold=True).pack(anchor="w")
        self.cmin, self.cmax, self.boost = tk.IntVar(value=5), tk.IntVar(value=100), tk.BooleanVar(value=True)
        for txt, var in (("Min CPU %", self.cmin), ("Max CPU %", self.cmax)):
            r = tk.Frame(c, bg=CARD)
            r.pack(fill="x", pady=2)
            self.lab(r, txt, width=10, anchor="w").pack(side="left")
            self.scale(r, var, from_=5, to=100, orient="horizontal", length=380).pack(side="left")
        self.chk(c, "Turbo Boost CPU aktif", self.boost).pack(anchor="w")
        r = tk.Frame(c, bg=CARD)
        r.pack(anchor="w", pady=8)
        for n, a in {"Hemat": (5, 60, False), "Seimbang": (5, 100, True),
                     "Performa": (60, 100, True), "Max": (100, 100, True)}.items():
            Btn(r, n, lambda a=a: (self.cmin.set(a[0]), self.cmax.set(a[1]), self.boost.set(a[2])),
                self, False).pack(side="left", padx=3)
        Btn(c, "Terapkan CPU", self.apply_cpu, self).pack(anchor="w")
        g = self.card(b)
        g.pack(fill="x")
        self.lab(g, f"GPU: {self.stats.gpu_name}", bold=True).pack(anchor="w")
        self.lab(g, "Klok/voltase/fan GPU AMD diatur lewat AMD Software (Adrenalin) - hanya GPU AMD. "
                    "PCIe Max Performa bisa dipakai di semua GPU.", dim=True,
                 wraplength=700).pack(anchor="w", pady=6)
        r = tk.Frame(g, bg=CARD)
        r.pack(anchor="w")
        Btn(r, "PCIe Max Performa", self.pcie, self, False).pack(side="left")
        Btn(r, "Buka AMD Software", self.open_amd, self).pack(side="left", padx=8)

    def apply_cpu(self):
        lo, hi, bo = min(self.cmin.get(), self.cmax.get()), self.cmax.get(), self.boost.get()
        def job():
            for k, v in (("PROCTHROTTLEMIN", lo), ("PROCTHROTTLEMAX", hi),
                         ("PERFBOOSTMODE", 2 if bo else 0)):
                for m in ("/setacvalueindex", "/setdcvalueindex"):
                    run(["powercfg", m, "SCHEME_CURRENT", "SUB_PROCESSOR", k, str(v)])
            run(["powercfg", "/setactive", "SCHEME_CURRENT"])
        threading.Thread(target=job, daemon=True).start()
        messagebox.showinfo("WinTweaks", f"CPU power diterapkan: min {lo}% / max {hi}%")

    def pcie(self):
        for m in ("/setacvalueindex", "/setdcvalueindex"):
            run(["powercfg", m, "SCHEME_CURRENT", "SUB_PCIEXPRESS", "ASPM", "0"])
        run(["powercfg", "/setactive", "SCHEME_CURRENT"])
        messagebox.showinfo("WinTweaks", "PCIe Link State Power Management dimatikan.")

    def open_amd(self):
        if not self.stats.amd:
            return messagebox.showinfo("WinTweaks", "GPU AMD tidak terdeteksi. Fitur ini hanya untuk AMD.")
        p = r"C:\Program Files\AMD\CNext\CNext\RadeonSoftware.exe"
        if os.path.exists(p):
            subprocess.Popen([p])
        else:
            messagebox.showinfo("WinTweaks", "AMD Software belum terpasang.")

    def p_audio(self, b):
        c = self.card(b)
        c.pack(fill="x")
        self.lab(c, "FX Sound Engine - EQ bawaan app, tanpa Equalizer APO", bold=True).pack(anchor="w")
        self.lab(c, "Menangkap suara sistem lalu mengolahnya. Pilih output (headset / speaker lain) "
                    "yang BEDA dari output default Windows supaya suara tidak dobel.",
                 dim=True, wraplength=700).pack(anchor="w", pady=(2, 8))
        outs = self.fx.outputs() or ["(tidak ada)"]
        self.outv = tk.StringVar(value=outs[0])
        self.menu(c, self.outv, *outs).pack(anchor="w")
        pr = tk.Frame(c, bg=CARD)
        pr.pack(anchor="w", pady=8)
        self.sliders = []
        for n, g in PRESETS.items():
            Btn(pr, n, lambda g=g: [s.set(v) for s, v in zip(self.sliders, g)], self, False).pack(
                side="left", padx=3)
        sl = tk.Frame(c, bg=CARD)
        sl.pack(pady=6)
        for i, f in enumerate(BANDS):
            col = tk.Frame(sl, bg=CARD)
            col.pack(side="left", padx=7)
            s = self.scale(col, from_=12, to=-12, orient="vertical", length=140, width=14,
                           command=lambda v, i=i: self.fx.gains.__setitem__(i, float(v)))
            s.set(self.fx.gains[i])
            s.pack()
            self.sliders.append(s)
            self.lab(col, f"{f // 1000}k" if f >= 1000 else str(f), dim=True, size=8).pack()
        self.fx_btn = Btn(c, "Matikan FX" if self.fx.run_ else "Nyalakan FX", self.toggle_fx, self)
        self.fx_btn.pack(anchor="w", pady=6)
        self.fx_msg = self.lab(c, "", dim=True)
        self.fx_msg.pack(anchor="w")

    def toggle_fx(self):
        if self.fx.run_:
            self.fx.stop()
            self.fx_btn.config(text="Nyalakan FX")
        else:
            self.fx.err = ""
            self.fx.start(self.outv.get())
            self.fx_btn.config(text="Matikan FX")

    # ---- rekam
    def ffmpeg(self):
        p = shutil.which("ffmpeg") or os.path.join(FF_DIR, "ffmpeg.exe")
        return p if os.path.exists(p) else None

    def get_ffmpeg(self):  # ffmpeg otomatis diunduh sekali, tanpa setup manual
        if self.ffmpeg():
            return self.ffmpeg()
        self.log("Mengunduh ffmpeg otomatis (sekali saja)...")
        os.makedirs(FF_DIR, exist_ok=True)
        zp = os.path.join(FF_DIR, "ff.zip")
        urllib.request.urlretrieve(FF_URL, zp)
        with zipfile.ZipFile(zp) as z:
            for n in z.namelist():
                if n.endswith("bin/ffmpeg.exe"):
                    with z.open(n) as s, open(os.path.join(FF_DIR, "ffmpeg.exe"), "wb") as d:
                        shutil.copyfileobj(s, d)
        os.remove(zp)
        return self.ffmpeg()

    def p_rec(self, b):
        c = self.card(b)
        c.pack(fill="x")
        w, h = get_current_resolution()
        self.res, self.fpsv = tk.StringVar(value=f"{w}x{h}"), tk.StringVar(value="30")
        r = tk.Frame(c, bg=CARD)
        r.pack(anchor="w")
        self.lab(r, "Resolusi").pack(side="left")
        self.menu(r, self.res, *dict.fromkeys([f"{w}x{h}", "1920x1080", "1600x900",
                                                "1280x720", "854x480"])).pack(side="left", padx=8)
        self.lab(r, "FPS").pack(side="left")
        self.menu(r, self.fpsv, "24", "30", "60").pack(side="left", padx=8)
        self.lab(c, "Encoder otomatis: AMD AMF (ringan untuk CPU) kalau GPU AMD, selain itu x264. "
                    "Hasil di Pictures\\WinTweaks.", dim=True, wraplength=700).pack(anchor="w", pady=8)
        r = tk.Frame(c, bg=CARD)
        r.pack(anchor="w")
        self.rec_btn = Btn(r, "■ Stop Rekam" if self.rec else "● Mulai Rekam", self.toggle_rec, self)
        self.rec_btn.pack(side="left")
        Btn(r, "Screenshot", self.shot, self, False).pack(side="left", padx=8)
        Btn(r, "Buka folder", lambda: (os.makedirs(PICS, exist_ok=True), os.startfile(PICS)),
            self, False).pack(side="left")
        self.rec_msg = self.lab(c, "", dim=True)
        self.rec_msg.pack(anchor="w", pady=8)

    def shot(self):
        os.makedirs(PICS, exist_ok=True)
        f = os.path.join(PICS, time.strftime("screenshot_%Y%m%d_%H%M%S.png"))
        ImageGrab.grab(all_screens=True).save(f)
        self.rec_msg.config(text=f"Tersimpan: {f}")

    def toggle_rec(self):
        if self.rec:
            self.stop_rec()
            return self.rec_btn.config(text="● Mulai Rekam")
        self.rec_btn.config(text="■ Stop Rekam")
        def job():
            try:
                ff = self.get_ffmpeg()
                os.makedirs(PICS, exist_ok=True)
                out = os.path.join(PICS, time.strftime("rekam_%Y%m%d_%H%M%S.mp4"))
                W, H = self.res.get().split("x")
                enc = (["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "24", "-qp_p", "26"]
                       if self.stats.amd else ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "24"])
                self.rec = subprocess.Popen(
                    [ff, "-y", "-f", "gdigrab", "-framerate", self.fpsv.get(), "-i", "desktop",
                     "-vf", f"scale={W}:{H}", *enc, "-pix_fmt", "yuv420p", out],
                    stdin=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
                self.log(f"Merekam -> {out}")
            except Exception as e:
                self.log(f"Rekam gagal: {e}")
        threading.Thread(target=job, daemon=True).start()

    def stop_rec(self):
        if self.rec:
            try:
                self.rec.stdin.write(b"q")
                self.rec.stdin.flush()
                self.rec.wait(8)
            except Exception:
                self.rec.kill()
            self.rec = None
            self.log("Rekaman selesai & tersimpan.")

    # ---- overlay
    def p_over(self, b):
        c = self.card(b)
        c.pack(fill="x")
        self.lab(c, "Cincin animasi CPU / GPU / RAM + FPS di atas layar game. Seret untuk "
                    "pindah posisi. Jalan di game windowed / borderless.", dim=True,
                 wraplength=700).pack(anchor="w", pady=(0, 10))
        self.ov_btn = Btn(c, "Matikan Overlay" if self.ov else "Nyalakan Overlay", self.toggle_ov, self)
        self.ov_btn.pack(anchor="w")
        self.lab(c, "FPS: taruh PresentMon.exe (gratis, Intel/GitHub) di folder yang sama dengan "
                    "WinTweaks.exe lalu buka ulang. Tanpa itu FPS tampil '--'.", dim=True,
                 wraplength=700).pack(anchor="w", pady=10)

    def toggle_ov(self):
        if self.ov:
            self.ov.destroy()
            self.ov = None
            return self.ov_btn.config(text="Nyalakan Overlay")
        o = tk.Toplevel(self.root)
        o.overrideredirect(True)
        o.attributes("-topmost", True)
        o.config(bg="#010101")
        o.attributes("-transparentcolor", "#010101")
        o.geometry("+30+30")
        for lbl, fn in (("CPU", lambda: self.stats.cpu), ("GPU", lambda: self.stats.gpu),
                        ("RAM", lambda: self.stats.ram)):
            Ring(o, lbl, 96, self.acc, fn, bg="#010101").pack(side="left")
        fps = tk.Label(o, bg="#010101", fg=self.acc[0], font=(FONT, 24, "bold"))
        fps.pack(side="left", padx=8)
        def upd():
            if self.ov is o:
                fps.config(text=f"{self.stats.fps} FPS" if self.stats.fps else "-- FPS")
                o.after(500, upd)
        d = {}
        o.bind("<Button-1>", lambda e: d.update(x=e.x, y=e.y))
        o.bind("<B1-Motion>", lambda e: o.geometry(
            f"+{o.winfo_x() + e.x - d['x']}+{o.winfo_y() + e.y - d['y']}"))
        self.ov = o
        upd()
        self.ov_btn.config(text="Matikan Overlay")

    def p_theme(self, b):
        for n, (a1, a2) in THEMES.items():
            c = self.card(b)
            c.pack(fill="x", pady=5)
            for i in range(12):
                tk.Frame(c, bg=mix(a1, a2, i / 11), width=22, height=22).pack(side="left")
            self.lab(c, n, bold=True).pack(side="left", padx=14)
            Btn(c, "Pakai", lambda n=n: self.set_theme(n), self, n == self.theme).pack(side="right")

    def set_theme(self, n):
        self.theme = n
        self.build()

    def poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                if self.logbox:
                    self.logbox.insert("end", m + "\n")
                    self.logbox.see("end")
                elif self.cur_page.startswith("Rekam"):
                    self.rec_msg.config(text=m)
        except (queue.Empty, tk.TclError):
            pass
        try:
            if self.cur_page == "Dashboard":
                self.gpu_lbl.config(text=f"GPU: {self.stats.gpu_name}")
            elif self.cur_page == "Audio FX" and self.fx.err:
                self.fx_msg.config(text=self.fx.err)
        except tk.TclError:
            pass
        self.root.after(200, self.poll)


def ensure_admin():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True
    args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable,
                                        " ".join(f'"{a}"' for a in args), None, 1)
    return False


if __name__ == "__main__":
    if ensure_admin():
        App().run()
