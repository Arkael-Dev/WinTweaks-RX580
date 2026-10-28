# -*- coding: utf-8 -*-
"""Fix gabungan:
1. Rekam: tombol STOP selalu ada (aplikasi + overlay), bisa dibatalkan saat "memulai",
   loop UI tidak mati kena error, hotkey cadangan Ctrl+Shift+R, auto-stop kalau disk hampir penuh.
2. Overlay statistik (cincin & teks kecil): slider Transparansi + pilihan Latar Tembus/Solid,
   langsung berubah saat digeser dan tersimpan.
Aman dijalankan di atas wintweaks.py yang sudah/belum kena apply_recfix.py.
"""
import sys

P = "wintweaks.py"
s = open(P, encoding="utf-8").read()


def rep(old, new):
    global s
    if s.count(old) != 1:
        sys.exit(f"GAGAL ({s.count(old)}x ketemu):\n" + old[:100])
    s = s.replace(old, new)


def block(start, end, new):
    """Ganti teks dari penanda `start` sampai sebelum `end`."""
    global s
    a = s.find(start)
    if a < 0:
        sys.exit("GAGAL: penanda tidak ketemu: " + start[:60])
    b = s.find(end, a + len(start))
    if b < 0:
        sys.exit("GAGAL: penanda akhir tidak ketemu: " + end[:60])
    s = s[:a] + new + s[b:]


if "def set_ov_alpha" in s:
    sys.exit("Sudah pernah dipasang, tidak ada yang diubah.")

# ---------------------------------------------------------------- 1. state awal
rep('''        self.rec_busy, self.rec_t0, self.toast = False, 0, ("", 0)''',
    '''        self.rec_busy, self.rec_t0, self.toast = False, 0, ("", 0)
        self.rec_cancel, self.rec_clock, self._disk_t = False, None, 0
        st0 = core.load_state()  # transparansi overlay tersimpan
        self.ov_alpha, self.ov_clear = st0.get("ov_alpha"), st0.get("ov_clear")''')

# ---------------------------------------------------------------- 2. FloatWin: alpha
rep("    def __init__(self, app, which, fill, x, y, scale, transparent):",
    "    def __init__(self, app, which, fill, x, y, scale, transparent, alpha=.92):")
rep('''        if transparent:
            o.attributes("-transparentcolor", T)
        else:
            o.attributes("-alpha", .92)''',
    '''        if transparent:
            o.attributes("-transparentcolor", T)
        o.attributes("-alpha", max(.2, min(1.0, alpha)))''')
rep('''    def pos(self):
        return self.o.winfo_x(), self.o.winfo_y()''',
    '''    def set_alpha(self, a):
        try:
            self.o.attributes("-alpha", max(.2, min(1.0, a)))
        except tk.TclError:
            pass

    def pos(self):
        return self.o.winfo_x(), self.o.winfo_y()''')

# ---------------------------------------------------------------- 3. tombol rekam di aplikasi
rep('''        self.rec_msg = self.lab(c, "", dim=True)
        self.rec_msg.pack(anchor="w", pady=8)''',
    '''        self.rec_clock = self.lab(c, "", bold=True)
        self.rec_clock.config(fg="#ff4d57")
        self.rec_clock.pack(anchor="w", pady=(10, 0))
        self.rec_msg = self.lab(c, "", dim=True)
        self.rec_msg.pack(anchor="w", pady=8)''')

