import cairo, math, subprocess, sys

W, H, FPS = 1920, 1080, 30
# MA/5N tooth counts (drive x driven): 12x41, 21x38, 32x41, 40x39, 43x33, reverse 12x43, final drive 14x60
Z = {1: (12, 41), 2: (21, 38), 3: (32, 41), 4: (40, 39), 5: (43, 33)}
R = {g: Z[g][1] / Z[g][0] for g in Z}
RR = 43 / 12
FD = 60 / 14
TYRE = 1.67   # m, Saxo 1.1i 155/70 R13 (handbook)
ZID = 17      # idler teeth (drawing only)
K = 0.25 / 3000
G = 80

def ss(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)
def lin(t, t0, t1, v0, v1):
    u = max(0.0, min(1.0, (t - t0) / (t1 - t0))); return v0 + (v1 - v0) * u
def kf(t, pts):
    if t <= pts[0][0]: return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0) if t1 > t0 else 1
            return v0 + (v1 - v0) * ss(u)
    return pts[-1][1]

# ---------------- timeline ----------------
SEGS = []
def add(t0, t1, f): SEGS.append((t0, t1, f))
CLUTCH = [(0, 0), (9, 0), (11, 1), (19.5, 1), (22.5, 0)]
THROT = []          # (t0,t1,level)
SLOW = [(11.3, 19.6)]
EVENTS = {'A': [], 'B': [], 'C': []}
PLANE = [(0, 0), (11.0, 0), (11.6, -1)]
CAPS = []
UNIT_OF = {1: ('A', -1), 2: ('A', 1), 3: ('B', -1), 4: ('B', 1), 5: ('C', -1)}
ORD = {1: '1st', 2: '2nd', 3: '3rd', 4: '4th', 5: '5th'}

def shift_ev(unit, side, ts):
    e = dict(kind='in', side=side, ts=ts, tst=ts + 0.8, tp=ts + 1.3, tb=ts + 2.0, te=ts + 5.2, ta=ts + 5.9, tg=ts + 6.6)
    EVENTS[unit].append(e); return e

def kmh(w_out): return w_out / FD * TYRE * 60 / 1000

# idle / clutch in / 1st
add(0, 11, lambda t: (850, 850, 0))
add(11, 14.0, lambda t: (850, lin(t, 11, 14.0, 850, 600), 0))
add(14.0, 17.6, lambda t: (850, lin(t, 14.0, 17.6, 600, 0), 0))
add(17.6, 19.5, lambda t: (850, 0, 0))
E1 = dict(kind='in', side=-1, ts=11.6, tst=12.6, tp=13.2, tb=14.0, te=17.6, ta=18.4, tg=19.2)
EVENTS['A'].append(E1)
def _pull(t):
    e = lin(t, 19.5, 22.5, 850, 1300); wi = e * ss((t - 19.5) / 3); return (e, wi, wi / R[1])
add(19.5, 22.5, _pull)
def _acc1(t):
    e = 1300 + 1700 * ss((t - 22.5) / 4.5); return (e, e, e / R[1])
add(22.5, 27, _acc1)
THROT.append((19.5, 27, 0.6))
TE = {1: E1['te']}

CAPS += [
 (0, 9, "Neutral — clutch engaged, car stopped",
  "Every drive gear on the input shaft (blue) is fixed to it, and all five gear pairs are always in mesh, so the engine turns all five driven gears on the output shaft. Each driven gear is free to turn on the output shaft. The three synchroniser hubs (green) are splined to the output shaft, which is not turning. No drive reaches the wheels."),
 (9, 11.6, "Clutch pedal pressed",
  "The pressure plate releases the clutch disc. The input shaft and all the driven gears it turns are no longer powered and slowly lose speed."),
 (11.6, 12.6, "Into 1st: lever left, then forward",
  "Moving the lever left selects the 1st/2nd fork. Pushing it forward makes the fork slide the 1/2 sleeve toward 1st gear."),
 (12.6, 14.0, "Pre-synchronisation",
  "Spring-and-ball detents in the hub move with the sleeve and push the blocker ring onto 1st gear's cone. Cone friction drags the ring round until its lugs hit the ends of their slots in the hub: its teeth now sit out of line with the sleeve teeth, chamfer facing chamfer."),
 (14.0, 17.6, "Synchronising 1st — sleeve blocked",
  "The sleeve presses on the ring's chamfers, forcing the ring hard onto the cone. Friction brakes 1st gear, and with it the whole input shaft, down to the output shaft's speed: zero, because the car is stopped. While the speeds differ, the friction torque holds the ring in the blocking position."),
 (17.6, 18.4, "Speeds equal — ring unblocks",
  "With no speed difference there is no friction torque left. The sleeve's chamfers turn the ring back and the sleeve slides through its teeth."),
 (18.4, 19.5, "1st gear engaged",
  "The sleeve slides over 1st gear's dog teeth. 1st gear is now locked to the hub, and so to the output shaft."),
 (19.5, 22.5, "Clutch released — moving off",
  "Power path: engine, clutch, input shaft, 1st drive gear, 1st driven gear, dog teeth, 1/2 sleeve, hub, output shaft, final-drive pinion, differential."),
 (22.5, 27, "Accelerating in 1st",
  f"Ratio 41/12 ≈ 3.42 : 1. The output shaft turns 3.42 times slower than the engine, multiplying torque. At 3,000 rpm: output ≈ {3000/R[1]:,.0f} rpm, road speed ≈ {kmh(3000/R[1]):.0f} km/h."),
]

NOTE_DRIVE = {
 2: "1st gear keeps spinning, but slower than the output shaft: it simply turns free on the shaft.",
 3: "The 1/2 sleeve is back in neutral; 3rd is engaged by its own synchroniser, between the 3rd and 4th driven gears.",
 4: "4th is almost 1 : 1 (40/39 = 0.975): the output shaft turns slightly faster than the engine.",
 5: "5th is an overdrive (43/33 = 0.767): the output shaft turns faster than the engine. The 5th gear set sits in the end housing, with a one-sided synchroniser.",
}
PLANE_TXT = {3: " Then the lever crosses to the centre plane, which works the 3/4 fork.",
             5: " Then the lever crosses to the right-hand plane, which works the 5th fork."}

