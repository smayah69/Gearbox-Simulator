import cairo, math, subprocess, sys

W, H, FPS, TOTAL = 1920, 1080, 30, 57.0
R1, R2 = 41 / 12, 38 / 21          # 1st ~3.42, 2nd ~1.81
K = 0.6 / 3000                      # visual rev/s per rpm
G = 80                              # close-up pitch per visual rev

def ss(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)

def lerp(a, b, u): return a + (b - a) * u

def kf(t, pts, smooth=True):
    if t <= pts[0][0]: return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0) if t1 > t0 else 1
            return v0 + (v1 - v0) * (ss(u) if smooth else u)
    return pts[-1][1]

def lin(t, t0, t1, v0, v1):
    u = max(0, min(1, (t - t0) / (t1 - t0))); return v0 + (v1 - v0) * u

# ---------------- timeline / physics ----------------
S1 = dict(d=-1, ts=13.0, tst=14.2, tp=14.8, tb=15.6, te=19.4, ta=20.2, tg=21.0)
S2 = dict(d=+1, ts=33.2, tst=34.0, tp=34.5, tb=35.2, te=38.8, ta=39.5, tg=40.3)
D1 = (31.3, 33.0)
W2 = 860.0
WOUT1 = 3000 / R1

def eng(t):
    return kf(t, [(0, 850), (21, 850), (24, 1300), (30, 3000), (30.6, 3000), (40.3, 1700),
                  (42.5, W2 * R2), (50, 3000), (60, 3000)])

def clutch(t):
    return kf(t, [(0, 0), (10, 0), (12, 1), (21.3, 1), (24, 0), (30.2, 0), (31, 1), (40.6, 1), (42.5, 0), (60, 0)])

def throttle(t):
    if 21 <= t < 30.4: return 0.35 + 0.4 * ss((t - 21) / 2)
    if 42.5 <= t < 50: return 0.6
    return 0.0

def w_out(t):
    if t < 21: return 0.0
    if t < 30: return w_in(t) / R1
    if t < 38.8: return lin(t, 30, 38.8, WOUT1, W2)
    if t < 42.5: return W2
    return w_in(t) / R2

def w_in(t):
    if t < 12: return 850.0
    if t < 15.6: return lin(t, 12, 15.6, 850, 600)
    if t < 19.4: return lin(t, 15.6, 19.4, 600, 0)
    if t < 21: return 0.0
    if t < 24: return eng(t) * ss((t - 21) / 3)
    if t < 30: return eng(t)
    if t < 32: return w_out(t) * R1
    if t < 35.2: return lin(t, 32, 35.2, w_out(32) * R1, 2900)
    if t < 38.8: return lin(t, 35.2, 38.8, 2900, W2 * R2)
    if t < 42.5: return W2 * R2
    return eng(t)

def vf(t):
    a = 1 - 0.65 * ss((t - 12.6) / 0.6) * (1 - ss((t - 21.0) / 0.6))
    b = 1 - 0.65 * ss((t - 30.8) / 0.6) * (1 - ss((t - 40.4) / 0.6))
    return min(a, b)

def slowmo(t): return (12.9 < t < 21.2) or (31.1 < t < 40.6)

# close-up geometry (px)
P, CH, TW = 70, 14, 0.44
HALF = TW / 2
SL = 125                       # sleeve half length
def contact_xs(yc, rx): return rx + yc / HALF * CH - SL
XB = contact_xs(0.25, 156)
XA = contact_xs(TW, 156)

def event_state(E, t):
    """returns a(abs sleeve travel), ring_off, ring_shift, friction, phase"""
    if t < E['ts']: return 0, 0.5, 0, 0, None
    if t < E['tst']:
        return 12 * ss((t - E['ts']) / (E['tst'] - E['ts'])), 0.5, 0, 0, 'move'
    if t < E['tp']:
        u = ss((t - E['tst']) / (E['tp'] - E['tst']))
        return 12 + 6 * u, 0.5, 6 * u, 0.35 * u, 'pre'
    if t < E['tb']:
        u = ss((t - E['tp']) / (E['tb'] - E['tp']))
        off = 0.5 + 0.25 * ss((t - E['tp']) / 0.3)
        return 18 + (XB - 18) * u, off, 6, 0.35 + 0.65 * u, 'index'
    if t < E['te']:
        return XB, 0.75, 6, 1.0, 'sync'
    if t < E['ta']:
        u = ss((t - E['te']) / (E['ta'] - E['te']))
        yc = 0.25 + (TW - 0.25) * u
        return contact_xs(yc, 156), 1 - yc, 6, 1 - u, 'align'
    if t < E['tg']:
        u = ss((t - E['ta']) / (E['tg'] - E['ta']))
        off = 1 - (TW + (0.5 - TW) * ss(min(1, u / 0.3)))
        return XA + (137 - XA) * u, off, 6, 0, 'slide'
    return 137, 0.5, 6, 0, 'engaged'