# ---------------------------------------------------------------- 4. rekam / stop / hotkey / refresh_ui
block("    def toggle_rec(self):", "    # ---- overlay (2 jendela", '''    def toggle_rec(self):
        if self.rec:
            return self.stop_rec()
        if self.rec_busy:  # lagi menyiapkan ffmpeg -> klik lagi = batalkan
            self.rec_cancel = True
            self.notify("Dibatalkan")
            self.log("Persiapan rekam dibatalkan.")
            return
        self.rec_busy, self.rec_cancel = True, False
        self.notify("Mulai merekam...")

        def job():
            try:
                ff = self.get_ffmpeg()
                if self.rec_cancel:
                    return
                os.makedirs(PICS, exist_ok=True)
                out = os.path.join(PICS, time.strftime("rekam_%Y%m%d_%H%M%S.mp4"))
                W, H = self.res_val
                x264 = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "24"]
                amf = ["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "24", "-qp_p", "26"]
                for enc in ([amf, x264] if self.stats.amd else [x264]):
                    p = subprocess.Popen(
                        [ff, "-y", "-f", "gdigrab", "-framerate", self.fps_val, "-i", "desktop",
                         "-vf", f"scale={W}:{H}", *enc, "-pix_fmt", "yuv420p", out],
                        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
                    time.sleep(1.5)
                    if p.poll() is None:  # jalan; kalau AMF gagal otomatis coba x264
                        if self.rec_cancel:  # dibatalkan selagi ffmpeg start
                            self._quit_proc(p)
                            return
                        self.rec, self.rec_t0 = p, time.time()
                        self.log(L("Merekam -> {0}").format(out))
                        return
                self.notify("Rekam gagal")
                self.log("Rekam gagal: ffmpeg berhenti.")
            except Exception as e:
                self.notify("Rekam gagal")
                self.log(f"Rekam gagal: {e}")
            finally:
                self.rec_busy = False
        threading.Thread(target=job, daemon=True).start()

    def _quit_proc(self, r):  # hentikan ffmpeg dengan rapi, paksa kill kalau macet
        try:
            r.stdin.write(b"q")
            r.stdin.flush()
            r.wait(10)
        except Exception:
            pass
        try:
            if r.poll() is None:
                r.kill()
        except Exception:
            pass

    def stop_rec(self, wait=False):
        r, self.rec = self.rec, None
        if not r:
            return

        def fin():
            self._quit_proc(r)
            self.log("Rekaman selesai & tersimpan.")
            self.notify("Rekaman tersimpan ✓")
        fin() if wait else threading.Thread(target=fin, daemon=True).start()

    def hotkeys(self):  # F9 = rekam/stop, F10 = screenshot, Ctrl+Shift+R = rekam/stop (cadangan)
        def loop():
            try:
                u = ctypes.windll.user32
                ok = u.RegisterHotKey(None, 1, 0, 0x78)
                u.RegisterHotKey(None, 2, 0, 0x79)
                u.RegisterHotKey(None, 3, 0x0002 | 0x0004, 0x52)
                if not ok:
                    self.q.put("F9 dipakai aplikasi lain - pakai Ctrl+Shift+R untuk rekam/stop")
                msg = ctypes.wintypes.MSG()
                while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == 0x0312:
                        self.q.put(f"__hk{msg.wParam}")
            except Exception as e:
                self.q.put(f"Hotkey gagal: {e}")
        threading.Thread(target=loop, daemon=True).start()

    def refresh_ui(self):
        if self.rec and self.rec.poll() is not None:
            self.rec = None
            self.notify("Rekaman berhenti")
        rec_on, busy = bool(self.rec), bool(self.rec_busy)
        el = int(time.time() - self.rec_t0) if rec_on else 0
        clock = f"{el // 60:02d}:{el % 60:02d}"
        try:
            if self.rec_btn is not None and self.rec_btn.winfo_exists():
                self.rec_btn.config(text=L("■ Stop Rekam" if rec_on else
                                           "✕ Batal" if busy else "● Mulai Rekam"))
        except Exception:
            pass
        try:
            if self.rec_clock is not None and self.rec_clock.winfo_exists():
                self.rec_clock.config(text=(f"● MEREKAM {clock}   -   klik ■ Stop Rekam / F9 / Ctrl+Shift+R"
                                            if rec_on else
                                            "… menyiapkan ffmpeg (klik Batal untuk membatalkan)"
                                            if busy else ""))
        except Exception:
            pass
        # jaga disk: berhenti otomatis kalau sisa < 1 GB
        if rec_on and time.time() - self._disk_t > 10:
            self._disk_t = time.time()
            try:
                if shutil.disk_usage(PICS).free < (1 << 30):
                    self.log("Disk hampir penuh (<1 GB), rekaman dihentikan otomatis.")
                    self.stop_rec()
            except Exception:
                pass
        # overlay rekam otomatis muncul saat mulai (termasuk saat menyiapkan), hilang saat stop
        act = rec_on or busy
        if act and not self.rec_prev and not self.rov:
            self.show_rov(auto=True)
        elif not act and self.rec_prev and self.rov and self.rov_auto:
            self.hide_rov()
        self.rec_prev = act
        blink = int(time.time() * 2) % 2
        if self.rov:
            try:
                if rec_on:
                    self.ov_rec.config(text=f"■ STOP {clock}", bg="#e01b24" if blink else "#8a1016")
                elif busy:
                    self.ov_rec.config(text=L("✕ Batal"), bg="#8a1016")
                else:
                    self.ov_rec.config(text="● REC  F9", bg="#26262c")
                msg, until = self.toast
                self.ov_toast.config(text=msg if time.time() < until else "")
            except Exception:
                pass
        if self.ov:
            try:
                st, f = self.stats, self.stats.fps_now()
                tmp = lambda v: f"{v:.0f}°C" if v else "--"
                if self.ov_rows:
                    self.ov_rows["cpu"].config(text=f"{st.cpu:.0f}%  {tmp(st.cpu_t)}")
                    self.ov_rows["gpu"].config(text=f"{st.gpu:.0f}%  {tmp(st.gpu_t)}")
                    self.ov_rows["ram"].config(text=f"{st.ram:.0f}%")
                    self.ov_rows["fps"].config(text=f"{f}" if f else "--")
                else:
                    self.ov_fps.config(text=f"{f} FPS" if f else "-- FPS")
                    self.ov_temp.config(text=f"CPU {tmp(st.cpu_t)}   GPU {tmp(st.gpu_t)}")
                self.ov_msg.config(text="" if f else L(st.fps_msg))
            except Exception:
                pass

''')