def upshift(t0, gf, gt):
    uf, sf = UNIT_OF[gf]; ut, st_ = UNIT_OF[gt]
    plane = uf != ut
    Rf, Rt = R[gf], R[gt]
    w0 = 3000 / Rf
    td0, td1 = t0 + 1.0, t0 + 2.5
    tfree = td0 + 0.39 * 1.5
    ts = td1 + (0.7 if plane else 0.1)
    EVENTS[uf].append(dict(kind='out', side=sf, t0=td0, t1=td1))
    e = shift_ev(ut, st_, ts)
    tb, te, tg = e['tb'], e['te'], e['tg']
    tr0, tr1 = tg + 0.2, tg + 2.2
    ta = tr1 + 4.5
    wS = w0 * 0.985
    def wout(t): return lin(t, t0, te, w0, wS)
    wf0 = wout(tfree) * Rf; wtb = wf0 * 0.97; wte = wS * Rt
    def engf(t):
        if t < t0 + 0.4: return 3000
        if t < tr0: return lin(t, t0 + 0.4, tr0, 3000, wte + 150)
        return lin(t, tr0, tr1, wte + 150, wte)
    add(t0, tfree, lambda t: (engf(t), wout(t) * Rf, wout(t)))
    add(tfree, tb, lambda t: (engf(t), lin(t, tfree, tb, wf0, wtb), wout(t)))
    add(tb, te, lambda t: (engf(t), lin(t, tb, te, wtb, wte), wout(t)))
    add(te, tr1, lambda t: (engf(t), wte, wS))
    def acc(t):
        ev = wte + (3000 - wte) * ss((t - tr1) / 4.5); return (ev, ev, ev / Rt)
    add(tr1, ta, acc)
    CLUTCH.extend([(t0, 0), (t0 + 0.8, 1), (tr0, 1), (tr1, 0)])
    THROT.append((tr1, ta, 0.6))
    SLOW.append((td0 - 0.3, tg + 0.3))
    if plane:
        p = {3: 0, 5: 1}[gt]; pf = {'A': -1, 'B': 0}[uf]
        PLANE.extend([(td1, pf), (td1 + 0.7, p)])
    TE[gt] = te
    Gf, Gt = ORD[gf], ORD[gt]
    CAPS.extend([
     (t0, td0, f"Clutch pressed for {Gt}",
      f"Throttle closed, clutch disengaged. {Gf} is still engaged, so the input shaft is now turned from the wheel side, at {Rf:.3g} × output-shaft speed."),
     (td0, ts, f"Out of {Gf}, through neutral",
      f"The fork pulls the sleeve off {Gf} gear's dog teeth. {Gf} gear is free again and the input shaft is no longer tied to the wheels." + PLANE_TXT.get(gt, "")),
     (ts, tb, f"Sleeve heads for {Gt}",
      f"The detents press {Gt} gear's blocker ring onto its cone; the ring indexes and blocks the sleeve. {Gt} gear is turning FASTER than the output shaft (input ÷ {Rt:.3g} is more than input ÷ {Rf:.3g}), so the synchroniser has to slow it down."),
     (tb, te, f"Synchronising {Gt} — slowing the input side",
      f"Cone friction brakes {Gt} gear, and with it the input shaft and clutch disc, from about {wtb:,.0f} to about {wte:,.0f} rpm: {Rt:.3g} × output-shaft speed. Until the speeds match, the ring keeps the sleeve blocked."),
     (te, tr0, f"{Gt} gear engaged",
      f"Speeds match, the ring unblocks, and the sleeve locks onto {Gt} gear's dog teeth."),
     (tr0, tr1, "Clutch released",
      f"The clutch disc grips the flywheel again, and engine speed is pulled to the input shaft's ≈ {wte:,.0f} rpm."),
     (tr1, ta + 0.5 if gt < 5 else ta + 1.0, f"Driving in {Gt}",
      f"Power path: input shaft, {Gt} drive gear, {Gt} driven gear, dog teeth, sleeve, hub, output shaft. Ratio ≈ {Rt:.3f} : 1. At 3,000 rpm: output ≈ {3000/Rt:,.0f} rpm, ≈ {kmh(3000/Rt):.0f} km/h. " + NOTE_DRIVE[gt]),
    ])
    return ta

t = 27
for gf, gt in ((1, 2), (2, 3), (3, 4), (4, 5)):
    ta = upshift(t, gf, gt)
    add(ta, ta + 0.5 if gt < 5 else ta + 1.0, lambda tt, g=gt: (3000, 3000, 3000 / R[g]))
    THROT.append((ta, ta + (0.5 if gt < 5 else 1.0), 0.6))
    t = ta + (0.5 if gt < 5 else 1.0)

# ---- stop ----
T5 = t
w5 = 3000 / R[5]
td0, td1 = T5 + 1.0, T5 + 2.5
tfree = td0 + 0.39 * 1.5
TSTOP = td0 + 6.0
EVENTS['C'].append(dict(kind='out', side=-1, t0=td0, t1=td1))
PLANE.extend([(td1, 1), (td1 + 0.7, 0)])
CLUTCH.extend([(T5, 0), (T5 + 0.8, 1)])
def wout_stop(t): return w5 if t < td0 else lin(t, td0, TSTOP, w5, 0)
def eng_stop(t): return lin(t, T5, T5 + 2.0, 3000, 850)
wf = wout_stop(tfree) * R[5]
add(T5, tfree, lambda t: (eng_stop(t), wout_stop(t) * R[5], wout_stop(t)))
add(tfree, TSTOP + 0.5, lambda t: (eng_stop(t), lin(t, tfree, TSTOP + 0.5, wf, 0), wout_stop(t)))
COMPRESS = (td0 + 0.2, TSTOP)
CAPS.extend([
 (T5, td0, "Slowing down: clutch pressed", "Throttle closed, clutch disengaged, ready to come out of 5th and stop."),
 (td0, td1 + 0.7, "Out of 5th, back to neutral",
  "The fork pulls the 5th sleeve off the dog teeth. The lever returns to the centre (3/4) plane, its spring-loaded rest position."),
 (td1 + 0.7, TSTOP + 0.6, "Braking to a stop (time compressed)",
  "In neutral with the clutch pressed nothing drives the input shaft, so it spins down. The output shaft slows with the wheels until the car stops."),
])

# ---- reverse ----
TR = TSTOP + 0.6
add(TSTOP + 0.5, TR + 3.5, lambda t: (850, 0, 0))
PLANE.extend([(TR + 0.2, 0), (TR + 0.8, 1)])
RI_IN = (TR + 1.0, TR + 2.8)
TRC0, TRC1 = TR + 3.5, TR + 6.5
def _rpull(t):
    e = lin(t, TRC0, TRC1, 850, 1300); wi = e * ss((t - TRC0) / 3); return (e, wi, -wi / RR)
add(TR + 3.5, TRC1, _rpull)
TRD1 = TRC1 + 5
def _rdrive(t):
    e = 1300 + 300 * ss((t - TRC1) / 3); return (e, e, -e / RR)