def sync_state(t):
    st = dict(xs=0, r1=0.5, r2=0.5, sh1=0, sh2=0, f1=0, f2=0, ph=None, side=0)
    if t < D1[0]:
        a, off, sh, f, ph = event_state(S1, t)
        st.update(xs=-a, r1=off, sh1=sh, f1=f, ph=ph, side=-1 if ph else 0)
    elif t < D1[1]:
        u = ss((t - D1[0]) / (D1[1] - D1[0]))
        st.update(xs=-137 * (1 - u), sh1=6 * (1 - u), ph='out', side=-1)
    else:
        a, off, sh, f, ph = event_state(S2, t)
        st.update(xs=a, r2=off, sh2=sh, f2=f, ph=ph, side=1 if ph else 0)
    return st

def eng_frac(xs, d):  # dog engagement fraction for side d
    v = xs * d
    return max(0.0, min(1.0, (v - 90) / 47))

# pre-integrate angles (visual revs)
NF = int(TOTAL * FPS)
ANG = []
a_in = a_out = a_e = 0.0
for i in range(NF):
    t = i / FPS
    ANG.append((a_in, a_out, a_e))
    dt = 1 / FPS
    v = vf(t)
    a_in += w_in(t) / 60 * 0 + w_in(t) * K * v * dt
    a_out += w_out(t) * K * v * dt
    a_e += eng(t) * K * v * dt

def ang_at(t):
    return ANG[min(NF - 1, int(round(t * FPS)))]

def rel_g(i, t):
    a_in, a_out, _ = ang_at(t)
    return (a_in / (R1 if i == 1 else R2) - a_out) * G

C1 = 0.5 - rel_g(1, S1['te'])
C2 = 0.5 - rel_g(2, S2['te'])

# ---------------- drawing helpers ----------------
BG = (0.06, 0.08, 0.11)
PANEL = (0.09, 0.12, 0.16)
BLUE = (0.42, 0.62, 0.86)
GREEN = (0.36, 0.76, 0.58)
GOLD = (0.88, 0.70, 0.33)
BRASS = (0.80, 0.56, 0.22)
GREY = (0.55, 0.57, 0.6)
ORANGE = (1.0, 0.55, 0.12)
WHITE = (0.93, 0.95, 0.97)
DIM = (0.62, 0.68, 0.75)
FONT = "DejaVu Sans"

def mix(a, b, u): return tuple(a[i] + (b[i] - a[i]) * u for i in range(3))

def text(c, s, x, y, size=18, col=WHITE, bold=False, align='l', alpha=1.0):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL,
                       cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)
    ext = c.text_extents(s)
    if align == 'c': x -= ext.x_advance / 2
    elif align == 'r': x -= ext.x_advance
    c.set_source_rgba(*col, alpha)
    c.move_to(x, y); c.show_text(s)
    return ext.x_advance

def wrap(c, s, x, y, width, size=18, col=WHITE, lh=1.38, bold=False, alpha=1.0):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL,
                       cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)
    line = ''
    for wd in s.split(' '):
        tst = (line + ' ' + wd).strip()
        if c.text_extents(tst).x_advance > width and line:
            text(c, line, x, y, size, col, bold, alpha=alpha); y += size * lh; line = wd
        else:
            line = tst
    if line: text(c, line, x, y, size, col, bold, alpha=alpha); y += size * lh
    return y

def rrect(c, x, y, w, h, r):
    c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    c.close_path()

def cyl(c, x0, x1, yc, R, col, ang=0.0, N=0, hel=0.0, lw=1.3, alpha=1.0, outline=True):
    g = cairo.LinearGradient(0, yc - R, 0, yc + R)
    for k in range(11):
        u = k / 10
        z = math.sqrt(max(0, 1 - (2 * u - 1) ** 2))
        sh = 0.28 + 0.72 * z
        if 0.25 < u < 0.4: sh = min(1.0, sh + 0.12)
        g.add_color_stop_rgba(u, col[0] * sh, col[1] * sh, col[2] * sh, alpha)
    c.rectangle(x0, yc - R, x1 - x0, 2 * R); c.set_source(g); c.fill()
    if N:
        c.set_line_width(lw)
        for i in range(N):
            th = 2 * math.pi * (i / N + ang)
            z = math.cos(th)
            if z <= 0.04: continue
            y = yc + R * math.sin(th)
            dy = hel * z
            c.set_source_rgba(0, 0, 0, (0.22 + 0.45 * z) * alpha)
            c.move_to(x0, y - dy); c.line_to(x1, y + dy); c.stroke()
    if outline:
        c.set_source_rgba(0, 0, 0, 0.6 * alpha); c.set_line_width(1.2)
        c.rectangle(x0, yc - R, x1 - x0, 2 * R); c.stroke()

def ghost(c, x0, x1, yc, R):
    c.set_source_rgba(*GREY, 0.28); c.set_line_width(1.2); c.set_dash([5, 4])
    c.rectangle(x0, yc - R, x1 - x0, 2 * R); c.stroke(); c.set_dash([])

