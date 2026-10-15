# Gearbox MA/5

**Live demo: https://gear.bombo.fun**

Interactive simulator and animations of the PSA **MA/5** 5-speed manual gearbox (Citroën Saxo / Xsara, Peugeot 106 / 206).

## Shift Lab (web app)

Play it at **https://gear.bombo.fun**:

- [`/saxo`](https://gear.bombo.fun/saxo): Citroën Saxo 1.1i, PSA MA/5 gearbox
- [`/polo`](https://gear.bombo.fun/polo): VW Polo 3 (6N) 1.4, VW 085 gearbox
- [`/corsa`](https://gear.bombo.fun/corsa): Opel Corsa B 1.2 16V, Opel F13 gearbox

No build step, no dependencies. To run it locally, serve the folder (for example `python -m http.server`) and open `/saxo/`, `/polo/` or `/corsa/`.

You drive the car with the clutch, throttle, brake and an H-pattern lever, and a live cutaway shows what happens inside: synchronisers, blocker rings, dog teeth, the reverse idler and the power flow.

| Key | Action |
|---|---|
| `E` | start / stop the engine |
| `Space` | hold to press the clutch |
| `W` / `↑` | throttle |
| `S` / `↓` | brake |
| `1`–`5`, `R`, `N` | select a gear (or drag the lever knob) |
| `M` | sound on / off |

Mouse or touch only: the pedals work as sliders.

Mistakes are simulated: shifting without the clutch (grinding), reverse while rolling or before the input shaft stops, pulling out of gear under load, stalling, over-revving on a downshift, lugging and clutch overheating. The Saxo also has the MA's 5th → reverse lockout.

### Project layout

| File | Purpose |
|---|---|
| `index.html` | car chooser |
| `saxo/`, `polo/`, `corsa/` | simulator pages |
| `cars.js` | per-car data: ratios, tooth counts, synchro layout, lever gate, engine curve, colours |
| `shiftlab.js`, `shiftlab.css` | shared simulator engine and styles |
| `vercel.json` | clean URLs (`/saxo`, `/polo`) |

## Animations

The Python scripts in `scripts/` render explanatory videos (pycairo + ffmpeg):

- `render_neutral_1_2.py`: neutral → 1st → 2nd
- `render_all_gears.py`: all five gears, neutral and reverse

```bash
pip install pycairo
python scripts/render_all_gears.py MA5_all_gears.mp4
```

## Data and assumptions

**Citroën Saxo 1.1i (MA/5)**
- Tooth counts (MA/5N): 1st 12×41, 2nd 21×38, 3rd 32×41, 4th 40×39, 5th 43×33, reverse 12×43.
- Final drive 14×60, tyre circumference 1.67 m (Saxo 1.1i handbook).
- All three synchronisers (1/2, 3/4, 5th) on the output shaft; reverse uses a sliding straight-cut idler meshing with teeth on the 1/2 sleeve.

**VW Polo 3 (6N) 1.4 60 hp (085)**
- Gearbox codes DKF / DQW / ETD / FFR: 1st 38:11 = 3.455, 2nd 43:22 = 1.955, 3rd 40:32 = 1.250, 4th 42:45 = 0.933, 5th 37:50 = 0.740, final drive 62:16 = 3.875.
- Tyre 175/70 R13 (about 1.75 m rolling circumference); engine 60 hp at 4700 rpm, 116 N·m at 3000 rpm.
- Synchro layout: 1/2 on the output shaft with the straight reverse teeth on its sleeve; 3/4 and 5th on the input shaft; 5th gear in the end cover. Inferred from teardown reports, not from the VW repair manual.
- The reverse ratio (≈ 3.2) and the reverse gate position are estimates.

**Opel Corsa B 1.2 16V (F13)**
- Engine X12XE: 65 hp at 5600 rpm, 110 N·m at 4000 rpm; tyre 165/70 R13 (about 1.72 m).
- F13 ratios: 3.727 / 2.136 / 1.414 / 1.121 / 0.892, reverse 3.308; final drive 3.74 (gearbox code F13 C374).
- Confirmed in the Corsa B workshop manual (So wird's gemacht, Band 90): F13 gearbox, X12XE engine data, 165/70 R13 tyre option, and the gate with reverse far left and forward of 1st.
- Reverse: lift the ring under the knob, far left and forward.
- Synchro layout (1/2 on the output shaft, 3/4 and 5th on the input shaft) is assumed: that manual doesn't cover gearbox internals.

**All cars**
- Engine torque curves, vehicle mass and synchro/clutch capacities are approximations.
- Drawings are schematic and not to scale.