add(TRC1, TRD1, _rdrive)
wr = 1600 / RR
TRB1 = TRD1 + 2.0
add(TRD1, TRB1, lambda t: (lin(t, TRD1, TRD1 + 1, 1600, 850), lin(t, TRD1, TRB1, wr, 0) * RR, -lin(t, TRD1, TRB1, wr, 0)))
RI_OUT = (TRB1 + 0.2, TRB1 + 1.6)
PLANE.extend([(RI_OUT[1], 1), (RI_OUT[1] + 0.6, 0)])
TN = RI_OUT[1] + 0.6
add(TRB1, TN, lambda t: (850, 0, 0))
add(TN, TN + 20, lambda t: (850, 850 * ss((t - TN) / 1.3), 0))
CLUTCH.extend([(TRC0, 1), (TRC1, 0), (TRD1, 0), (TRD1 + 0.8, 1), (TN, 1), (TN + 1.3, 0)])
THROT.extend([(TRC0, TRD1, 0.35)])
TOTAL = TN + 8.5
END = TN + 2.5
CAPS.extend([
 (TR, RI_IN[0], "Selecting reverse — car stopped",
  "With the car stopped and the input shaft at rest, the lever goes right into the 5th/reverse plane, then back. The gate has a lockout so you cannot go straight from 5th into reverse."),
 (RI_IN[0], TRC0, "Reverse idler slides into mesh",
  "Reverse has no synchroniser. A rocker lever slides the straight-cut idler gear along its own shaft until it meshes with the reverse gear on the input shaft and the straight teeth on the outside of the 1/2 sleeve. If the input shaft were still turning, these teeth would grind."),
 (TRC0, TRC1, "Clutch released — reversing",
  "Power path: input shaft, reverse gear (12 teeth), idler, sleeve teeth (43 teeth), hub, output shaft. The extra gear in the train makes the output shaft turn the other way, so the car moves backwards. Ratio 43/12 ≈ 3.58 : 1."),
 (TRC1, TRD1, "Driving in reverse",
  "The 1/2 sleeve stays centred: in reverse it acts only as a gear, so 1st and 2nd remain free. All five forward driven gears still turn free on the output shaft."),
 (TRD1, TN, "Stop, then back to neutral",
  "Clutch pressed, car stopped. The idler slides back out of mesh and the lever returns to the centre plane."),
 (TN, END + 0.5, "Neutral again",
  "Clutch released in neutral: the engine turns the input shaft and all five driven gears again, but every gear is free and no drive reaches the wheels."),
])

SEGS.sort(key=lambda s: s[0])
CLUTCH.sort(key=lambda p: p[0])
PLANE.sort(key=lambda p: p[0])

def speeds(t):
    for t0, t1, f in SEGS:
        if t0 <= t < t1: return f(t)
    return SEGS[-1][2](min(t, SEGS[-1][1]))
def clutch(t): return kf(t, CLUTCH)
def throttle(t):
    for a, b, l in THROT:
        if a <= t < b: return l * ss((t - a) / 0.6)
    return 0.0
def slowmo(t): return any(a < t < b for a, b in SLOW)
def vf(t):
    v = 1.0
    for a, b in SLOW:
        v = min(v, 1 - 0.65 * ss((t - a) / 0.5) * (1 - ss((t - b + 0.5) / 0.5)))
    return v
def ri(t): return ss((t - RI_IN[0]) / (RI_IN[1] - RI_IN[0])) - ss((t - RI_OUT[0]) / (RI_OUT[1] - RI_OUT[0]))

# ---------------- synchro geometry ----------------
P, CH, TW = 70, 14, 0.44
HALF = TW / 2
SL = 125
def contact_xs(yc, rx): return rx + yc / HALF * CH - SL
XB = contact_xs(0.25, 156)
XA = contact_xs(TW, 156)

def ev_in(E, t):
    if t < E['tst']: return 12 * ss((t - E['ts']) / (E['tst'] - E['ts'])), 0.5, 0, 0, 'move'
    if t < E['tp']:
        u = ss((t - E['tst']) / (E['tp'] - E['tst'])); return 12 + 6 * u, 0.5, 6 * u, 0.35 * u, 'pre'
    if t < E['tb']:
        u = ss((t - E['tp']) / (E['tb'] - E['tp']))
        return 18 + (XB - 18) * u, 0.5 + 0.25 * ss((t - E['tp']) / 0.3), 6, 0.35 + 0.65 * u, 'index'
    if t < E['te']: return XB, 0.75, 6, 1.0, 'sync'
    if t < E['ta']:
        u = ss((t - E['te']) / (E['ta'] - E['te'])); yc = 0.25 + (TW - 0.25) * u
        return contact_xs(yc, 156), 1 - yc, 6, 1 - u, 'align'
    if t < E['tg']:
        u = ss((t - E['ta']) / (E['tg'] - E['ta']))
        return XA + (137 - XA) * u, 1 - (TW + (0.5 - TW) * ss(min(1, u / 0.3))), 6, 0, 'slide'
    return 137, 0.5, 6, 0, 'engaged'

def unit_state(u, t):
    st = dict(xs=0.0, r={-1: 0.5, 1: 0.5}, sh={-1: 0, 1: 0}, f={-1: 0, 1: 0}, ph=None, side=0)
    last = None
    for E in EVENTS[u]:
        t0 = E['ts'] if E['kind'] == 'in' else E['t0']
        if t0 <= t: last = E
    if last is None: return st
    s = last['side']
    if last['kind'] == 'in':
        a, off, sh, f, ph = ev_in(last, t)
        st['xs'] = s * a; st['r'][s] = off; st['sh'][s] = sh; st['f'][s] = f; st['ph'] = ph; st['side'] = s
        if ph == 'engaged': st['ph'] = None
    else:
        v = ss((t - last['t0']) / (last['t1'] - last['t0']))
        st['xs'] = s * 137 * (1 - v); st['sh'][s] = 6 * (1 - v)
        st['ph'] = 'out' if v < 1 else None; st['side'] = s
    return st

def eng_frac(xs, d): return max(0.0, min(1.0, (xs * d - 90) / 47))

def all_state(t):
    U = {u: unit_state(u, t) for u in 'ABC'}
    e = {}
    for g, (u, s) in UNIT_OF.items(): e[g] = eng_frac(U[u]['xs'], s)
    return U, e

# ---------------- pre-integration ----------------
NF = int(TOTAL * FPS)
ANG = []
a_in = a_out = a_e = a_id = 0.0
TRI = RI_IN[1]
for i in range(NF):
    t = i / FPS
    ANG.append((a_in, a_out, a_e, a_id))
    e, wi, wo = speeds(t)
    v = vf(t) * K / FPS
    a_in += wi * v; a_out += wo * v; a_e += e * v
    if ri(t) > 0.999: a_id += wi * 12 / ZID * v
def ang_at(t): return ANG[max(0, min(NF - 1, int(round(t * FPS))))]
def rel_g(g, t):
    ai, ao, _, _ = ang_at(t); return (ai / R[g] - ao) * G
CG = {g: 0.5 - rel_g(g, TE[g]) for g in TE}

# ---------------- drawing helpers ----------------
BG = (0.06, 0.08, 0.11); PANEL = (0.09, 0.12, 0.16)
BLUE = (0.42, 0.62, 0.86); GREEN = (0.36, 0.76, 0.58); GOLD = (0.88, 0.70, 0.33)
BRASS = (0.80, 0.56, 0.22); GREY = (0.55, 0.57, 0.6); ORANGE = (1.0, 0.55, 0.12)
PURPLE = (0.72, 0.55, 0.9); WHITE = (0.93, 0.95, 0.97); DIM = (0.62, 0.68, 0.75)
FONT = "DejaVu Sans"
def mix(a, b, u): return tuple(a[i] + (b[i] - a[i]) * u for i in range(3))

def text(c, s, x, y, size=18, col=WHITE, bold=False, align='l', alpha=1.0):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size); ext = c.text_extents(s)
    if align == 'c': x -= ext.x_advance / 2
    elif align == 'r': x -= ext.x_advance
    c.set_source_rgba(*col, alpha); c.move_to(x, y); c.show_text(s)