def leader(c, x, y, tx, ty, s, col=DIM, size=15, align='l'):
    c.set_source_rgba(*col, 0.8); c.set_line_width(1)
    c.move_to(x, y); c.line_to(tx, ty); c.stroke()
    c.arc(x, y, 2.5, 0, 2 * math.pi); c.fill()
    text(c, s, tx + (4 if align == 'l' else -4), ty + 5, size, col, align=align)

def arrow(c, x0, y0, x1, y1, col, lw=3, head=10, alpha=1.0):
    c.set_source_rgba(*col, alpha); c.set_line_width(lw)
    c.move_to(x0, y0); c.line_to(x1, y1); c.stroke()
    a = math.atan2(y1 - y0, x1 - x0)
    c.move_to(x1, y1)
    c.line_to(x1 - head * math.cos(a - 0.45), y1 - head * math.sin(a - 0.45))
    c.line_to(x1 - head * math.cos(a + 0.45), y1 - head * math.sin(a + 0.45))
    c.close_path(); c.fill()

# ---------------- side view ----------------
YI, YO = 300, 515
D = YO - YI
r1d, r1n = D * 12 / 53, D * 41 / 53
r2d, r2n = D * 21 / 59, D * 38 / 59
SVF = 35 / 137  # side view sleeve shift per close-up px

