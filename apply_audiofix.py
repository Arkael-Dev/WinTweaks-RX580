# -*- coding: utf-8 -*-
"""Fix audio rekaman layar (sebelumnya video tanpa suara).

gdigrab hanya menangkap gambar. Sekarang suara direkam terpisah lewat WASAPI
(pyaudiowpatch): suara sistem/game (loopback) dan/atau mikrofon, lalu
digabung ke video dengan ffmpeg saat STOP.

Halaman Rekam dapat pilihan: Audio (Sistem / Sistem + Mic / Mic / Tanpa audio),
perangkat output, perangkat mikrofon, dan tombol Segarkan. Pilihan tersimpan.
Bagian lain tidak diubah. Juga menambah pyaudiowpatch ke build.yml.
"""
import os
import sys

P = "wintweaks.py"
Y = os.path.join(".github", "workflows", "build.yml")
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


if "class AudioRec" in s:
    sys.exit("Sudah pernah dipasang, tidak ada yang diubah.")

# ---------------------------------------------------------------- 1. import
rep("import time, urllib.request, webbrowser, zipfile",
    "import time, urllib.request, wave, webbrowser, zipfile")

# ---------------------------------------------------------------- 2. kelas perekam audio
AUDIO = r'''class AudioRec:
    """Rekam suara sistem (WASAPI loopback) dan/atau mikrofon ke WAV lewat pyaudiowpatch.
    Hening tetap diisi (loopback tidak mengirim data saat tidak ada suara), jadi durasi
    audio selalu sama dengan video."""

    @staticmethod
    def devices():
        """-> (daftar nama output, daftar nama mikrofon)."""
        import pyaudiowpatch as pa
        p = pa.PyAudio()
        try:
            outs = [d["name"] for d in p.get_loopback_device_info_generator()]
            host = p.get_host_api_info_by_type(pa.paWASAPI)["index"]
            mics = []
            for i in range(p.get_device_count()):
                d = p.get_device_info_by_index(i)
                if d["hostApi"] == host and d["maxInputChannels"] > 0 and not d.get("isLoopbackDevice"):
                    mics.append(d["name"])
            return list(dict.fromkeys(outs)), list(dict.fromkeys(mics))
        finally:
            p.terminate()

    def __init__(self, folder, tag, use_sys, use_mic, sys_name="Default", mic_name="Default"):
        import pyaudiowpatch as pa
        self.pa, self.p, self.srcs, self.err = pa, pa.PyAudio(), [], []
        try:
            host = self.p.get_host_api_info_by_type(pa.paWASAPI)
            if use_sys:
                self._add(self._find_sys(host, sys_name), os.path.join(folder, f"{tag}.sys.wav"), "sistem")
            if use_mic:
                self._add(self._find_mic(host, mic_name), os.path.join(folder, f"{tag}.mic.wav"), "mikrofon")
        except Exception:
            self.abort()
            raise
        if not self.srcs:
            self.abort()
            raise RuntimeError("; ".join(self.err) or "tidak ada perangkat audio")

    def _find_sys(self, host, name):
        loops = list(self.p.get_loopback_device_info_generator())
        if name and name != "Default":
            for d in loops:
                if d["name"] == name:
                    return d
        spk = self.p.get_device_info_by_index(host["defaultOutputDevice"])
        for d in loops:  # loopback milik speaker default
            if spk["name"] in d["name"]:
                return d
        if loops:
            return loops[0]
        raise RuntimeError("perangkat output tidak ditemukan")

    def _find_mic(self, host, name):
        if name and name != "Default":
            for i in range(self.p.get_device_count()):
                d = self.p.get_device_info_by_index(i)
                if d["hostApi"] == host["index"] and d["name"] == name and d["maxInputChannels"] > 0:
                    return d
        return self.p.get_device_info_by_index(host["defaultInputDevice"])

    def _add(self, dev, path, label):
        try:
            self.srcs.append(_AudioSrc(self.pa, self.p, dev, path))
        except Exception as e:  # satu sumber gagal -> sumber lain tetap jalan
            self.err.append(f"{label}: {e}")

    def stop(self):
        """Hentikan & tutup file. -> daftar path WAV."""
        end, paths = time.time(), []
        for sr in self.srcs:
            try:
                sr.close(end)
                paths.append(sr.path)
            except Exception:
                pass
        try:
            self.p.terminate()
        except Exception:
            pass
        return paths

    def abort(self):  # batal: hapus semua file
        for pth in self.stop():
            try:
                os.remove(pth)
            except OSError:
                pass


class _AudioSrc:
    def __init__(self, pa, p, dev, path):
        self.pa, self.path = pa, path
        self.rate, self.ch = int(dev["defaultSampleRate"]), max(1, int(dev["maxInputChannels"]))
        self.w = wave.open(path, "wb")
        self.w.setnchannels(self.ch)
        self.w.setsampwidth(2)
        self.w.setframerate(self.rate)
        self.frames, self.lock, self.open = 0, threading.Lock(), True
        self.t0 = time.time()
        try:
            self.stream = p.open(format=pa.paInt16, channels=self.ch, rate=self.rate, input=True,
                                 input_device_index=dev["index"], frames_per_buffer=1024,
                                 stream_callback=self._cb)
        except Exception:
            self.w.close()
            raise

    def _pad(self, n):
        if n > 0:
            self.w.writeframes(bytes(n * 2 * self.ch))
            self.frames += n

    def _cb(self, data, frame_count, time_info, status):
        try:
            n = len(data) // (2 * self.ch)
            with self.lock:
                if self.open:
                    gap = int((time.time() - self.t0) * self.rate) - self.frames - n
                    if gap > self.rate // 20:  # > 50 ms tanpa data = hening
                        self._pad(gap)
                    self.w.writeframes(data)
                    self.frames += n
        except Exception:
            pass
        return (None, self.pa.paContinue)

    def close(self, end):
        try:
            self.stream.stop_stream()
            self.stream.close()
        except Exception:
            pass
        with self.lock:
            self.open = False
            self._pad(int((end - self.t0) * self.rate) - self.frames)
            self.w.close()


'''
rep("class Btn(tk.Label):", AUDIO + "class Btn(tk.Label):")