def wrap(c, s, x, y, width, size=18, col=WHITE, lh=1.4, bold=False, alpha=1.0):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size); line = ''
    for wd in s.split(' '):
        tst = (line + ' ' + wd).strip()
        if c.text_extents(tst).x_advance > width and line:
            text(c, line, x, y, size, col, bold, alpha=alpha); y += size * lh; line = wd
        else: line = tst
    if line: text(c, line, x, y, size, col, bold, alpha=alpha); y += size * lh
    return y
def rrect(c, x, y, w, h, r):
    c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0); c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi); c.arc(x + r, y + r, r, math.pi, 1.5 * math.pi); c.close_path()

def cyl(c, x0, x1, yc, R_, col, ang=0.0, N=0, hel=0.0, lw=1.3, alpha=1.0):
    g = cairo.LinearGradient(0, yc - R_, 0, yc + R_)
    for k in range(11):
        u = k / 10; z = math.sqrt(max(0, 1 - (2 * u - 1) ** 2)); sh = 0.28 + 0.72 * z
        if 0.25 < u < 0.4: sh = min(1.0, sh + 0.12)
        g.add_color_stop_rgba(u, col[0] * sh, col[1] * sh, col[2] * sh, alpha)
    c.rectangle(x0, yc - R_, x1 - x0, 2 * R_); c.set_source(g); c.fill()
    if N:
        c.set_line_width(lw)
        for i in range(N):
            th = 2 * math.pi * (i / N + ang); z = math.cos(th)
            if z <= 0.04: continue
            y = yc + R_ * math.sin(th); dy = hel * z
            c.set_source_rgba(0, 0, 0, (0.22 + 0.45 * z) * alpha)
            c.move_to(x0, y - dy); c.line_to(x1, y + dy); c.stroke()
    c.set_source_rgba(0, 0, 0, 0.6 * alpha); c.set_line_width(1.2)
    c.rectangle(x0, yc - R_, x1 - x0, 2 * R_); c.stroke()

def leader(c, x, y, tx, ty, s, col=DIM, size=13, align='l'):
    c.set_source_rgba(*col, 0.8); c.set_line_width(1)
    c.move_to(x, y); c.line_to(tx, ty); c.stroke()
    c.arc(x, y, 2.5, 0, 2 * math.pi); c.fill()
    if s: text(c, s, tx + (4 if align == 'l' else -4), ty + 5, size, col, align=align)
def arrow(c, x0, y0, x1, y1, col, lw=3, head=10, alpha=1.0):
    c.set_source_rgba(*col, alpha); c.set_line_width(lw)
    c.move_to(x0, y0); c.line_to(x1, y1); c.stroke()
    a = math.atan2(y1 - y0, x1 - x0)
    c.move_to(x1, y1)
    c.line_to(x1 - head * math.cos(a - 0.45), y1 - head * math.sin(a - 0.45))
    c.line_to(x1 - head * math.cos(a + 0.45), y1 - head * math.sin(a + 0.45)); c.close_path(); c.fill()
def tag(c, x, y, s, col):
    c.select_font_face(FONT, 0, 1); c.set_font_size(12)
    w = c.text_extents(s).x_advance + 12
    rrect(c, x - w / 2, y - 14, w, 20, 5); c.set_source_rgba(*col, 0.92); c.fill()
    text(c, s, x, y + 1, 12, (0.05, 0.05, 0.05), True, 'c')
def path(c, t, pts, col, alpha, w=9):
    c.set_line_join(cairo.LINE_JOIN_ROUND); c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_source_rgba(*col, 0.25 * alpha); c.set_line_width(w + 10)
    c.move_to(*pts[0]); [c.line_to(*p) for p in pts[1:]]; c.stroke()
    c.set_source_rgba(*col, 0.95 * alpha); c.set_line_width(w); c.set_dash([16, 12], -t * 60)
    c.move_to(*pts[0]); [c.line_to(*p) for p in pts[1:]]; c.stroke()
    c.set_dash([]); c.set_line_cap(cairo.LINE_CAP_BUTT)

# ---------------- side view ----------------
YI, YO = 268, 483
D = YO - YI
def radii(g): zd, zn = Z[g]; return D * zd / (zd + zn), D * zn / (zd + zn)
PAIR_X = {1: (222, 262), 2: (375, 415), 3: (448, 488), 4: (601, 641), 5: (712, 752)}
UNIT_X = {'A': 318.5, 'B': 544.5, 'C': 807}
SR, DR, RGR, HR = 92, 84, 80, 74
SVF = 26 / 137
RG_R, ID_R = 40, (YO - SR - YI - 40) / 2
ID_Y = YI + 40 + ID_R

