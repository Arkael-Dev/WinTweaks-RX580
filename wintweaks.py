# -*- coding: utf-8 -*-
"""WinTweaks CPU GPU Universal - tweak, power, record, overlay."""
import ctypes, ctypes.wintypes, glob, json, math, re, os, queue, shutil, subprocess, sys, threading
import time, urllib.request, zipfile
import tkinter as tk
from tkinter import messagebox

import psutil
from PIL import ImageGrab

import core
from core import (run, run_ps, t, TWEAKS, apply_tweaks, undo_all,
                  get_current_resolution, EXE_DIR, BASE_DIR, NO_WINDOW)

THEMES = {"Radeon Red": ("#ed1c24", "#ff5a1f"), "Cyber Cyan": ("#19e6ff", "#7b5cff"),
          "Neon Purple": ("#b45cff", "#ff4fd8"), "Matrix Green": ("#2dff8a", "#d4ff3d")}
BG, SIDE, CARD, CARD2, FG, DIM = "#09090a", "#0e0e10", "#151518", "#202026", "#f4f4f6", "#8d8d96"
FONT = "Segoe UI"
PICS = os.path.join(os.path.expanduser("~"), "Pictures", "WinTweaks")
FF_DIR = os.path.join(os.environ.get("APPDATA", EXE_DIR), "WinTweaks", "ffmpeg")
PM_DIR = os.path.join(os.environ.get("APPDATA", EXE_DIR), "WinTweaks", "presentmon")
FF_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
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
        self.fps_t, self.fps_started, self.fps_msg = 0, False, ""
        for fn in (self._gpu_info, self._loop, self._gpu_loop):
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

    def fps_now(self):
        return self.fps if self.fps and time.time() - self.fps_t < 3 else None

    def start_fps(self):
        if not self.fps_started:
            self.fps_started = True
            threading.Thread(target=self._fps_loop, daemon=True).start()

    def _pm_path(self):
        f = glob.glob(os.path.join(EXE_DIR, "PresentMon*.exe")) + glob.glob(
            os.path.join(PM_DIR, "PresentMon*.exe"))
        return f[0] if f else None

    def _pm_download(self):  # PresentMon diunduh otomatis sekali
        os.makedirs(PM_DIR, exist_ok=True)
        urls = []
        try:
            rq = urllib.request.Request(
                "https://api.github.com/repos/GameTechDev/PresentMon/releases/latest",
                headers={"User-Agent": "WinTweaks"})
            for a in json.load(urllib.request.urlopen(rq, timeout=20))["assets"]:
                if re.search(r"PresentMon.*x64\.exe$", a["name"], re.I):
                    urls.append(a["browser_download_url"])
        except Exception:
            pass
        urls.append("https://github.com/GameTechDev/PresentMon/releases/download/"
                    "v1.10.0/PresentMon-1.10.0-x64.exe")
        dst = os.path.join(PM_DIR, "PresentMon.exe")
        for u in urls:
            try:
                urllib.request.urlretrieve(u, dst)
                return dst
            except Exception:
                continue
        raise RuntimeError("unduh PresentMon gagal (cek internet)")

    def _fps_loop(self):
        self.fps_msg = "Menyiapkan FPS (unduh PresentMon sekali)..."
        pm = self._pm_path()
        if not pm:
            try:
                pm = self._pm_download()
            except Exception as e:
                self.fps_msg = f"FPS gagal: {e}"
                return
        hdr = []
        for args in (["--output_stdout", "--stop_existing_session"],
                     ["-output_stdout", "-stop_existing_session"]):
            p = subprocess.Popen([pm, *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 text=True, creationflags=NO_WINDOW, errors="ignore")
            for _ in range(8):
                ln = (p.stdout.readline() or "").strip().lower().split(",")
                if len(ln) > 5 and ("processname" in ln or "application" in ln):
                    hdr = ln
                    break
            if hdr:
                break
            p.kill()
        if not hdr:
            self.fps_msg = "FPS gagal: PresentMon tidak mau jalan."
            return
        try:
            ip = hdr.index("processname") if "processname" in hdr else hdr.index("application")
            im = next(hdr.index(k) for k in ("msbetweenpresents", "frametime") if k in hdr)
        except (ValueError, StopIteration):
            self.fps_msg = "FPS gagal: format PresentMon tidak dikenal."
            return
        self.fps_msg = ""
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
                if len(best) >= 5 and sum(best) > 0:
                    self.fps, self.fps_t = round(1000 * len(best) / sum(best)), time.time()
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


class Banner(tk.Canvas):
    """Header gaya AMD Radeon: panel gelap, potongan miring merah, kilau bergerak."""
    def __init__(self, master, acc):
        super().__init__(master, height=110, bg=CARD, highlightthickness=0)
        self.acc, self.x = acc, -200
        self.bind("<Configure>", lambda e: None)
        self._tick()

    def _tick(self):
        try:
            w = max(self.winfo_width(), 700)
            self.delete("all")
            self.create_polygon(0, 0, w * .62, 0, w * .62 - 70, 110, 0, 110,
                                fill=mix(CARD, self.acc[0], .16), outline="")
            self.create_polygon(w * .62 + 6, 0, w * .62 + 26, 0, w * .62 - 44, 110,
                                w * .62 - 64, 110, fill=self.acc[0], outline="")
            self.create_polygon(w * .62 + 34, 0, w * .62 + 40, 0, w * .62 - 30, 110,
                                w * .62 - 36, 110, fill=self.acc[1], outline="")
            sx = self.x
            self.create_polygon(sx, 0, sx + 50, 0, sx - 20, 110, sx - 70, 110,
                                fill=mix(CARD, "#ffffff", .07), outline="")
            self.x = sx + 9 if sx < w + 100 else -200
            self.create_text(28, 38, anchor="w", text="ARKAEL WIN TWEAKS", fill=FG,
                             font=(FONT, 26, "bold"))
            self.create_text(30, 76, anchor="w", text="CPU  ·  GPU   INTEL  &  AMD",
                             fill=self.acc[0], font=(FONT, 12, "bold"))
            self.create_text(w - 20, 92, anchor="e", text="RADEON STYLE", fill=DIM,
                             font=(FONT, 8, "bold"))
        except tk.TclError:
            return
        self.after(40, self._tick)


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


# ------------------------------------------------------------ app
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Arkael Win Tweaks")
        self.root.geometry("1040x680")
        self.root.minsize(960, 620)
        self.root.configure(bg=BG)
        ico = os.path.join(BASE_DIR, "assets", "icon.ico")
        if os.path.exists(ico):
            self.root.iconbitmap(ico)
        self.theme, self.cur_page = "Radeon Red", "Dashboard"
        self.acc = THEMES[self.theme]
        self.stats, _, self.q = Stats(), None, queue.Queue()
        self.rec = self.ov = self.logbox = self.rec_btn = None
        self.rec_busy, self.rec_t0, self.toast = False, 0, ("", 0)
        self.res_val, self.fps_val = get_current_resolution(), "30"
        self.checks = {}
        self.build()
        self.hotkeys()
        self.root.after(100, self.poll)

    def run(self):
        self.root.mainloop()
        self.stats.on = False
        self.stop_rec(wait=True)

    def build(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.acc = THEMES[self.theme]
        side = tk.Frame(self.root, bg=SIDE, width=210)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="ARKAEL", bg=SIDE, fg=FG, font=(FONT, 20, "bold")).pack(
            anchor="w", padx=22, pady=(24, 0))
        tk.Label(side, text="WIN TWEAKS", bg=SIDE, fg=self.acc[0],
                 font=(FONT, 9, "bold")).pack(anchor="w", padx=22, pady=(0, 22))
        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)
        self.pages = {"Dashboard": self.p_dash, "Tweaks": self.p_tweaks,
                      "Power CPU/GPU": self.p_power, "Rekam & Screenshot": self.p_rec, "Overlay FPS": self.p_over,
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
        f = tk.Frame(p, bg=CARD, padx=18, pady=14, highlightthickness=1,
                     highlightbackground="#26262c")
        tk.Frame(f, bg=self.acc[0], height=2).pack(fill="x", pady=(0, 10))
        return f

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
        Banner(b, self.acc).pack(fill="x", pady=(0, 12))
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
        self.res.trace_add("write", lambda *a: setattr(self, "res_val", tuple(self.res.get().split("x"))))
        self.fpsv.trace_add("write", lambda *a: setattr(self, "fps_val", self.fpsv.get()))
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

    def notify(self, msg):
        self.toast = (msg, time.time() + 2.5)

    def shot(self):
        os.makedirs(PICS, exist_ok=True)
        f = os.path.join(PICS, time.strftime("screenshot_%Y%m%d_%H%M%S.png"))
        ImageGrab.grab(all_screens=True).save(f)
        self.notify("Screenshot tersimpan ✓")
        self.log(f"Screenshot: {f}")

    def toggle_rec(self):
        if self.rec:
            return self.stop_rec()
        if self.rec_busy:
            return
        self.rec_busy = True
        self.notify("Mulai merekam...")
        def job():
            try:
                ff = self.get_ffmpeg()
                os.makedirs(PICS, exist_ok=True)
                out = os.path.join(PICS, time.strftime("rekam_%Y%m%d_%H%M%S.mp4"))
                W, H = self.res_val
                x264 = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "24"]
                amf = ["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "24", "-qp_p", "26"]
                for enc in ([amf, x264] if self.stats.amd else [x264]):
                    p = subprocess.Popen(
                        [ff, "-y", "-f", "gdigrab", "-framerate", self.fps_val, "-i", "desktop",
                         "-vf", f"scale={W}:{H}", *enc, "-pix_fmt", "yuv420p", out],
                        stdin=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
                    time.sleep(1.5)
                    if p.poll() is None:  # jalan; kalau AMF gagal otomatis coba x264
                        self.rec, self.rec_t0 = p, time.time()
                        self.log(f"Merekam -> {out}")
                        return
                self.notify("Rekam gagal")
                self.log("Rekam gagal: ffmpeg berhenti.")
            except Exception as e:
                self.notify("Rekam gagal")
                self.log(f"Rekam gagal: {e}")
            finally:
                self.rec_busy = False
        threading.Thread(target=job, daemon=True).start()

    def stop_rec(self, wait=False):
        r, self.rec = self.rec, None
        if not r:
            return
        def fin():
            try:
                r.stdin.write(b"q")
                r.stdin.flush()
                r.wait(10)
            except Exception:
                r.kill()
            self.log("Rekaman selesai & tersimpan.")
            self.notify("Rekaman tersimpan ✓")
        fin() if wait else threading.Thread(target=fin, daemon=True).start()

    def hotkeys(self):  # F9 = rekam, F10 = screenshot (jalan juga saat main game)
        def loop():
            u = ctypes.windll.user32
            u.RegisterHotKey(None, 1, 0, 0x78)
            u.RegisterHotKey(None, 2, 0, 0x79)
            msg = ctypes.wintypes.MSG()
            while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x0312:
                    self.q.put(f"__hk{msg.wParam}")
        threading.Thread(target=loop, daemon=True).start()

    def refresh_ui(self):
        if self.rec and self.rec.poll() is not None:
            self.rec = None
            self.notify("Rekaman berhenti")
        rec_on = bool(self.rec)
        try:
            if self.rec_btn is not None and self.rec_btn.winfo_exists():
                self.rec_btn.config(text="■ Stop Rekam" if rec_on else "● Mulai Rekam")
        except Exception:
            pass
        if self.ov:
            try:
                if rec_on:
                    el = int(time.time() - self.rec_t0)
                    blink = int(time.time() * 2) % 2
                    self.ov_rec.config(text=f"■ REC {el // 60:02d}:{el % 60:02d}  F9",
                                       bg="#e01b24" if blink else "#8a1016")
                else:
                    self.ov_rec.config(text="● REC  F9", bg="#26262c")
                f = self.stats.fps_now()
                self.ov_fps.config(text=f"{f} FPS" if f else "-- FPS")
                msg, until = self.toast
                self.ov_toast.config(text=msg if time.time() < until else
                                     (self.stats.fps_msg if not f else ""))
            except tk.TclError:
                pass

    # ---- overlay
    def p_over(self, b):
        c = self.card(b)
        c.pack(fill="x")
        self.lab(c, "Cincin animasi CPU / GPU / RAM + FPS + tombol Rekam & Screenshot di layar. "
                    "Hotkey global: F9 = rekam on/off, F10 = screenshot. Seret untuk pindah. "
                    "Jalan di game windowed / borderless.", dim=True,
                 wraplength=700).pack(anchor="w", pady=(0, 10))
        self.ov_btn = Btn(c, "Matikan Overlay" if self.ov else "Nyalakan Overlay", self.toggle_ov, self)
        self.ov_btn.pack(anchor="w")
        self.lab(c, "FPS otomatis: PresentMon diunduh sekali saat overlay pertama dinyalakan (butuh internet). FPS muncul setelah game berjalan.", dim=True,
                 wraplength=700).pack(anchor="w", pady=10)

    def toggle_ov(self):
        if self.ov:
            self.ov.destroy()
            self.ov = None
            return self.ov_btn.config(text="Nyalakan Overlay")
        self.stats.start_fps()
        o = tk.Toplevel(self.root)
        o.overrideredirect(True)
        o.attributes("-topmost", True)
        o.config(bg="#010101")
        o.attributes("-transparentcolor", "#010101")
        o.geometry("+30+30")
        top = tk.Frame(o, bg="#010101")
        top.pack(anchor="w")
        for lbl, fn in (("CPU", lambda: self.stats.cpu), ("GPU", lambda: self.stats.gpu),
                        ("RAM", lambda: self.stats.ram)):
            Ring(top, lbl, 96, self.acc, fn, bg="#010101").pack(side="left")
        self.ov_fps = tk.Label(top, bg="#010101", fg=self.acc[0], font=(FONT, 24, "bold"),
                               text="-- FPS")
        self.ov_fps.pack(side="left", padx=8)
        bar = tk.Frame(o, bg="#010101")
        bar.pack(anchor="w", pady=(2, 0))
        def pill(text, cmd):
            l = tk.Label(bar, text=text, bg="#26262c", fg=FG, font=(FONT, 10, "bold"),
                         padx=12, pady=5, cursor="hand2")
            l.pack(side="left", padx=(0, 6))
            l.bind("<Button-1>", lambda e: cmd())
            return l
        self.ov_rec = pill("● REC  F9", self.toggle_rec)
        pill("SHOT  F10", self.shot)
        self.ov_toast = tk.Label(o, bg="#010101", fg=FG, font=(FONT, 9, "bold"), anchor="w")
        self.ov_toast.pack(anchor="w", pady=(3, 0))
        d = {}
        for w in (o, top):
            w.bind("<Button-1>", lambda e: d.update(x=e.x_root - o.winfo_x(), y=e.y_root - o.winfo_y()))
            w.bind("<B1-Motion>", lambda e: o.geometry(f"+{e.x_root - d['x']}+{e.y_root - d['y']}"))
        self.ov = o
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
                if m == "__hk1":
                    self.toggle_rec()
                elif m == "__hk2":
                    self.shot()
                elif self.logbox:
                    self.logbox.insert("end", m + "\n")
                    self.logbox.see("end")
                elif self.cur_page.startswith("Rekam"):
                    self.rec_msg.config(text=m)
        except (queue.Empty, tk.TclError):
            pass
        self.refresh_ui()
        try:
            if self.cur_page == "Dashboard":
                self.gpu_lbl.config(text=f"GPU: {self.stats.gpu_name}")
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