def side_view(c, t, st):
    a_in, a_out, a_e = ang_at(t)
    cl = clutch(t)
    xs = st['xs']; off = xs * SVF
    e1, e2 = eng_frac(xs, -1), eng_frac(xs, 1)

    rrect(c, 20, 80, 1135, 625, 10); c.set_source_rgb(*PANEL); c.fill()
    text(c, "INSIDE THE GEARBOX  —  side cutaway (simplified, not to scale)", 40, 108, 17, DIM, True)

    # casing
    c.set_source_rgba(0.5, 0.55, 0.62, 0.35); c.set_line_width(2)
    c.move_to(125, 150); c.line_to(780, 150); c.line_to(780, 165); c.line_to(925, 165)
    c.line_to(925, 640); c.line_to(780, 640); c.line_to(780, 690); c.stroke()
    c.move_to(125, 150); c.line_to(125, 470); c.stroke()

    # engine & clutch
    cyl(c, 30, 60, YI, 18, GREY, -a_e, 6)
    text(c, "engine", 8, YI + 45, 13, DIM)
    cyl(c, 58, 82, YI, 118, GREY, -a_e, 40, 0)                      # flywheel
    dsh = 4 * cl; psh = 9 * cl
    cyl(c, 84 + dsh, 93 + dsh, YI, 102, BLUE, -a_in, 28)            # disc
    cyl(c, 95 + psh, 112 + psh, YI, 108, GREY, -a_e, 30)             # pressure plate
    # input shaft
    cyl(c, 86, 905, YI, 14, BLUE, -a_in, 8)
    # bearings
    for bx in (128, 768, 905):
        for yy in (YI, YO):
            c.set_source_rgba(0.75, 0.75, 0.78, 0.9); c.rectangle(bx - 7, yy - 24, 14, 10); c.rectangle(bx - 7, yy + 14, 14, 10); c.fill()
    # output shaft
    cyl(c, 140, 905, YO, 15, GREEN, a_out, 8)
    # ghost 3rd/4th/5th
    for (x0, x1, ri) in ((560, 600, D / 2.276), (640, 680, D / 1.975), (835, 875, D / 1.767)):
        ghost(c, x0, x1, YI, ri); ghost(c, x0, x1, YO, D - ri)
    text(c, "3rd / 4th / 5th gear sets", 600, 672, 14, GREY)
    text(c, "(not involved — outline only)", 600, 689, 12, GREY)

    # final drive
    rp = 32
    cyl(c, 160, 198, YO, rp, GREEN, a_out, 13, 4)
    c.save(); c.rectangle(20, 80, 1135, 625); c.clip()
    cyl(c, 155, 203, YO + rp + 130, 130, GREEN, -a_out * rp / 130, 52, -4)
    c.restore()

    # 1st pair
    gcol1 = mix(GOLD, GREEN, e1); gcol2 = mix(GOLD, GREEN, e2)
    cyl(c, 250, 305, YI, r1d, BLUE, -a_in, 12, 6)
    cyl(c, 250, 305, YO, r1n, gcol1, a_in * 12 / 41, 41, -6)
    cyl(c, 305, 322, YO, 92, gcol1, a_in * 12 / 41, 34)              # dog ring/cone of 1st
    # 2nd pair
    cyl(c, 445, 500, YI, r2d, BLUE, -a_in, 21, 6)
    cyl(c, 445, 500, YO, r2n, gcol2, a_in * 21 / 38, 38, -6)
    cyl(c, 428, 445, YO, 92, gcol2, a_in * 21 / 38, 34)

    # blocker rings (brass)
    rs1 = st['sh1'] * SVF * 0.5; rs2 = st['sh2'] * SVF * 0.5
    ring1_ang = a_out if (st['r1'] != 0.5 or e1 > 0) else a_out
    cyl(c, 323 - rs1, 336 - rs1, YO, 88, BRASS, a_out, 30)
    cyl(c, 414 + rs2, 427 + rs2, YO, 88, BRASS, a_out, 30)
    # friction glow
    for f, x in ((st['f1'], 322 - rs1), (st['f2'], 427 + rs2)):
        if f > 0.01:
            flick = 0.75 + 0.25 * math.sin(t * 40)
            rg = cairo.LinearGradient(x - 10, 0, x + 10, 0)
            rg.add_color_stop_rgba(0, 1, 0.3, 0.05, 0)
            rg.add_color_stop_rgba(0.5, 1, 0.45, 0.1, 0.85 * f * flick)
            rg.add_color_stop_rgba(1, 1, 0.3, 0.05, 0)
            c.rectangle(x - 10, YO - 92, 20, 184); c.set_source(rg); c.fill()
    # hub
    cyl(c, 352, 398, YO, 80, GREEN, a_out, 24)
    # sleeve
    sx0, sx1 = 340 + off, 410 + off
    cyl(c, sx0, sx0 + 28, YO, 100, GREEN, a_out, 36)
    cyl(c, sx0 + 28, sx0 + 42, YO, 86, mix(GREEN, (0, 0, 0), 0.35), a_out, 30)
    cyl(c, sx0 + 42, sx1, YO, 100, GREEN, a_out, 36)

    # fork + rail
    gx = sx0 + 35
    c.set_source_rgba(0.62, 0.62, 0.66, 1); c.rectangle(300 + off, 186, 470, 14); c.fill()
    c.set_source_rgba(0.62, 0.62, 0.66, 0.92); c.rectangle(gx - 7, 186, 14, YO - 100 - 186 + 6); c.fill()
    c.set_source_rgba(0.62, 0.62, 0.66, 0.55); c.rectangle(gx - 6, YO - 96, 12, 104); c.fill()
    c.set_source_rgba(0, 0, 0, 0.6); c.set_line_width(1); c.rectangle(gx - 7, 186, 14, YO - 100 - 186 + 6); c.stroke()

    # power path
    pa = (1 - cl) * max(e1, e2)
    if pa > 0.02:
        gxp = 278 if e1 > e2 else 472
        dogx = 314 if e1 > e2 else 436
        pts = [(40, YI), (gxp, YI), (gxp, YO - 60), (375, YO - 60), (375, YO), (180, YO), (180, YO + rp + 40)]
        path(c, t, pts, ORANGE, pa)
    na = (1 - cl) * (1 - max(e1, e2))
    if na > 0.02:
        path(c, t, [(40, YI), (500, YI)], (0.55, 0.75, 1.0), na * 0.8, w=6)

    # labels
    leader(c, 70, YI - 118, 40, 150, "flywheel", size=13)
    leader(c, 88 + dsh, YI + 98, 40, 440, "clutch disc", size=13)
    leader(c, 104 + psh, YI + 104, 40, 468, "pressure plate", size=13)
    leader(c, 700, YI, 935, 250, "INPUT shaft", BLUE, 15)
    leader(c, 720, YO, 935, 470, "OUTPUT shaft", GREEN, 15)
    leader(c, 278, YI - r1d, 230, 128, "1st drive gear (fixed)", BLUE, 13)
    leader(c, 472, YI - r2d, 470, 128, "2nd drive gear (fixed)", BLUE, 13)
    leader(c, 300, YO + 125, 312, 680, "1st driven gear", gcol1, 13)
    leader(c, 498, YO + 110, 520, 640, "2nd driven gear", gcol2, 13)
    leader(c, 300 + off + 300, 193, 935, 200, "selector rail", GREY, 13)
    leader(c, gx, 360, 935, 330, "selector fork", GREY, 13)
    leader(c, sx1 - 8, YO - 95, 935, 410, "sleeve", GREEN, 13)
    leader(c, 398, YO + 70, 935, 540, "hub (splined to output shaft)", GREEN, 13)
    leader(c, 336 - rs1, YO + 80, 935, 580, "blocker rings (brass)", BRASS, 13)
    leader(c, 414 + rs2, YO + 80, 935, 580, "", BRASS, 13)
    leader(c, 180, YO + 32, 40, 600, "final-drive", GREEN, 13)
    text(c, "pinion", 44, 620, 13, GREEN)
    text(c, "→ differential", 44, 637, 13, GREEN)

    # state tags
    def tag(x, y, s, col):
        c.select_font_face(FONT, 0, 1); c.set_font_size(13)
        w = c.text_extents(s).x_advance + 14
        rrect(c, x - w / 2, y - 15, w, 22, 6); c.set_source_rgba(*col, 0.92); c.fill()
        text(c, s, x, y + 1, 13, (0.05, 0.05, 0.05), True, 'c')
    tag(278, YO + r1n - 10 if YO + r1n - 10 < 690 else 680, "LOCKED" if e1 > 0.99 else "FREE", ORANGE if e1 > 0.99 else GOLD)
    tag(472, YO + r2n + 18, "LOCKED" if e2 > 0.99 else "FREE", ORANGE if e2 > 0.99 else GOLD)

    # legend
    lx, ly = 935, 625
    for col, s in ((BLUE, "turns with input shaft"), (GREEN, "turns with output shaft"),
                   (GOLD, "free gear (on needle bearing)"), (ORANGE, "power flow")):
        c.set_source_rgb(*col); c.rectangle(lx, ly - 10, 12, 12); c.fill()
        text(c, s, lx + 18, ly + 1, 13, DIM); ly += 19