# ---------------------------------------------------------------- 3. state awal
rep('''        self.res_val, self.fps_val = get_current_resolution(), "30"''',
    '''        self.res_val, self.fps_val = get_current_resolution(), "30"
        self.arec, self.rec_out, self.rec_vid = None, None, None
        self.aud_val, self.aud_sys, self.aud_mic = (st0.get("rec_audio") or "Sistem",
                                                    st0.get("rec_sys") or "Default",
                                                    st0.get("rec_mic") or "Default")
        self.aud_devs = ([], [])''')

# ---------------------------------------------------------------- 4. UI halaman Rekam
rep('''        self.lab(c, "Encoder otomatis: AMD AMF (ringan untuk CPU) kalau GPU AMD, selain itu x264. "''',
    '''        self.audv, self.sysv, self.micv = (tk.StringVar(value=self.aud_val),
                                           tk.StringVar(value=self.aud_sys),
                                           tk.StringVar(value=self.aud_mic))
        for v in (self.audv, self.sysv, self.micv):
            v.trace_add("write", lambda *a: self.set_aud())
        r = tk.Frame(c, bg=CARD)
        r.pack(anchor="w", pady=(10, 0))
        self.lab(r, "Audio", width=12, anchor="w").pack(side="left")
        self.menu(r, self.audv, "Sistem", "Sistem + Mic", "Mic", "Tanpa audio").pack(side="left")
        Btn(r, "Segarkan", self.scan_audio, self, False).pack(side="left", padx=12)
        r = tk.Frame(c, bg=CARD)
        r.pack(anchor="w", pady=(6, 0))
        self.lab(r, "Output suara", width=12, anchor="w").pack(side="left")
        self.m_sys = self.menu(r, self.sysv, "Default")
        self.m_sys.config(width=34, anchor="w")
        self.m_sys.pack(side="left")
        r = tk.Frame(c, bg=CARD)
        r.pack(anchor="w", pady=(6, 0))
        self.lab(r, "Mikrofon", width=12, anchor="w").pack(side="left")
        self.m_mic = self.menu(r, self.micv, "Default")
        self.m_mic.config(width=34, anchor="w")
        self.m_mic.pack(side="left")
        self.scan_audio()
        self.lab(c, "Sistem = suara game/aplikasi. Mic = suara kamu. Audio direkam terpisah lalu "
                    "digabung otomatis saat Stop (butuh beberapa detik).",
                 dim=True, wraplength=700).pack(anchor="w", pady=(8, 0))
        self.lab(c, "Encoder otomatis: AMD AMF (ringan untuk CPU) kalau GPU AMD, selain itu x264. "''')

