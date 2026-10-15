# Gearbox Simulator

**Shift Lab**: drive a 5-speed manual gearbox in your browser and watch what happens inside it.

**▶ Live: https://gear.bombo.fun**

You work the clutch, throttle, brake and an H-pattern gear lever. A live cutaway shows the shafts, synchronisers, blocker rings, dog teeth, reverse idler and power flow, with real gear ratios for each car.

## Cars

| Car | Gearbox | Page |
|---|---|---|
| Citroën Saxo 1.1i (TU1JP, 60 hp) | PSA MA/5 | [/saxo](https://gear.bombo.fun/saxo) |
| VW Polo 3 (6N2) 1.0 (AUC, 50 hp) | VW 085 | [/polo](https://gear.bombo.fun/polo) |
| Opel Corsa B 1.2 16V (X12XE, 65 hp) | Opel F13 | [/corsa](https://gear.bombo.fun/corsa) |
| Geely GX3 2022 1.5 (JLγ-4G15, 102 hp) | Geely S170B2 (estimated ratios) | [/gx3](https://gear.bombo.fun/gx3) |

## Controls

| Key | Action |
|---|---|
| `E` | start / stop the engine |
| `Space` | hold to press the clutch (it comes up smoothly when released) |
| `W` / `↑` | throttle |
| `S` / `↓` | brake |
| `1`–`5`, `R`, `N` | move the gear lever (or drag the knob) |
| `M` | sound on / off |

With a mouse or touch screen only, the pedals work as sliders.

## What it simulates

- **Synchronisers:** the blocker ring holds the sleeve until cone friction matches the gear's speed to the shaft, then the sleeve slides onto the dog teeth.
- **Clutch:** slip, bite point, heat, and engine speed pulled up or down to the input shaft.
- **Physics:** engine torque curve, gear and final-drive ratios, tyre size, car mass, rolling and air resistance, brakes.
- **Mistakes:**
  - shifting without the clutch (grinding);
  - reverse while rolling, or before the input shaft has stopped;
  - pulling out of gear under load;
  - stalling (dropping the clutch, pulling away in 3rd, braking to a stop in gear);
  - over-revving on a downshift;
  - lugging and clutch overheating;
  - the Saxo's 5th → reverse lockout.

## Run locally

No build step and no dependencies. Serve the folder and open a car page:

```bash
python -m http.server 8000
# then open http://localhost:8000/saxo/ (or /polo/, /corsa/, /gx3/)
```

## Project layout

| Path | Purpose |
|---|---|
| `index.html` | car chooser (home page) |
| `saxo/`, `polo/`, `corsa/`, `gx3/` | one simulator page per car |
| `cars.js` | per-car data: ratios, tooth counts, final drive, tyre, mass, torque curve, synchro layout, lever gate, colours and side silhouette |
| `shiftlab.js`, `shiftlab.css` | shared simulator engine and styles |
| `vercel.json` | clean URLs (`/saxo`, `/polo`, …) |
| `scripts/` | Python scripts that render the MA/5 explainer videos |

### Adding a car

1. Add an entry to `cars.js`. Copy an existing one and change the ratios, final drive, tyre, mass, torque curve, which shaft each synchroniser sits on (`units`), the lever gate (`planes`, `rev`) and the body `shape`.
2. Copy one of the car folders, then change its `<title>`, subtitle and `window.SHIFTLAB_CAR`.
3. Add the car to the switcher on every page and a card on `index.html`.

## Animations

`scripts/` renders two explainer videos of the MA/5 gearbox (pycairo + ffmpeg):

- `render_neutral_1_2.py`: neutral → 1st → 2nd
- `render_all_gears.py`: all five gears, neutral and reverse

```bash
pip install pycairo
python scripts/render_all_gears.py MA5_all_gears.mp4
```

## Data and sources

| Car | Confirmed | Estimated or assumed |
|---|---|---|
| **Saxo** | MA/5N tooth counts (1st 12×41, 2nd 21×38, 3rd 32×41, 4th 40×39, 5th 43×33, R 12×43); final drive 14×60 and 1.67 m tyre (Saxo 1.1i handbook); all three synchros on the output shaft; reverse idler meshing with teeth on the 1/2 sleeve | n/a |
| **Polo** | 085 gearbox, codes DKG / DXD / ESY / FFE: 3.455 / 2.095 / 1.448 / 1.098 / 0.891, final drive 4.063; engine AUC/ALD 50 hp, 86 N·m; tyre 155/70 R13 | reverse ratio (≈ 3.2); 3/4 and 5th synchros on the input shaft (from teardown reports, not a VW manual) |
| **Corsa** | F13 gearbox (code C374, final drive 3.74); ratios 3.727 / 2.136 / 1.414 / 1.121 / 0.892, R 3.308; X12XE 65 hp, 110 N·m; 165/70 R13; gate with reverse far left and forward (So wird's gemacht, Band 90) | synchro layout (the manual doesn't cover gearbox internals) |
| **GX3** | engine JLγ-4G15 1.5, ~102 hp, 142 N·m; 1180 kg; 205/60 R16; gearbox S170B2; reverse right of 5th, back | all gear ratios (3.545 / 1.913 / 1.310 / 0.971 / 0.795), final drive (4.294) and synchro layout: not published by Geely |

For every car, the torque curves, clutch and synchro capacities and drag figures are approximations, and the drawings are schematic, not to scale.