def path(c, t, pts, col, alpha, w=9):
    c.set_line_join(cairo.LINE_JOIN_ROUND); c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_source_rgba(*col, 0.25 * alpha); c.set_line_width(w + 10)
    c.move_to(*pts[0]); [c.line_to(*p) for p in pts[1:]]; c.stroke()
    c.set_source_rgba(*col, 0.95 * alpha); c.set_line_width(w)
    c.set_dash([16, 12], -t * 60)
    c.move_to(*pts[0]); [c.line_to(*p) for p in pts[1:]]; c.stroke()
    c.set_dash([])
    c.set_line_cap(cairo.LINE_CAP_BUTT)

# ---------------- synchro close-up ----------------
X0, Y0 = 1530, 410
CY0, CY1 = 200, 600

def tooth(c, xa, xb, yc, chL, chR, col, alpha=1):
    h = TW * P / 2
    c.move_to(xa + (CH if chL else 0), yc - h)
    c.line_to(xb - (CH if chR else 0), yc - h)
    if chR: c.line_to(xb, yc)
    c.line_to(xb - (CH if chR else 0), yc + h)
    c.line_to(xa + (CH if chL else 0), yc + h)
    if chL: c.line_to(xa, yc)
    c.close_path()
    g = cairo.LinearGradient(0, yc - h, 0, yc + h)
    g.add_color_stop_rgba(0, *mix(col, WHITE, 0.25), alpha)
    g.add_color_stop_rgba(0.5, *col, alpha)
    g.add_color_stop_rgba(1, *mix(col, (0, 0, 0), 0.45), alpha)
    c.set_source(g); c.fill_preserve()
    c.set_source_rgba(0, 0, 0, 0.7 * alpha); c.set_line_width(1.2); c.stroke()

def teeth_col(c, xa, xb, off, chL, chR, col, alpha=1):
    for k in range(-5, 6):
        yc = Y0 - ((off % 1.0) + k) * P
        if yc < CY0 - P or yc > CY1 + P: continue
        tooth(c, xa, xb, yc, chL, chR, col, alpha)