# ---------------------------------------------------------------- 5. rekam / stop / audio
block("    def toggle_rec(self):", "    def hotkeys(self):", r'''    def set_aud(self):  # pilihan audio disimpan
        self.aud_val, self.aud_sys, self.aud_mic = self.audv.get(), self.sysv.get(), self.micv.get()
        try:
            st = core.load_state()
            st["rec_audio"], st["rec_sys"], st["rec_mic"] = self.aud_val, self.aud_sys, self.aud_mic
            core.save_state(st)
        except Exception:
            pass

    def scan_audio(self):  # isi daftar perangkat audio
        try:
            self.aud_devs = AudioRec.devices()
            err = None
        except Exception as e:
            self.aud_devs, err = ([], []), e
        for m, var, devs in ((self.m_sys, self.sysv, self.aud_devs[0]),
                             (self.m_mic, self.micv, self.aud_devs[1])):
            try:
                mm = m["menu"]
                mm.delete(0, "end")
                for o in ["Default"] + list(devs):
                    mm.add_command(label=o, command=lambda o=o, var=var: var.set(o))
                if var.get() not in ["Default"] + list(devs):
                    var.set("Default")
            except Exception:
                pass
        if err:
            self.log(f"Modul audio tidak tersedia ({err}) - rekam video saja.")

    def toggle_rec(self):
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
                tag = time.strftime("rekam_%Y%m%d_%H%M%S")
                out = os.path.join(PICS, tag + ".mp4")
                use_sys = self.aud_val in ("Sistem", "Sistem + Mic")
                use_mic = self.aud_val in ("Mic", "Sistem + Mic")
                want_a = use_sys or use_mic
                vid = os.path.join(PICS, tag + ".video.mp4") if want_a else out  # audio digabung saat stop
                W, H = self.res_val
                x264 = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "24"]
                amf = ["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "24", "-qp_p", "26"]
                for enc in ([amf, x264] if self.stats.amd else [x264]):
                    p = subprocess.Popen(
                        [ff, "-y", "-f", "gdigrab", "-framerate", self.fps_val, "-i", "desktop",
                         "-vf", f"scale={W}:{H}", *enc, "-pix_fmt", "yuv420p", vid],
                        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
                    arec, t0 = None, time.time()
                    while time.time() - t0 < 1.5 and p.poll() is None:
                        # audio mulai begitu video mulai menulis, supaya sinkron
                        if want_a and arec is None and os.path.isfile(vid) and os.path.getsize(vid) > 0:
                            try:
                                arec = AudioRec(PICS, tag, use_sys, use_mic, self.aud_sys, self.aud_mic)
                                for e in arec.err:
                                    self.log(f"Audio {e}")
                            except Exception as e:
                                self.log(f"Audio gagal ({e}) - rekam video saja.")
                                want_a = False
                        time.sleep(0.05)
                    if p.poll() is None:  # jalan; kalau AMF gagal otomatis coba x264
                        if want_a and arec is None:  # video lambat menulis file -> mulai audio sekarang
                            try:
                                arec = AudioRec(PICS, tag, use_sys, use_mic, self.aud_sys, self.aud_mic)
                            except Exception as e:
                                self.log(f"Audio gagal ({e}) - rekam video saja.")
                                want_a = False
                        if self.rec_cancel:  # dibatalkan selagi ffmpeg start
                            if arec:
                                arec.abort()
                            self._quit_proc(p)
                            return
                        self.arec, self.rec_out, self.rec_vid = arec, out, vid
                        self.rec, self.rec_t0 = p, time.time()
                        self.log(L("Merekam -> {0}").format(out))
                        return
                    if arec:  # encoder mati (mis. AMF gagal) -> buang audio, coba encoder lain
                        arec.abort()
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

    def merge_audio(self, vid, wavs, out):
        """Gabung video + WAV jadi MP4 ber-suara. Gagal -> video tetap disimpan tanpa suara."""
        good = [w for w in wavs if os.path.isfile(w) and os.path.getsize(w) > 1024]
        if vid == out:
            return
        if not os.path.isfile(vid):
            self.log("Rekaman video tidak ditemukan.")
            return
        ok = False
        try:
            if good:
                ff = self.ffmpeg() or self.get_ffmpeg()
                cmd = [ff, "-y", "-i", vid]
                for w in good:
                    cmd += ["-i", w]
                norm = "aresample=48000,aformat=channel_layouts=stereo"
                if len(good) == 1:
                    fc = f"[1:a]{norm}[a]"
                else:
                    fc = (f"[1:a]{norm}[a1];[2:a]{norm}[a2];"
                          "[a1][a2]amix=inputs=2:duration=longest:dropout_transition=0,"
                          "volume=2,alimiter=limit=0.95[a]")
                cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out]
                r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                   creationflags=NO_WINDOW, timeout=900)
                ok = r.returncode == 0 and os.path.isfile(out) and os.path.getsize(out) > 0
                if not ok:
                    tail = r.stderr.decode("utf-8", "ignore").strip().splitlines()[-2:]
                    self.log("Gabung audio gagal: " + " | ".join(tail))
        except Exception as e:
            self.log(f"Gabung audio gagal: {e}")
        if ok:
            try:
                os.remove(vid)
            except OSError:
                pass
        else:  # jangan sampai rekaman hilang: simpan video apa adanya
            try:
                os.replace(vid, out)
            except OSError:
                pass
            self.log("Rekaman disimpan tanpa suara.")
        for w in wavs:
            try:
                os.remove(w)
            except OSError:
                pass

    def stop_rec(self, wait=False):
        r, self.rec = self.rec, None
        a, self.arec = self.arec, None
        out, vid = self.rec_out, self.rec_vid
        if not r:
            return

        def fin():
            wavs = []
            try:
                wavs = a.stop() if a else []
            except Exception as e:
                self.log(f"Audio berhenti dengan error: {e}")
            self._quit_proc(r)
            if out and vid and vid != out:  # video sementara -> jadi file akhir (dengan/tanpa audio)
                if wavs:
                    self.notify("Menggabung audio...")
                self.merge_audio(vid, wavs, out)
            self.log("Rekaman selesai & tersimpan.")
            self.notify("Rekaman tersimpan ✓")
        fin() if wait else threading.Thread(target=fin, daemon=True).start()

''')

