p='public/dashboard/safety-manager.html'
s=open(p,encoding='utf-8').read()
start=s.index("        <!-- S6 — Needs Your Attention -->")
end=s.index("        </div>\n", s.index("s6-attention", start))+len("        </div>\n")
block=s[start:end]
s=s[:start]+s[end:]
anchor="        <div class=\"exec-bento\""
# insert before bento, after page title? Just before exec-bento
insert=block+"\n\n"
s=s.replace(anchor, insert+anchor,1)
open(p,'w',encoding='utf-8').write(s)
print("done")