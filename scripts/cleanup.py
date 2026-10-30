p='public/dashboard/safety-manager.html'
s=open(p,encoding='utf-8').read()
s=s.replace("""        <!-- S2 — 5x5 Risk Matrix -->
        <div class="exec-bento-half exec-card" data-section="s2">
            <div class="exec-card-header">
                <h2 class="exec-card-title">5&times;5 Risk Matrix</h2>
                <a href="#" class="exec-card-link">View all</a>
            </div>
            <div class="exec-risk-matrix" id="s2-matrix"></div>
            <div class="exec-chart-caption" id="s2-caption">&mdash;</div>
        </div>

""","")
s=s.replace("""        <!-- S5 — Corrective Actions donut -->
        <div class="exec-bento-third exec-card" data-section="s5">
            <div class="exec-card-header">
                <h2 class="exec-card-title">Corrective Actions</h2>
                <a href="#" class="exec-card-link">View all</a>
            </div>
            <div class="exec-donut-wrap" id="s5-body">
                <div style="position: relative; width: 220px; height: 220px;">
                    <canvas id="s5-donut-canvas" class="exec-donut-canvas"></canvas>
                    <div class="exec-donut-center-label" id="s5-donut-center">&mdash;</div>
                </div>
                <div class="exec-donut-legend" id="s5-donut-legend"></div>
            </div>
        </div>

""","")
start=s.index("        <!-- S8 — SPIs with 12-month trends -->")
end=s.index("        </div>\n", s.index("Hazard Register", start))+len("        </div>\n")
s=s[:start]+s[end:]
open(p,'w',encoding='utf-8').write(s)
print("done")