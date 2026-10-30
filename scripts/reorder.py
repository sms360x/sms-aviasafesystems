p='public/dashboard/safety-manager.html'
s=open(p,encoding='utf-8').read()
# extract S6+S7 blocks
import re
s6_start=s.index("        <!-- S6 — Needs Your Attention -->")
s7_end=s.index("        </div>\n", s.index("S7 — My Tasks & Approvals", s6_start))+len("        </div>\n")
block=s[s6_start:s7_end]
s=s[:s6_start]+s[s7_end:]
# insert after KPI closing (line after s1-body div)
anchor="        </div>\n\n\n        <!-- Reports Page -->"
insert=block+"\n\n"+anchor
s=s.replace(anchor, insert, 1)
open(p,'w',encoding='utf-8').write(s)
print("done")