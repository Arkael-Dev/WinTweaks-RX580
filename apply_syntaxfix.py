# -*- coding: utf-8 -*-
"""Fix build gagal: IndentationError di App.poll (blok animasi judul Dashboard
tidak masuk ke dalam `if self.cur_page == "Dashboard":`). Hanya merapikan indentasi."""
import sys

P = "wintweaks.py"
s = open(P, encoding="utf-8").read()
lines = s.split("\n")

try:
    i = next(k for k, l in enumerate(lines)
             if l == '            if self.cur_page == "Dashboard":'
             and lines[k + 1].startswith("            full_txt = "))
except StopIteration:
    sys.exit("Tidak ada yang perlu diperbaiki (blok poll sudah benar atau berbeda).")

j = i + 1
while not lines[j].startswith("        self.root.after(200, self.poll)"):
    j += 1
# blok = baris i+1 .. sebelum `        except Exception:` penutup try di indent 8
k = j - 1
while lines[k].strip() == "":
    k -= 1
assert lines[k] == "            pass" and lines[k - 1] == "        except Exception:", "struktur tak dikenal"
end = k - 1  # baris `except Exception:` milik try luar
for n in range(i + 1, end):
    if lines[n].strip():
        lines[n] = "    " + lines[n]
open(P, "w", encoding="utf-8").write("\n".join(lines))
print("OK: indentasi poll diperbaiki")
