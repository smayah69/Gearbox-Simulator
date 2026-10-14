# Gearbox MA/5

**Live demo: https://gear.bombo.fun**

Interactive simulator and animations of the PSA **MA/5** 5-speed manual gearbox (Citroën Saxo / Xsara, Peugeot 106 / 206).

## MA/5 Shift Lab (web app)

Play it at **https://gear.bombo.fun**, or open `index.html` in a browser. No build step, no dependencies.

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

Mistakes are simulated: shifting without the clutch (grinding), reverse while rolling or before the input shaft stops, pulling out of gear under load, stalling, over-revving on a downshift, the 5th → reverse lockout, lugging and clutch overheating.

## Animations

The Python scripts in `scripts/` render explanatory videos (pycairo + ffmpeg):

- `render_neutral_1_2.py`: neutral → 1st → 2nd
- `render_all_gears.py`: all five gears, neutral and reverse

```bash
pip install pycairo
python scripts/render_all_gears.py MA5_all_gears.mp4
```

## Data and assumptions

- Gear tooth counts (MA/5N): 1st 12×41, 2nd 21×38, 3rd 32×41, 4th 40×39, 5th 43×33, reverse 12×43.
- Final drive 14×60 and 1.67 m tyre circumference (Saxo 1.1i).
- All three synchronisers (1/2, 3/4, 5th) sit on the output shaft; reverse uses a sliding straight-cut idler meshing with teeth on the 1/2 sleeve.
- Engine torque curve, vehicle mass and synchro/clutch capacities are approximations.
- Drawings are schematic and not to scale.
