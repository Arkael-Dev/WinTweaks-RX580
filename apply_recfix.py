# -*- coding: utf-8 -*-
"""Fix: tombol/overlay STOP rekam tidak muncul & F9 mati (loop UI mati kena error)."""
import sys

P = "wintweaks.py"
s = open(P, encoding="utf-8").read()


def rep(old, new):
    global s
    if s.count(old) != 1:
        sys.exit(f"GAGAL ({s.count(old)}x ketemu):\n" + old[:90])
    s = s.replace(old, new)


# 1. loop UI tidak boleh mati karena satu error
rep('''        except (queue.Empty, tk.TclError):
            pass
        self.refresh_ui()
        try:
            if self.cur_page == "Dashboard":''',
    '''        except (queue.Empty, tk.TclError):
            pass
        except Exception as e:
            self.logbox_err(f"UI: {e}")
        try:
            self.refresh_ui()
        except Exception as e:
            self.logbox_err(f"UI: {e}")
        try:
            if self.cur_page == "Dashboard":''')

rep('''        except tk.TclError:
            pass
        self.root.after(200, self.poll)''',
    '''        except Exception:
            pass
        self.root.after(200, self.poll)

    def logbox_err(self, m):  # catat error UI sekali saja, jangan spam
        if getattr(self, "_last_err", None) != m:
            self._last_err = m
            try:
                self.log(m)
            except Exception:
                pass''')

# 2. tombol utama: langsung kelihatan "MEMULAI" saat ffmpeg disiapkan
rep('''self.rec_btn.config(text=L("■ Stop Rekam" if rec_on else "● Mulai Rekam"))''',
    '''self.rec_btn.config(text=L("■ Stop Rekam" if rec_on else
                                           "… MEMULAI" if self.rec_busy else "● Mulai Rekam"))''')

# 3. overlay STOP muncul langsung saat mulai (tidak menunggu ffmpeg siap)
rep('''        if rec_on and not self.rec_prev and not self.rov:
            self.show_rov(auto=True)
        elif not rec_on and self.rec_prev and self.rov and self.rov_auto:
            self.hide_rov()
        self.rec_prev = rec_on''',
    '''        act = rec_on or self.rec_busy
        if act and not self.rec_prev and not self.rov:
            self.show_rov(auto=True)
        elif not act and self.rec_prev and self.rov and self.rov_auto:
            self.hide_rov()
        self.rec_prev = act''')

# 4. stop: pastikan proses benar-benar berhenti
rep('''            except Exception:
                r.kill()
            self.log("Rekaman selesai & tersimpan.")''',
    '''            except Exception:
                pass
            try:
                if r.poll() is None:
                    r.kill()
            except Exception:
                pass
            self.log("Rekaman selesai & tersimpan.")''')

open(P, "w", encoding="utf-8").write(s)
print("OK: fix tombol STOP rekam terpasang")