def side_view(c, t, U, e):
    ai, ao, ae, aid = ang_at(t)
    cl = clutch(t)
    eng_, wi, wo = speeds(t)
    rio = ri(t)
    rrect(c, 20, 80, 1135, 625, 10); c.set_source_rgb(*PANEL); c.fill()
    text(c, "INSIDE THE GEARBOX  —  side cutaway (simplified, not to scale)", 40, 106, 17, DIM, True)
    c.save(); c.rectangle(20, 80, 1135, 625); c.clip()
    # casing
    c.set_source_rgba(0.5, 0.55, 0.62, 0.35); c.set_line_width(2)
    c.move_to(125, 135); c.line_to(690, 135); c.line_to(690, 128); c.line_to(885, 128); c.line_to(885, 640); c.line_to(690, 640); c.line_to(690, 700); c.stroke()
    c.move_to(125, 135); c.line_to(125, 440); c.stroke()
    c.move_to(690, 135); c.line_to(690, 640); c.stroke()
    text(c, "5th-gear end housing", 762, 152, 12, GREY)
    # engine + clutch
    cyl(c, 30, 60, YI, 18, GREY, -ae, 6)
    text(c, "engine", 22, YI + 40, 11, DIM)
    cyl(c, 58, 82, YI, 118, GREY, -ae, 40)
    dsh, psh = 4 * cl, 9 * cl
    cyl(c, 84 + dsh, 93 + dsh, YI, 102, BLUE, -ai, 28)
    cyl(c, 95 + psh, 112 + psh, YI, 108, GREY, -ae, 30)
    # shafts
    cyl(c, 86, 872, YI, 14, BLUE, -ai, 8)
    cyl(c, 140, 872, YO, 15, GREEN, ao, 8)
    for bx in (128, 690, 872):
        for yy in (YI, YO):
            c.set_source_rgba(0.75, 0.75, 0.78, 0.9); c.rectangle(bx - 7, yy - 24, 14, 10); c.rectangle(bx - 7, yy + 14, 14, 10); c.fill()
    # final drive
    cyl(c, 158, 194, YO, 30, GREEN, ao, 14, 4)
    cyl(c, 153, 199, YO + 30 + 128, 128, GREEN, -ao * 14 / 60, 60, -4)
    # reverse idler (on its own shaft beside the main shafts: drawn behind)
    c.set_source_rgba(0.6, 0.6, 0.65, 0.9); c.rectangle(232, ID_Y - 5, 140, 10); c.fill()
    ix = 302 - 46 * (1 - rio)
    cyl(c, ix, ix + 33, ID_Y, ID_R, PURPLE, aid, ZID, 0, alpha=0.95)
    # gear pairs
    for g in range(1, 6):
        x0, x1 = PAIR_X[g]; rd, rn = radii(g)
        col = mix(GOLD, GREEN, e[g])
        cyl(c, x0, x1, YI, rd, BLUE, -ai, Z[g][0], 6)
        cyl(c, x0, x1, YO, rn, col, ai * Z[g][0] / Z[g][1], Z[g][1], -6)
        text(c, ORD[g], (x0 + x1) / 2, YI - rd - 8, 14, BLUE, True, 'c')
        ty = min(YO + rn + 17, 692)
        tag(c, (x0 + x1) / 2, ty, "LOCKED" if e[g] > 0.99 else "FREE", ORANGE if e[g] > 0.99 else GOLD)
    # reverse gear on input + idler shaft
    cyl(c, 303, 334, YI, RG_R, PURPLE, -ai, 12)
    # synchro units
    for u in 'ABC':
        st = U[u]; cx = UNIT_X[u]; off = st['xs'] * SVF
        sides = (-1, 1) if u != 'C' else (-1,)
        for s in sides:
            g = [gg for gg, (uu, ss_) in UNIT_OF.items() if uu == u and ss_ == s][0]
            col = mix(GOLD, GREEN, e[g])
            dx0 = cx + s * 39
            xa, xb = sorted((dx0, dx0 + s * 14))
            cyl(c, xa, xb, YO, DR, col, ai * Z[g][0] / Z[g][1], 30)
            rs = st['sh'][s] * SVF * 0.5
            rx0 = cx + s * 28 + s * rs
            xa, xb = sorted((rx0, rx0 + s * 10))
            cyl(c, xa, xb, YO, RGR, BRASS, ao, 26)
            f = st['f'][s]
            if f > 0.01:
                xg = cx + s * 39 + s * rs
                fl = 0.75 + 0.25 * math.sin(t * 40)
                rg = cairo.LinearGradient(xg - 10, 0, xg + 10, 0)
                rg.add_color_stop_rgba(0, 1, 0.3, 0.05, 0); rg.add_color_stop_rgba(0.5, 1, 0.45, 0.1, 0.85 * f * fl); rg.add_color_stop_rgba(1, 1, 0.3, 0.05, 0)
                c.rectangle(xg - 10, YO - DR - 6, 20, 2 * DR + 12); c.set_source(rg); c.fill()
        cyl(c, cx - 20, cx + 20, YO, HR, GREEN, ao, 22)
        sx0 = cx - 28 + off
        if u == 'A':
            cyl(c, sx0, sx0 + 21, YO, SR, GREEN, ao, 43)
            cyl(c, sx0 + 21, sx0 + 35, YO, SR - 14, mix(GREEN, (0, 0, 0), 0.35), ao, 24)
            cyl(c, sx0 + 35, sx0 + 56, YO, SR, GREEN, ao, 43)
        else:
            cyl(c, sx0, sx0 + 21, YO, SR, GREEN, ao, 24)
            cyl(c, sx0 + 21, sx0 + 35, YO, SR - 14, mix(GREEN, (0, 0, 0), 0.35), ao, 24)
            cyl(c, sx0 + 35, sx0 + 56, YO, SR, GREEN, ao, 24)
        # fork from below
        gx = cx + off
        c.set_source_rgba(0.62, 0.62, 0.66, 0.95); c.rectangle(gx - 7, YO + SR - 4, 14, 705 - (YO + SR - 4)); c.fill()
        c.set_source_rgba(0.62, 0.62, 0.66, 0.55); c.rectangle(gx - 6, YO - 8, 12, SR + 6); c.fill()
        c.set_source_rgba(0.62, 0.62, 0.66, 1); c.rectangle(gx - 40, 690, 80, 10); c.fill()
    # power path
    pa = (1 - cl)
    gsel = max(e, key=lambda g: e[g])
    if pa > 0.02 and e[gsel] > 0.99:
        x0, x1 = PAIR_X[gsel]; gxp = (x0 + x1) / 2; cx = UNIT_X[UNIT_OF[gsel][0]]
        pts = [(40, YI), (gxp, YI), (gxp, YO - 50), (cx, YO - 50), (cx, YO), (176, YO), (176, YO + 80)]
        path(c, t, pts, ORANGE, pa)
    elif pa > 0.02 and rio > 0.99:
        path(c, t, [(40, YI), (318.5, YI), (318.5, YO), (176, YO), (176, YO + 80)], ORANGE, pa)
    elif pa > 0.02 and abs(wi) > 1:
        path(c, t, [(40, YI), (760, YI)], (0.55, 0.75, 1.0), pa * 0.8, w=6)
    c.restore()
    # labels
    leader(c, 70, YI - 118, 40, 140, "flywheel")
    leader(c, 88 + dsh, YI + 98, 40, 420, "clutch disc")
    leader(c, 104 + psh, YI + 104, 40, 448, "pressure plate")
    leader(c, 176, YO + 30, 40, 590, "final-drive pinion", GREEN)
    text(c, "→ differential", 44, 610, 13, GREEN)
    leader(c, 860, YI, 905, 205, "INPUT shaft", BLUE, 15)
    text(c, "all drive gears fixed", 909, 224, 12, BLUE)
    leader(c, 860, YO, 905, 455, "OUTPUT shaft", GREEN, 15)
    text(c, "driven gears free + 3 synchros", 909, 474, 12, GREEN)
    leader(c, 334, YI + 20, 905, 262, "reverse gear (on input)", PURPLE)
    leader(c, ix + 33, ID_Y, 905, 300, "reverse idler (slides)", PURPLE)
    for u, nm in (('A', "1/2 + R teeth"), ('B', "3/4"), ('C', "5th")):
        tag(c, UNIT_X[u] + U[u]['xs'] * SVF, YO + SR + 22, nm, GREEN)
    text(c, "synchro sleeves (green) · forks below", 909, 360, 12, GREEN)
    text(c, "1/2 sleeve also carries the", 909, 380, 12, GREEN)
    text(c, "straight reverse teeth", 909, 396, 12, GREEN)
    leader(c, UNIT_X['B'] + 33, YO + 70, 905, 520, "blocker rings (brass)", BRASS)
    leader(c, UNIT_X['C'], 660, 905, 555, "selector forks", GREY)
    lx, ly = 905, 600
    for col, s in ((BLUE, "turns with input shaft"), (GREEN, "turns with output shaft"),
                   (GOLD, "free gear"), (PURPLE, "reverse train"), (ORANGE, "power flow")):
        c.set_source_rgb(*col); c.rectangle(lx, ly - 10, 12, 12); c.fill()
        text(c, s, lx + 18, ly + 1, 12, DIM); ly += 18

# ---------------- close-up ----------------
X0, Y0 = 1530, 410
CY0, CY1 = 200, 600
def tooth(c, xa, xb, yc, chL, chR, col, alpha=1):
    h = TW * P / 2
    c.move_to(xa + (CH if chL else 0), yc - h); c.line_to(xb - (CH if chR else 0), yc - h)
    if chR: c.line_to(xb, yc)
    c.line_to(xb - (CH if chR else 0), yc + h); c.line_to(xa + (CH if chL else 0), yc + h)
    if chL: c.line_to(xa, yc)
    c.close_path()
    g = cairo.LinearGradient(0, yc - h, 0, yc + h)
    g.add_color_stop_rgba(0, *mix(col, WHITE, 0.25), alpha); g.add_color_stop_rgba(0.5, *col, alpha)
    g.add_color_stop_rgba(1, *mix(col, (0, 0, 0), 0.45), alpha)
    c.set_source(g); c.fill_preserve(); c.set_source_rgba(0, 0, 0, 0.7 * alpha); c.set_line_width(1.2); c.stroke()