# ---------------------------------------------------------------- 6. video mati sendiri -> audio ikut dihentikan
rep('''        if self.rec and self.rec.poll() is not None:
            self.rec = None
            self.notify("Rekaman berhenti")''',
    '''        if self.rec and self.rec.poll() is not None:
            self.notify("Rekaman berhenti")
            self.stop_rec()  # tutup audio & gabungkan yang sudah terekam''')

# ---------------------------------------------------------------- 7. terjemahan
rep('''    "Rekaman tersimpan ✓": "Recording saved ✓", "Rekaman berhenti": "Recording stopped",''',
    '''    "Rekaman tersimpan ✓": "Recording saved ✓", "Rekaman berhenti": "Recording stopped",
    "Audio": "Audio", "Output suara": "Sound output", "Mikrofon": "Microphone",
    "Segarkan": "Refresh", "Menggabung audio...": "Merging audio...",
    "Sistem = suara game/aplikasi. Mic = suara kamu. Audio direkam terpisah lalu "
    "digabung otomatis saat Stop (butuh beberapa detik).":
        "System = game/app sound. Mic = your voice. Audio is recorded separately and "
        "merged automatically on Stop (takes a few seconds).",''')

open(P, "w", encoding="utf-8").write(s)

# ---------------------------------------------------------------- 8. build.yml: pasang pyaudiowpatch
if os.path.isfile(Y):
    y = open(Y, encoding="utf-8").read()
    if "pyaudiowpatch" not in y:
        a = "pip install pyinstaller psutil pillow"
        b = "          --add-data \"assets;assets\"\n"
        if y.count(a) != 1 or y.count(b) != 1:
            sys.exit("GAGAL: build.yml tidak cocok, tidak diubah (wintweaks.py sudah terubah).")
        y = y.replace(a, a + " pyaudiowpatch")
        y = y.replace(b, b + "          --hidden-import pyaudiowpatch\n")
        open(Y, "w", encoding="utf-8").write(y)
print("OK: audio rekaman (sistem + mic) terpasang")