# ---------------------------------------------------------------- 5. halaman Overlay: transparansi
rep('''        self.menu(r, self.ov_modev, "Cincin", "Teks kecil").pack(side="left")
        self.ov_modev.trace_add("write", lambda *a: self.set_ov_mode(self.ov_modev.get()))''',
    '''        self.menu(r, self.ov_modev, "Cincin", "Teks kecil").pack(side="left")
        self.ov_modev.trace_add("write", lambda *a: self.set_ov_mode(self.ov_modev.get()))
        r = tk.Frame(c, bg=CARD)
        r.pack(fill="x", pady=(0, 8))
        self.lab(r, "Latar", width=8, anchor="w").pack(side="left")
        self.ov_bgv = tk.StringVar(value="Tembus" if self.ov_is_clear() else "Solid")
        self.menu(r, self.ov_bgv, "Tembus", "Solid").pack(side="left")
        self.ov_bgv.trace_add("write", lambda *a: self.set_ov_bg(self.ov_bgv.get()))
        r = tk.Frame(c, bg=CARD)
        r.pack(fill="x", pady=(0, 8))
        self.lab(r, "Transparansi", width=12, anchor="w").pack(side="left")
        av = tk.IntVar(value=int(self.ov_alpha_eff() * 100))
        sc = self.scale(r, av, from_=20, to=100, orient="horizontal", length=300, showvalue=True,
                        command=lambda v: self.set_ov_alpha(int(float(v)) / 100))
        sc.pack(side="left", padx=8)
        self.lab(r, "100 = jelas, makin kecil makin tembus (cincin & teks)", dim=True).pack(side="left")''')

# ---------------------------------------------------------------- 6. mode / latar / alpha overlay
block("    def set_ov_mode(self, m):", "    def fill_ov(self, f, s):", '''    def ov_is_clear(self):  # latar tembus? (default: tembus untuk Cincin, solid untuk Teks kecil)
        return self.ov_clear if self.ov_clear is not None else self.ov_mode == "Cincin"

    def ov_alpha_eff(self):
        return self.ov_alpha if self.ov_alpha is not None else (1.0 if self.ov_is_clear() else .92)

    def save_ov_opts(self):
        try:
            st = core.load_state()
            st["ov_alpha"], st["ov_clear"] = self.ov_alpha, self.ov_clear
            core.save_state(st)
        except Exception:
            pass

    def reopen_ov(self):  # transparan vs solid beda jendela -> buka ulang di posisi yang sama
        if self.ov:
            x, y = self.ov.pos()
            self.ov.destroy()
            self.ov = None
            self.root.after(1, lambda: self.show_ov(x, y))

    def set_ov_mode(self, m):
        self.ov_mode = m
        self.reopen_ov()

    def set_ov_bg(self, v):
        self.ov_clear = (v == "Tembus")
        self.save_ov_opts()
        self.reopen_ov()

    def set_ov_alpha(self, a):
        self.ov_alpha = a
        if self.ov:
            self.ov.set_alpha(a)
        self.save_ov_opts()

    # -- overlay statistik
    def toggle_ov(self):
        if self.ov:
            self.ov.destroy()
            self.ov = None
            self.set_btn(self.ov_btn, "Nyalakan Overlay Statistik")
            return
        self.stats.start_fps()
        self.show_ov()
        self.set_btn(self.ov_btn, "Matikan Overlay Statistik")

    def show_ov(self, x=30, y=30):
        self.ov = FloatWin(self, "ov", self.fill_ov, x, y, self.scales["ov"],
                           self.ov_is_clear(), self.ov_alpha_eff())

''')

# ---------------------------------------------------------------- 7. poll: tidak boleh mati
a = s.index("    def poll(self):")
b = s.index("\n\ndef ensure_admin", a)
s = s[:a] + '''    def poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m in ("__hk1", "__hk3"):
                    self.toggle_rec()
                elif m == "__hk2":
                    self.shot()
                elif self.logbox:
                    self.logbox.insert("end", m + "\\n")
                    self.logbox.see("end")
                elif self.msg_lbl:
                    self.msg_lbl.config(text=m)
        except queue.Empty:
            pass
        except Exception as e:
            self.logbox_err(f"UI: {e}")
        try:
            self.refresh_ui()
        except Exception as e:
            self.logbox_err(f"UI: {e}")
        try:
            if self.cur_page == "Dashboard":
                self.gpu_lbl.config(text=f"CPU: {L(self.stats.cpu_name)}   |   "
                                         f"GPU: {L(self.stats.gpu_name)}")
        except Exception:
            pass
        self.root.after(200, self.poll)  # loop ini harus selalu lanjut

    def logbox_err(self, m):  # catat error UI sekali saja, jangan spam
        if getattr(self, "_last_err", None) != m:
            self._last_err = m
            try:
                self.log(m)
            except Exception:
                pass''' + s[b:]

open(P, "w", encoding="utf-8").write(s)
print("OK: tombol STOP rekam + transparansi overlay terpasang")