def teeth_col(c, xa, xb, off, chL, chR, col):
    for k in range(-5, 6):
        yc = Y0 - ((off % 1.0) + k) * P
        if CY0 - P < yc < CY1 + P: tooth(c, xa, xb, yc, chL, chR, col)

def active_unit(t):
    if t >= TR - 0.5: return 'REV'
    best = 'A'; bt = -1
    for u in 'ABC':
        for E in EVENTS[u]:
            t0 = E['ts'] if E['kind'] == 'in' else E['t0']
            if E['kind'] == 'in' and t0 - 0.8 <= t and t0 > bt: best, bt = u, t0
    return best

def closeup(c, t, U, e):
    rrect(c, 1165, 80, 735, 625, 10); c.set_source_rgb(*PANEL); c.fill()
    u = active_unit(t)
    if u == 'REV':
        return reverse_view(c, t)
    names = {'A': ("1st", "2nd"), 'B': ("3rd", "4th"), 'C': ("5th", None)}[u]
    text(c, f"{'1/2' if u=='A' else '3/4' if u=='B' else '5th'} SYNCHRONISER — close-up", 1185, 106, 17, DIM, True)
    text(c, "teeth unrolled flat · viewed in a frame turning with the sleeve", 1185, 128, 13, DIM)
    st = U[u]; xs = st['xs']
    eng_, wi, wo = speeds(t)
    c.save(); c.rectangle(1170, CY0, 725, CY1 - CY0); c.clip()
    c.set_source_rgb(0.07, 0.09, 0.12); c.paint()
    for d, nm in ((-1, names[0]), (1, names[1])):
        def X(v): return X0 + d * v
        if nm is None:
            xa, xb = sorted((X(150), X(335)))
            c.rectangle(xa, CY0, xb - xa, CY1 - CY0); c.set_source_rgb(0.1, 0.12, 0.15); c.fill()
            continue
        g = int(nm[0]); col = mix(GOLD, GREEN, e[g])
        goff = rel_g(g, t) + CG[g]
        rx = 150 + st['sh'][d]; f = st['f'][d]
        xa, xb = sorted((X(270), X(335))); c.rectangle(xa, CY0, xb - xa, CY1 - CY0); c.set_source_rgb(*mix(col, (0, 0, 0), 0.35)); c.fill()
        xa, xb = sorted((X(rx + 48), X(213))); c.rectangle(xa, CY0, xb - xa, CY1 - CY0); c.set_source_rgb(*mix(col, (0, 0, 0), 0.55)); c.fill()
        if f > 0.01:
            fl = 0.8 + 0.2 * math.sin(t * 37 + d)
            c.rectangle(xa - 2, CY0, xb - xa + 4, CY1 - CY0); c.set_source_rgba(1, 0.4, 0.08, 0.75 * f * fl); c.fill()
        xa, xb = sorted((X(rx + 26), X(rx + 48))); c.rectangle(xa, CY0, xb - xa, CY1 - CY0); c.set_source_rgb(*mix(BRASS, (0, 0, 0), 0.25)); c.fill()
        xa, xb = sorted((X(215), X(270))); teeth_col(c, xa, xb, goff, d > 0, d < 0, col)
        xa, xb = sorted((X(rx), X(rx + 36))); teeth_col(c, xa, xb, st['r'][d], d > 0, d < 0, BRASS)
    teeth_col(c, X0 - 85, X0 + 85, 0.5, False, False, mix(GREEN, (0, 0, 0), 0.45))
    teeth_col(c, X0 + xs - SL, X0 + xs + SL, 0.0, True, True, GREEN)
    c.restore()
    c.set_source_rgba(1, 1, 1, 0.15); c.rectangle(1170, CY0, 725, CY1 - CY0); c.set_line_width(1); c.stroke()
    for d, nm in ((-1, names[0]), (1, names[1])):
        if nm is None:
            text(c, "end of shaft", X0 + d * 240, 175, 13, DIM, align='c'); continue
        text(c, f"{nm} gear", X0 + d * 300, 160, 14, GOLD, True, 'c'); text(c, "body", X0 + d * 300, 177, 12, DIM, align='c')
        text(c, "dog", X0 + d * 242, 160, 13, GOLD, align='c'); text(c, "teeth", X0 + d * 242, 177, 13, GOLD, align='c')
        text(c, "blocker", X0 + d * 175, 160, 13, BRASS, align='c'); text(c, "ring", X0 + d * 175, 177, 13, BRASS, align='c')
    text(c, "sleeve (slides on hub splines)", X0 + xs, 622, 13, GREEN, True, 'c')
    text(c, f"← toward {names[0]}", 1185, 622, 13, DIM)
    if names[1]: text(c, f"toward {names[1]} →", 1880, 622, 13, DIM, align='r')
    if st['ph']:
        dd = st['side'] if st['ph'] != 'out' else -st['side']
        ax = X0 + xs
        arrow(c, ax - dd * 40, 645, ax + dd * 40, 645, WHITE, 3, 12, 0.85)
        text(c, "fork force", ax + 50, 650, 12, WHITE)
    if st['ph'] == 'sync':
        text(c, "BLOCKED — chamfer on chamfer", 1880, 108, 15, (1, 0.45, 0.2), True, 'r')
    for d, nm in ((-1, names[0]), (1, names[1])):
        if nm is None: continue
        g = int(nm[0]); rel = wi / R[g] - wo; x = X0 + d * 175
        if e[g] > 0.99: s, col = "LOCKED to sleeve", ORANGE
        elif abs(rel) < 3: s, col = "speed = sleeve speed", GREEN
        else: s, col = f"{nm} gear vs sleeve: {rel:+,.0f} rpm", GOLD
        text(c, s, x, 692, 13, col, True, 'c')
        if e[g] < 0.99 and abs(rel) > 3:
            up = rel > 0; xx = X0 + d * 300
            arrow(c, xx, 540 if up else 260, xx, 450 if up else 350, WHITE, 3, 10, 0.6)

def gear_poly(c, cx, cy, r, n, th, col, alpha=1.0):
    m = r / n * 2
    ro, rr = r + m * 0.5, r - m * 0.6
    c.new_path()
    for k in range(n):
        a0 = th + 2 * math.pi * k / n
        pw = 2 * math.pi / n
        for (fa, rad) in ((-0.5, rr), (-0.28, ro), (0.0, ro), (0.22, rr)):
            a = a0 + (fa + 0.14) * pw
            c.line_to(cx + rad * math.cos(a), cy + rad * math.sin(a))
    c.close_path()
    g = cairo.RadialGradient(cx - r * 0.3, cy - r * 0.3, r * 0.1, cx, cy, ro)
    g.add_color_stop_rgba(0, *mix(col, WHITE, 0.25), alpha); g.add_color_stop_rgba(1, *mix(col, (0, 0, 0), 0.35), alpha)
    c.set_source(g); c.fill_preserve(); c.set_source_rgba(0, 0, 0, 0.7 * alpha); c.set_line_width(1.2); c.stroke()
    c.arc(cx, cy, r * 0.22, 0, 2 * math.pi); c.set_source_rgba(0.1, 0.1, 0.12, alpha); c.fill()
    c.move_to(cx, cy); c.line_to(cx + r * 0.7 * math.cos(th), cy + r * 0.7 * math.sin(th))
    c.set_source_rgba(1, 1, 1, 0.5 * alpha); c.set_line_width(3); c.stroke()