def closeup(c, t, st):
    a_in, a_out, _ = ang_at(t)
    rrect(c, 1165, 80, 735, 625, 10); c.set_source_rgb(*PANEL); c.fill()
    text(c, "1st/2nd SYNCHRONISER — close-up", 1185, 108, 17, DIM, True)
    text(c, "teeth unrolled flat · viewed in a frame turning with the sleeve", 1185, 130, 13, DIM)
    xs = st['xs']
    e1, e2 = eng_frac(xs, -1), eng_frac(xs, 1)
    g1off = rel_g(1, t) + C1
    g2off = rel_g(2, t) + C2

    c.save(); c.rectangle(1170, CY0, 725, CY1 - CY0); c.clip()
    c.set_source_rgb(0.07, 0.09, 0.12); c.paint()
    for d, goff, roff, sh, f, gcol, e in ((-1, g1off, st['r1'], st['sh1'], st['f1'], mix(GOLD, GREEN, e1), e1),
                                          (1, g2off, st['r2'], st['sh2'], st['f2'], mix(GOLD, GREEN, e2), e2)):
        def X(v): return X0 + d * v
        # gear body
        xa, xb = sorted((X(270), X(335)))
        c.rectangle(xa, CY0, xb - xa, CY1 - CY0); c.set_source_rgb(*mix(gcol, (0, 0, 0), 0.35)); c.fill()
        # cone zone + friction
        rx = 150 + sh
        xa, xb = sorted((X(rx + 48), X(213)))
        c.rectangle(xa, CY0, xb - xa, CY1 - CY0); c.set_source_rgba(*mix(gcol, (0, 0, 0), 0.55), 1); c.fill()
        if f > 0.01:
            flick = 0.8 + 0.2 * math.sin(t * 37 + d)
            c.rectangle(xa - 2, CY0, xb - xa + 4, CY1 - CY0); c.set_source_rgba(1, 0.4, 0.08, 0.75 * f * flick); c.fill()
        # ring body
        xa, xb = sorted((X(rx + 26), X(rx + 48)))
        c.rectangle(xa, CY0, xb - xa, CY1 - CY0); c.set_source_rgb(*mix(BRASS, (0, 0, 0), 0.25)); c.fill()
        # dog teeth
        xa, xb = sorted((X(215), X(270)))
        teeth_col(c, xa, xb, goff, d > 0, d < 0, gcol)
        # ring teeth
        xa, xb = sorted((X(rx), X(rx + 36)))
        teeth_col(c, xa, xb, roff, d > 0, d < 0, BRASS)
    # hub splines
    teeth_col(c, X0 - 85, X0 + 85, 0.5, False, False, mix(GREEN, (0, 0, 0), 0.45))
    # sleeve teeth
    teeth_col(c, X0 + xs - SL, X0 + xs + SL, 0.0, True, True, GREEN)
    c.restore()
    c.set_source_rgba(1, 1, 1, 0.15); c.rectangle(1170, CY0, 725, CY1 - CY0); c.set_line_width(1); c.stroke()

    # column labels
    for d, nm in ((-1, "1st gear"), (1, "2nd gear")):
        text(c, nm, X0 + d * 300, 165, 14, GOLD, True, 'c')
        text(c, "body", X0 + d * 300, 182, 12, DIM, align='c')
        text(c, "dog", X0 + d * 242, 165, 13, GOLD, align='c')
        text(c, "teeth", X0 + d * 242, 182, 13, GOLD, align='c')
        text(c, "blocker", X0 + d * 175, 165, 13, BRASS, align='c')
        text(c, "ring", X0 + d * 175, 182, 13, BRASS, align='c')
    text(c, "sleeve (slides on hub splines)", X0 + xs, 622, 13, GREEN, True, 'c')
    text(c, "← toward 1st", 1185, 622, 13, DIM)
    text(c, "toward 2nd →", 1880, 622, 13, DIM, align='r')

    # fork force arrow
    ph = st['ph']
    if ph in ('move', 'pre', 'index', 'sync', 'align', 'slide', 'out'):
        d = st['side']
        if ph == 'out': d = 1
        ax = X0 + xs
        arrow(c, ax - d * 40, 645, ax + d * 40, 645, WHITE, 3, 12, 0.85)
        text(c, "fork force", ax + 50, 650, 12, WHITE)

    # relative speed readout
    rel1 = w_in(t) / R1 - w_out(t); rel2 = w_in(t) / R2 - w_out(t)
    yy = 692
    for d, rel, e, nm in ((-1, rel1, e1, "1st"), (1, rel2, e2, "2nd")):
        x = X0 + d * 175
        if e > 0.99: s, col = "LOCKED to sleeve", ORANGE
        elif abs(rel) < 3: s, col = "speed = sleeve speed", GREEN
        else: s, col = f"{nm} gear vs sleeve: {rel:+.0f} rpm", GOLD
        text(c, s, x, yy, 13, col, True, 'c')
    if st['ph'] == 'sync':
        text(c, "BLOCKED — chamfer on chamfer", 1880, 110, 15, (1, 0.45, 0.2), True, 'r')
    # moving arrows on gear columns
    for d, rel, e in ((-1, rel1, e1), (1, rel2, e2)):
        if e < 0.99 and abs(rel) > 3:
            x = X0 + d * 300
            up = rel > 0
            arrow(c, x, 540 if up else 260, x, 450 if up else 350, WHITE, 3, 10, 0.6)

# ---------------- HUD ----------------
def hud(c, t, st):
    # caption box
    rrect(c, 20, 720, 990, 345, 10); c.set_source_rgb(*PANEL); c.fill()
    cap = caption(t)
    if cap:
        t0, t1, title, body = cap
        al = min(1, (t - t0) / 0.35, (t1 - t) / 0.35 + 0.0001)
        al = max(0, min(1, al))
        text(c, title.upper(), 44, 765, 24, ORANGE, True, alpha=al)
        wrap(c, body, 44, 805, 940, 20, WHITE, 1.45, alpha=al)
    # rpm bars
    rrect(c, 1025, 720, 455, 345, 10); c.set_source_rgb(*PANEL); c.fill()
    text(c, "SPEEDS (rpm)", 1045, 752, 16, DIM, True)
    xs = st['xs']; e1, e2 = eng_frac(xs, -1), eng_frac(xs, 1)
    rows = [("Engine", eng(t), GREY), ("Input shaft", w_in(t), BLUE),
            ("1st driven gear", w_in(t) / R1, mix(GOLD, GREEN, e1)),
            ("2nd driven gear", w_in(t) / R2, mix(GOLD, GREEN, e2)),
            ("Output shaft", w_out(t), GREEN)]
    y = 790
    for nm, v, col in rows:
        text(c, nm, 1045, y, 15, WHITE)
        text(c, f"{v:,.0f}", 1460, y, 15, WHITE, True, 'r')
        c.set_source_rgba(1, 1, 1, 0.08); c.rectangle(1045, y + 8, 415, 12); c.fill()
        c.set_source_rgb(*col); c.rectangle(1045, y + 8, 415 * min(1, v / 3200), 12); c.fill()
        y += 52
    text(c, "Ratios: 1st ≈ 3.42:1, 2nd ≈ 1.81:1", 1045, 1052, 13, DIM)

    # H pattern
    rrect(c, 1490, 720, 200, 345, 10); c.set_source_rgb(*PANEL); c.fill()
    text(c, "GEAR LEVER", 1590, 752, 16, DIM, True, 'c')
    cx, cy = 1590, 880
    c.set_source_rgba(1, 1, 1, 0.35); c.set_line_width(10); c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.move_to(cx - 55, cy); c.line_to(cx + 55, cy); c.stroke()
    for gx_, gs in ((-55, ("1", "2")), (0, ("3", "4")), (55, ("5", None))):
        c.move_to(cx + gx_, cy - 70); c.line_to(cx + gx_, cy + (70 if gs[1] else 0)); c.stroke()
        text(c, gs[0], cx + gx_, cy - 82, 16, WHITE, True, 'c')
        if gs[1]: text(c, gs[1], cx + gx_, cy + 98, 16, WHITE, True, 'c')
    c.set_line_cap(cairo.LINE_CAP_BUTT)
    lat = kf(t, [(0, 0), (12.4, 0), (13.0, -1)])
    kx = cx + 55 * lat; ky = cy + 70 * xs / 137
    c.arc(kx, ky, 15, 0, 2 * math.pi); c.set_source_rgb(*ORANGE); c.fill()
    c.arc(kx - 4, ky - 4, 5, 0, 2 * math.pi); c.set_source_rgba(1, 1, 1, 0.5); c.fill()
    gname = "1st" if e1 > 0.99 else "2nd" if e2 > 0.99 else "neutral"
    text(c, gname.upper(), 1590, 1045, 20, ORANGE, True, 'c')

    # pedals
    rrect(c, 1700, 720, 200, 345, 10); c.set_source_rgb(*PANEL); c.fill()
    text(c, "PEDALS", 1800, 752, 16, DIM, True, 'c')
    cl = clutch(t)
    px, py = 1760, 790
    angl = math.radians(15 + 40 * cl)
    ex, ey = px + 150 * math.sin(angl) * 0.5, py + 150 * math.cos(angl)
    c.set_source_rgb(0.7, 0.7, 0.75); c.set_line_width(6); c.move_to(px, py); c.line_to(ex, ey); c.stroke()
    rrect(c, ex - 22, ey - 6, 44, 14, 4); c.set_source_rgb(*(ORANGE if cl > 0.5 else GREY)); c.fill()
    text(c, "clutch", 1760, 990, 14, WHITE, align='c')
    text(c, "PRESSED" if cl > 0.5 else "released", 1760, 1010, 13, ORANGE if cl > 0.5 else DIM, True, 'c')
    th = throttle(t)
    c.set_source_rgba(1, 1, 1, 0.1); c.rectangle(1840, 800, 22, 170); c.fill()
    c.set_source_rgb(0.35, 0.8, 0.45); c.rectangle(1840, 970 - 170 * th, 22, 170 * th); c.fill()
    text(c, "throttle", 1851, 990, 14, WHITE, align='c')

CAPS = [
 (0, 10, "Neutral — clutch engaged, car stopped",
  "The engine turns the input shaft (blue). Its fixed 1st and 2nd drive gears are always meshed with the 1st and 2nd driven gears, so those spin too, but they run free on needle bearings on the output shaft. The hub and sleeve (green) are splined to the output shaft, which is not turning. No drive reaches the wheels."),
 (10, 12.4, "Clutch pedal pressed",
  "The pressure plate releases the clutch disc. The input shaft, and the free gears it drives, are no longer powered and slowly lose speed."),
 (12.4, 14.2, "Lever left, then forward to 1st",
  "Moving the lever left selects the 1st/2nd fork; pushing it forward makes the fork slide the sleeve toward 1st gear."),
 (14.2, 15.6, "Pre-synchronisation",
  "Spring-loaded struts in the hub move with the sleeve and push the brass blocker ring onto 1st gear's cone. Cone friction drags the ring round until its lugs hit the ends of their slots in the hub: its teeth now sit half a tooth out of line, chamfer facing chamfer."),
 (15.6, 19.4, "Synchronisation — sleeve blocked",
  "The sleeve presses on the ring's chamfers, forcing the ring hard onto the cone. Friction brakes 1st gear, and with it the whole input shaft, down to the output shaft's speed: zero, because the car is stopped. While the speeds differ, the friction torque holds the ring in the blocking position."),
 (19.4, 20.2, "Speeds equal — ring unblocks",
  "With no speed difference there is no friction torque left. The sleeve's chamfers turn the ring back and the sleeve slides through its teeth."),
 (20.2, 21.3, "1st gear engaged",
  "The sleeve slides over 1st gear's dog teeth. 1st gear is now locked to the hub, and so to the output shaft."),
 (21.3, 24.2, "Clutch released — moving off",
  "Power path: engine, clutch, input shaft, 1st drive gear, 1st driven gear, dog teeth, sleeve, hub, output shaft, final-drive pinion, differential. 2nd gear still spins, freewheeling on its bearing."),
 (24.2, 30.2, "Accelerating in 1st",
  "Ratio ≈ 3.42 : 1. The output shaft turns about 3.42 times slower than the engine, multiplying torque. At 3,000 rpm the output shaft turns at about 880 rpm."),
 (30.2, 31.3, "Clutch pressed for the change to 2nd",
  "Throttle closed, clutch disengaged. 1st is still engaged, so the input shaft is now turned from the wheel side, at 3.42 × output-shaft speed."),
 (31.3, 33.2, "Lever pulled back through neutral",
  "The fork pulls the sleeve off 1st gear's dog teeth. 1st gear is free again and the input shaft is no longer tied to the wheels."),
 (33.2, 35.2, "Sleeve heads for 2nd",
  "Same plane, lever straight back. The struts press 2nd gear's blocker ring onto its cone; the ring indexes and blocks the sleeve. 2nd gear is turning FASTER than the output shaft (input ÷ 1.81 is more than input ÷ 3.42)."),
 (35.2, 38.8, "Synchronisation — slowing down",
  "Cone friction now brakes 2nd gear, and with it the input shaft and clutch disc, from about 2,900 to about 1,560 rpm: 1.81 × output-shaft speed. On an upshift the synchroniser slows the input side; on a downshift it speeds it up."),
 (38.8, 40.6, "2nd gear engaged",
  "Speeds match, the ring unblocks, and the sleeve locks onto 2nd gear's dog teeth."),
 (40.6, 43.0, "Clutch released",
  "The clutch disc grips the flywheel again, and engine speed is pulled to the input shaft's ≈ 1,560 rpm."),
 (43.0, 57, "Driving in 2nd",
  "Power path: input shaft, 2nd drive gear, 2nd driven gear, dog teeth, sleeve, hub, output shaft. Ratio ≈ 1.81 : 1. 1st gear keeps spinning, but slower than the output shaft: it simply freewheels on its needle bearing."),
]