def rot_arrow(c, cx, cy, r, sign, col, alpha):
    if alpha < 0.02: return
    a0, a1 = -2.4, -0.9
    c.set_source_rgba(*col, alpha); c.set_line_width(3)
    c.arc(cx, cy, r, a0, a1); c.stroke()
    ae = a1 if sign > 0 else a0
    tx, ty = -math.sin(ae) * sign, math.cos(ae) * sign
    px, py = cx + r * math.cos(ae), cy + r * math.sin(ae)
    c.move_to(px + tx * 10, py + ty * 10); c.line_to(px - ty * 6, py + tx * 6); c.line_to(px + ty * 6, py - tx * 6); c.close_path(); c.fill()

# end-view reverse geometry
PITCH = 22.0
RIN = 12 * PITCH / (2 * math.pi); RIDL = ZID * PITCH / (2 * math.pi); RSLV = 43 * PITCH / (2 * math.pi)
SC = (X0 + 160, 430)
ang1 = math.radians(228)
IC = (SC[0] + (RSLV + RIDL) * math.cos(ang1), SC[1] + (RSLV + RIDL) * math.sin(ang1))
ang2 = math.radians(205)
INC = (IC[0] + (RIDL + RIN) * math.cos(ang2), IC[1] + (RIDL + RIN) * math.sin(ang2))

def reverse_view(c, t):
    text(c, "REVERSE GEAR — end view", 1185, 106, 17, DIM, True)
    text(c, "looking along the shafts · reverse train is straight-cut, no synchroniser", 1185, 128, 13, DIM)
    ai, ao, ae, aid = ang_at(t)
    rio = ri(t)
    a_te = ang_at(RI_IN[1])
    phi1 = math.atan2(IC[1] - INC[1], IC[0] - INC[0])
    phi2 = math.atan2(SC[1] - IC[1], SC[0] - IC[0])
    cin = phi1
    cid = phi1 + math.pi - math.pi / ZID
    pw = 2 * math.pi / ZID
    dl = (phi2 - cid) % pw
    if dl > pw / 2: dl -= pw
    cs = phi2 + math.pi + dl * ZID / 43 - math.pi / 43
    th_in = 2 * math.pi * (ai - a_te[0])
    th_id = -2 * math.pi * (aid - a_te[3])
    th_s = -2 * math.pi * (ao - a_te[1])
    eng_, wi, wo = speeds(t)
    gear_poly(c, *SC, RSLV, 43, th_s + cs, GREEN)
    text(c, "1/2 sleeve — reverse teeth (43)", SC[0], SC[1] + RSLV + 24, 13, GREEN, True, 'c')
    text(c, "on OUTPUT shaft", SC[0], SC[1] + RSLV + 40, 12, GREEN, align='c')
    gear_poly(c, *INC, RIN, 12, th_in + cin, PURPLE)
    text(c, "reverse gear (12)", INC[0] - RIN - 30, INC[1] - 4, 13, PURPLE, True, 'r')
    text(c, "on INPUT shaft", INC[0] - RIN - 30, INC[1] + 13, 12, PURPLE, align='r')
    ia = 0.25 + 0.75 * rio
    gear_poly(c, IC[0], IC[1], RIDL, ZID, th_id + cid, PURPLE, ia)
    text(c, "reverse idler", IC[0] - RIDL - 26, IC[1] + 30, 13, PURPLE, True, 'r')
    if rio < 0.99:
        text(c, "idler out of mesh" if rio < 0.01 else ("idler sliding out of mesh…" if t > RI_OUT[0] else "idler sliding into mesh…"), IC[0] - RIDL - 26, IC[1] + 47, 12, WHITE, align='r')
    on = 1.0 if abs(wi) > 5 else 0.0
    rot_arrow(c, INC[0], INC[1], RIN + 18, 1, WHITE, 0.8 * on)
    rot_arrow(c, IC[0], IC[1], RIDL + 16, -1, WHITE, 0.8 * on * (rio > 0.99))
    rot_arrow(c, SC[0], SC[1], RSLV + 12, 1 if wo < 0 else -1, ORANGE, 0.9 * (1.0 if abs(wo) > 5 else 0))
    y = 640
    text(c, "Forward gears: 2 gears in mesh → output turns OPPOSITE to input.", 1185, y, 14, WHITE)
    text(c, "Reverse: idler added → output turns the SAME way as input → car backwards.", 1185, y + 22, 14, ORANGE, True)
    text(c, f"Output shaft: {wo:+,.0f} rpm", 1185, y + 48, 13, DIM)

# ---------------- HUD ----------------
def caption(t):
    best = None
    for cp in CAPS:
        if cp[0] <= t < cp[1]: best = cp
    return best