def caption(t):
    for cp in CAPS:
        if cp[0] <= t < cp[1]: return cp
    return None

def header(c, t):
    c.set_source_rgb(0.04, 0.05, 0.07); c.rectangle(0, 0, W, 70); c.fill()
    text(c, "CITROËN MA/5 MANUAL GEARBOX", 24, 44, 26, WHITE, True)
    text(c, "neutral → 1st → 2nd", 560, 44, 22, ORANGE, True)
    if slowmo(t):
        rrect(c, 1540, 16, 360, 38, 8); c.set_source_rgba(0.9, 0.2, 0.2, 0.9); c.fill()
        text(c, "SLOW MOTION — real shift < 1 s", 1720, 41, 16, WHITE, True, 'c')

def overlay_card(c, alpha, lines):
    c.set_source_rgba(0.03, 0.04, 0.06, 0.86 * alpha); c.rectangle(0, 0, W, H); c.fill()
    y = 330
    for s, size, col, bold in lines:
        if s.startswith("•"):
            y = wrap(c, s, 470, y, 1000, size, col, 1.35, bold, alpha) + 8
        else:
            text(c, s, W / 2, y, size, col, bold, 'c', alpha); y += size * 1.7

def frame(c, t):
    c.set_source_rgb(*BG); c.paint()
    st = sync_state(t)
    header(c, t)
    side_view(c, t, st)
    closeup(c, t, st)
    hud(c, t, st)
    if t < 4.5:
        a = 1 if t < 3.8 else (4.5 - t) / 0.7
        overlay_card(c, a, [
            ("CITROËN MA/5 GEARBOX", 54, WHITE, True),
            ("What happens inside: neutral → 1st → 2nd", 30, ORANGE, True),
            ("", 10, WHITE, False),
            ("Schematic animation: layout simplified and not to scale.", 20, DIM, False),
            ("Ratios used: 1st ≈ 3.42 : 1, 2nd ≈ 1.81 : 1 (common MA/5 values; exact ratios vary by version).", 20, DIM, False),
            ("Gear changes are shown in slow motion.", 20, DIM, False)])
    if t > 51:
        a = min(1, (t - 51) / 0.6)
        overlay_card(c, a, [
            ("KEY POINTS", 44, ORANGE, True),
            ("• The 1st and 2nd gear pairs are always in mesh. Engaging a gear means locking a free gear to its shaft with the sliding sleeve.", 24, WHITE, False),
            ("• Before the dog teeth can mesh, the synchroniser matches speeds with friction between the blocker ring and the gear's cone.", 24, WHITE, False),
            ("• The blocker ring stops the sleeve until the speeds are equal. Pushing the lever harder only raises cone pressure and shortens the sync time.", 24, WHITE, False),
            ("• From rest into 1st, the synchro stops the input shaft. On an upshift it slows it down; on a downshift it speeds it up.", 24, WHITE, False)])

def main():
    out = sys.argv[1]
    only = sys.argv[2:]
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(surf)
    if only:
        for s in only:
            t = float(s); frame(c, t); surf.write_to_png(f"{out}_{s}.png")
        return
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                          "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    for i in range(NF):
        frame(c, i / FPS); surf.flush()
        p.stdin.write(bytes(surf.get_data()))
    p.stdin.close(); p.wait()

main()