def hud(c, t, U, e):
    eng_, wi, wo = speeds(t)
    rrect(c, 20, 720, 990, 345, 10); c.set_source_rgb(*PANEL); c.fill()
    cap = caption(t)
    if cap:
        t0, t1, title, body = cap
        al = max(0, min(1, (t - t0) / 0.35, (t1 - t) / 0.35))
        text(c, title.upper(), 44, 765, 24, ORANGE, True, alpha=al)
        wrap(c, body, 44, 805, 940, 20, WHITE, 1.42, alpha=al)
    rrect(c, 1025, 720, 455, 345, 10); c.set_source_rgb(*PANEL); c.fill()
    text(c, "SPEEDS (rpm)", 1045, 750, 16, DIM, True)
    y = 782
    for nm, v, col in (("Engine", eng_, GREY), ("Input shaft", wi, BLUE), ("Output shaft", wo, GREEN)):
        text(c, nm, 1045, y, 15, WHITE); text(c, f"{v:,.0f}", 1460, y, 15, WHITE, True, 'r')
        c.set_source_rgba(1, 1, 1, 0.08); c.rectangle(1045, y + 7, 415, 11); c.fill()
        c.set_source_rgb(*col); c.rectangle(1045, y + 7, 415 * min(1, abs(v) / 4000), 11); c.fill()
        y += 44
    text(c, "Driven gears (on output shaft)", 1045, y, 13, DIM, True); y += 22
    for g in range(1, 6):
        v = wi / R[g]; col = mix(GOLD, GREEN, e[g])
        text(c, ORD[g], 1045, y, 13, WHITE)
        c.set_source_rgba(1, 1, 1, 0.08); c.rectangle(1085, y - 9, 300, 9); c.fill()
        c.set_source_rgb(*col); c.rectangle(1085, y - 9, 300 * min(1, v / 4000), 9); c.fill()
        text(c, f"{v:,.0f}", 1440, y, 13, WHITE, align='r')
        if e[g] > 0.99: text(c, "◆", 1458, y, 13, ORANGE)
        y += 21
    text(c, "MA/5N tooth counts · final drive 14×60", 1045, 1055, 12, DIM)
    # lever
    rrect(c, 1490, 720, 200, 345, 10); c.set_source_rgb(*PANEL); c.fill()
    text(c, "GEAR LEVER", 1590, 750, 16, DIM, True, 'c')
    cx, cy = 1590, 860
    c.set_source_rgba(1, 1, 1, 0.35); c.set_line_width(10); c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.move_to(cx - 55, cy); c.line_to(cx + 55, cy); c.stroke()
    for gx_, (up_, dn) in ((-55, ("1", "2")), (0, ("3", "4")), (55, ("5", "R"))):
        c.move_to(cx + gx_, cy - 62); c.line_to(cx + gx_, cy + 62); c.stroke()
        text(c, up_, cx + gx_, cy - 74, 16, WHITE, True, 'c'); text(c, dn, cx + gx_, cy + 88, 16, WHITE, True, 'c')
    c.set_line_cap(cairo.LINE_CAP_BUTT)
    pl = kf(t, PLANE)
    if pl < -0.5: v = U['A']['xs'] / 137
    elif pl > 0.5: v = U['C']['xs'] / 137 + ri(t)
    else: v = U['B']['xs'] / 137
    kx, ky = cx + 55 * pl, cy + 62 * v
    c.arc(kx, ky, 14, 0, 2 * math.pi); c.set_source_rgb(*ORANGE); c.fill()
    c.arc(kx - 4, ky - 4, 5, 0, 2 * math.pi); c.set_source_rgba(1, 1, 1, 0.5); c.fill()
    gname = "neutral"
    for g in e:
        if e[g] > 0.99: gname = ORD[g]
    if ri(t) > 0.99: gname = "reverse"
    text(c, gname.upper(), 1590, 1003, 20, ORANGE, True, 'c')
    sp = kmh(wo)
    text(c, f"{abs(sp):.0f} km/h" + (" ◀ backwards" if sp < -0.5 else ""), 1590, 1035, 15, WHITE, True, 'c')
    # pedals
    rrect(c, 1700, 720, 200, 345, 10); c.set_source_rgb(*PANEL); c.fill()
    text(c, "PEDALS", 1800, 750, 16, DIM, True, 'c')
    cl = clutch(t); px, py = 1760, 790
    angl = math.radians(15 + 40 * cl); ex, ey = px + 75 * math.sin(angl), py + 150 * math.cos(angl)
    c.set_source_rgb(0.7, 0.7, 0.75); c.set_line_width(6); c.move_to(px, py); c.line_to(ex, ey); c.stroke()
    rrect(c, ex - 22, ey - 6, 44, 14, 4); c.set_source_rgb(*(ORANGE if cl > 0.5 else GREY)); c.fill()
    text(c, "clutch", 1760, 990, 14, WHITE, align='c')
    text(c, "PRESSED" if cl > 0.5 else "released", 1760, 1010, 13, ORANGE if cl > 0.5 else DIM, True, 'c')
    th = throttle(t)
    c.set_source_rgba(1, 1, 1, 0.1); c.rectangle(1840, 800, 22, 170); c.fill()
    c.set_source_rgb(0.35, 0.8, 0.45); c.rectangle(1840, 970 - 170 * th, 22, 170 * th); c.fill()
    text(c, "throttle", 1851, 990, 14, WHITE, align='c')

def header(c, t):
    c.set_source_rgb(0.04, 0.05, 0.07); c.rectangle(0, 0, W, 70); c.fill()
    text(c, "CITROËN MA/5 MANUAL GEARBOX", 24, 44, 26, WHITE, True)
    text(c, "N → 1 → 2 → 3 → 4 → 5 → N → R → N", 560, 44, 22, ORANGE, True)
    if slowmo(t):
        rrect(c, 1540, 16, 360, 38, 8); c.set_source_rgba(0.9, 0.2, 0.2, 0.9); c.fill()
        text(c, "SLOW MOTION — real shift < 1 s", 1720, 41, 16, WHITE, True, 'c')
    elif COMPRESS[0] < t < COMPRESS[1]:
        rrect(c, 1540, 16, 360, 38, 8); c.set_source_rgba(0.2, 0.4, 0.9, 0.9); c.fill()
        text(c, "TIME COMPRESSED", 1720, 41, 16, WHITE, True, 'c')

def overlay_card(c, alpha, lines, y=300):
    c.set_source_rgba(0.03, 0.04, 0.06, 0.88 * alpha); c.rectangle(0, 0, W, H); c.fill()
    for s, size, col, bold in lines:
        if s.startswith("•"): y = wrap(c, s, 420, y, 1080, size, col, 1.35, bold, alpha) + 8
        else: text(c, s, W / 2, y, size, col, bold, 'c', alpha); y += size * 1.7

def frame(c, t):
    c.set_source_rgb(*BG); c.paint()
    U, e = all_state(t)
    header(c, t); side_view(c, t, U, e); closeup(c, t, U, e); hud(c, t, U, e)
    if t < 5:
        a = 1 if t < 4.3 else (5 - t) / 0.7
        overlay_card(c, a, [
            ("CITROËN MA/5 GEARBOX", 54, WHITE, True),
            ("All five gears, neutral and reverse", 30, ORANGE, True),
            ("", 10, WHITE, False),
            ("Schematic animation: layout simplified and not to scale.", 20, DIM, False),
            ("Gear ratios from MA/5N tooth counts: 1st 41/12 · 2nd 38/21 · 3rd 41/32 · 4th 39/40 · 5th 33/43 · reverse 43/12.", 20, DIM, False),
            ("Road speeds: final drive 14×60 and 1.67 m tyre (Saxo 1.1i, from your handbook).", 20, DIM, False),
            ("Gear changes are shown in slow motion.", 20, DIM, False)], 330)
    if t > END:
        a = min(1, (t - END) / 0.6)
        overlay_card(c, a, [
            ("KEY POINTS", 44, ORANGE, True),
            ("• All five forward gear pairs are always in mesh. Engaging a gear means locking its free driven gear to the output shaft with a sliding sleeve.", 24, WHITE, False),
            ("• On the MA all three synchronisers (1/2, 3/4, 5th) sit on the output shaft; every drive gear on the input shaft is fixed.", 24, WHITE, False),
            ("• A synchroniser matches speeds by cone friction before the dog teeth mesh. On upshifts it slows the input shaft; from rest into 1st it stops it.", 24, WHITE, False),
            ("• Reverse uses a sliding straight-cut idler and has no synchroniser: stop the car, wait for the input shaft to stop, then engage.", 24, WHITE, False),
            ("• Lever planes: left = 1/2, centre = 3/4 (rest position), right = 5/R.", 24, WHITE, False)], 260)

def main():
    out = sys.argv[1]; only = sys.argv[2:]
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H); c = cairo.Context(surf)
    if only:
        for s in only:
            frame(c, float(s)); surf.write_to_png(f"{out}_{s}.png")
        return
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                          "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    for i in range(NF):
        frame(c, i / FPS); surf.flush(); p.stdin.write(bytes(surf.get_data()))
    p.stdin.close(); p.wait()

if __name__ == "__main__":
    main()
