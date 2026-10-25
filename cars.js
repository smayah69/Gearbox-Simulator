// Car configurations for the Shift Lab simulator.
// Ratios are input-shaft turns per output-shaft turn; Z = [drive teeth, driven teeth] (used for drawing).
window.SHIFTLAB_CARS = {
  saxo: {
    id: "saxo",
    name: "Citroën Saxo 1.1i",
    gearbox: "PSA MA/5",
    // MA/5N tooth counts
    Z: {1:[12,41], 2:[21,38], 3:[32,41], 4:[40,39], 5:[43,33]},
    ratio: {1:41/12, 2:38/21, 3:41/32, 4:39/40, 5:33/43, R:-43/12},
    fd: 60/14, fdTeeth: [14,60],            // final drive 14x60 (Saxo 1.1i, 20 CF 03)
    tyre: 1.67,                             // m, 155/70 R13
    mass: 960, cda: 0.61, clutchCap: 170, limit: 6300,
    // TU1JP 1.1 8v, approximate full-throttle torque curve (rpm, N·m)
    tq: [[0,0],[400,30],[800,62],[1500,74],[2500,84],[3400,90],[4500,86],[5500,76],[6300,64],[7200,45]],
    // nitrous kit (game add-on): extra N·m at full throttle, seconds per bottle, seconds to refill
    nos: {tq:70, time:7, refill:20},
    // engine sound: TU1JP 8v, buzzy and raspy with overrun pops
    sound: {wave:"sawtooth", sub:0.45, harm:[2,0.25,"square"], cutoff:520, open:1900, q:5, drive:0.35, rasp:0.10, raspHz:1400, burble:0.22, whine:0, pops:0.6, starter:36, vol:1},
    // all three synchronisers on the output shaft
    units: { A:{shaft:"out", gears:{"-1":1,"1":2}}, B:{shaft:"out", gears:{"-1":3,"1":4}}, C:{shaft:"out", gears:{"-1":5}} },
    planes: { "-1":{unit:"A",up:1,down:2}, "0":{unit:"B",up:3,down:4}, "1":{unit:"C",up:5,down:"R"} },
    rev: {plane:1, dir:1},
    lockout5R: true,
    lockoutText: "The MA gate stops you going straight from 5th into reverse. Move the lever back to the centre plane first.",
    revHint: "Reverse: right plane, then back. A lockout blocks 5th → R.",
    endHousing: "5th-gear end housing",
    inNote: "all drive gears fixed",
    outNote: "3 synchros",
    // side silhouette (nose to the right), SVG path data; 5-door Saxo
    shape: {
      shell: "M-58 10 L-58 -8 Q-58 -12 -55 -13 L-47 -27 Q-45 -30 -40 -30 L-2 -30 Q3 -30 6 -27 L24 -12 Q42 -9 53 -6 Q58 -4 58 1 L58 10 Q58 13 55 13 L-55 13 Q-58 13 -58 10 Z",
      glass: ["M-48 -14 L-42 -26 L-13 -26 L-13 -14 Z", "M-9 -14 L-9 -26 L0 -26 Q3 -26 5 -24 L18 -14 Z"],
      lines: "M-11 -12 L-11 11 M-41 -12 Q-43 0 -39 10 M21 -12 L20 6 M-37 -26 L-38 -14",
      strip: "M-55 0 L22 0",
      lamp: "M48 -7 L56 -5 L57 -1 L47 -2 Z",
      tail: "M-58 -11 L-56 -12 L-56 -3 L-58 -3 Z",
    },
    body: "saxo", colour: "#1d3b78", edge: "#0d1c3d", faceInk: "#ffffff",
  },
  polo: {
    id: "polo",
    name: "VW Polo 3 (6N2) 1.0",
    gearbox: "VW 085",
    // 085 gearbox, codes DKG / DXD / ESY / FFE (1.0 37 kW)
    Z: {1:[11,38], 2:[21,44], 3:[29,42], 4:[41,45], 5:[46,41]},
    ratio: {1:38/11, 2:44/21, 3:42/29, 4:45/41, 5:41/46, R:-3.18},   // reverse ratio estimated
    fd: 65/16, fdTeeth: [16,65],            // final drive 65:16 = 4.063
    tyre: 1.67,                             // m, 155/70 R13
    mass: 1057, cda: 0.67, clutchCap: 170, limit: 6000,
    // AUC / ALD 1.0 8v: 50 hp at 5000 rpm, 86 N·m at 3000-3600 rpm (approximate curve)
    tq: [[0,0],[400,30],[800,62],[1500,74],[2500,82],[3000,86],[3600,86],[4300,80],[5000,72],[5700,60],[6500,42]],
    // nitrous kit (game add-on): extra N·m at full throttle, seconds per bottle, seconds to refill
    nos: {tq:65, time:7, refill:20},
    // engine sound: AUC 1.0 8v, low and thrummy, lumpy at idle
    sound: {wave:"square", sub:0.7, harm:[1.5,0.2,"triangle"], cutoff:360, open:1100, q:3, drive:0.2, rasp:0.04, raspHz:700, burble:0.4, whine:0, pops:0.15, starter:30, vol:1.05},
    // 1/2 synchro on the output shaft (its sleeve carries the reverse teeth); 3/4 and 5th on the input shaft
    units: { A:{shaft:"out", gears:{"-1":1,"1":2}}, B:{shaft:"in", gears:{"-1":3,"1":4}}, C:{shaft:"in", gears:{"-1":5}} },
    planes: { "-2":{up:"R",down:null}, "-1":{unit:"A",up:1,down:2}, "0":{unit:"B",up:3,down:4}, "1":{unit:"C",up:5,down:null} },
    rev: {plane:-2, dir:-1},
    lockout5R: false,
    lockoutText: "",
    revHint: "Reverse: far-left plane, then forward.",
    endHousing: "5th gear in the end cover",
    inNote: "3/4 + 5th synchros",
    outNote: "1/2 synchro + R teeth",
    // side silhouette (nose to the right), SVG path data; 5-door Polo 6N2
    shape: {
      shell: "M-58 10 L-58 -12 Q-58 -15 -57 -17 L-54 -30 Q-53 -33 -48 -33 L0 -33 Q4 -33 7 -30 L24 -14 Q40 -11 52 -8 Q58 -6 58 -1 L58 10 Q58 13 55 13 L-55 13 Q-58 13 -58 10 Z",
      glass: ["M-41 -16 L-39 -29 L-12 -29 L-12 -16 Z", "M-8 -16 L-8 -29 L-1 -29 Q2 -29 4 -27 L18 -16 Z"],
      lines: "M-10 -14 L-10 11 M-42 -14 Q-44 0 -41 11 M20 -14 L19 6",
      strip: "M-55 -1 L20 -1",
      lamp: "M43 -9 Q52 -9 57 -6 L57 -3 Q50 -4 43 -5 Z",
      tail: "M-58 -15 L-56 -15 L-56 -5 L-58 -5 Z",
    },
    body: "polo", colour: "#f4f5f2", edge: "#7d8798", faceInk: "#1f2a3c",
  },
  corsa: {
    id: "corsa",
    name: "Opel Corsa B 1.2 16V",
    gearbox: "Opel F13",
    // F13 5-speed; drawing tooth counts chosen to match the ratios
    Z: {1:[11,41], 2:[22,47], 3:[29,41], 4:[33,37], 5:[37,33]},
    ratio: {1:3.727, 2:2.136, 3:1.414, 4:1.121, 5:0.892, R:-3.308},
    fd: 3.74, fdTeeth: [19,71],             // F13 C374: final drive 3.74
    tyre: 1.72,                             // m, 165/70 R13
    mass: 960, cda: 0.64, clutchCap: 190, limit: 6400,
    // X12XE Ecotec 1.2 16v: 65 hp at 5600 rpm, 110 N·m at 4000 rpm (approximate curve)
    tq: [[0,0],[400,32],[800,70],[1500,86],[2500,96],[3200,102],[4000,110],[5000,101],[5600,82],[6400,66],[7000,50]],
    // nitrous kit (game add-on): extra N·m at full throttle, seconds per bottle, seconds to refill
    nos: {tq:80, time:7, refill:20},
    // engine sound: X12XE 16v, revvy with a bright top end and intake roar
    sound: {wave:"sawtooth", sub:0.3, harm:[2,0.35,"sawtooth"], cutoff:700, open:2600, q:6, drive:0.45, rasp:0.07, raspHz:2200, burble:0.12, whine:0.035, whineMul:4, pops:0.35, starter:42, vol:0.95},
    // layout assumed like other transverse 5-speeds of its era (the So wird's gemacht manual doesn't cover F13 internals)
    units: { A:{shaft:"out", gears:{"-1":1,"1":2}}, B:{shaft:"in", gears:{"-1":3,"1":4}}, C:{shaft:"in", gears:{"-1":5}} },
    planes: { "-2":{up:"R",down:null}, "-1":{unit:"A",up:1,down:2}, "0":{unit:"B",up:3,down:4}, "1":{unit:"C",up:5,down:null} },
    rev: {plane:-2, dir:-1},
    lockout5R: false,
    lockoutText: "",
    revHint: "Reverse: lift the ring under the knob, then far left and forward.",
    endHousing: "5th gear in the end cover",
    inNote: "3/4 + 5th synchros",
    outNote: "1/2 synchro + R teeth",
    // side silhouette (nose to the right), SVG path data; 5-door Corsa B
    shape: {
      shell: "M-44 -15 H44 A13 13 0 0 1 57 -2 V-1 A13 13 0 0 1 44 12 H-44 A13 13 0 0 1 -57 -1 V-2 A13 13 0 0 1 -44 -15 Z M-53 -14 Q-54 -36 -40 -43 Q-14 -50 10 -44 Q20 -40 38 -15 Z",
      glass: ["M-47 -18 Q-47 -34 -37 -39 L-19 -41 L-19 -18 Z", "M-14 -18 L-14 -42 Q2 -43 10 -39 Q18 -33 29 -18 Z"],
      lines: "M-16 -13 L-16 8 M-42 -13 L-40 6 M14 -13 L14 8",
      strip: "",
      lamp: "M47 -9 Q56 -9 57 -3 L47 -2 Z",
      tail: "",
    },
    body: "corsa", colour: "#f6f6f3", edge: "#7d8798", faceInk: "#1f2a3c",
  },
  gx3: {
    id: "gx3",
    name: "Geely GX3 2022 1.5",
    gearbox: "Geely S170B2",
    // ESTIMATED ratios: the S170B2 ratios are not published; typical 1.5 L compact-SUV values
    Z: {1:[11,39], 2:[23,44], 3:[29,38], 4:[35,34], 5:[39,31]},
    ratio: {1:3.545, 2:1.913, 3:1.310, 4:0.971, 5:0.795, R:-3.25},
    fd: 4.294, fdTeeth: [17,73],            // estimated
    tyre: 1.99,                             // m, 205/60 R16
    mass: 1255, cda: 0.72, clutchCap: 240, limit: 6400,
    // JLγ-4G15 1.5 16v: about 102 hp at 5600 rpm, 142 N·m at 4400 rpm (approximate curve)
    tq: [[0,0],[400,45],[800,95],[1500,112],[2500,124],[3500,134],[4400,142],[5000,138],[5600,128],[6200,110],[6800,85]],
    // nitrous kit (game add-on): extra N·m at full throttle, seconds per bottle, seconds to refill
    nos: {tq:95, time:8, refill:20},
    // engine sound: JLγ-4G15, smooth and muted, a faint chain whine
    sound: {wave:"triangle", sub:0.55, harm:[2,0.18,"sine"], cutoff:440, open:1300, q:1.5, drive:0.08, rasp:0.02, raspHz:900, burble:0.06, whine:0.03, whineMul:7, pops:0, starter:48, vol:0.85},
    // synchro layout assumed (not published for the S170B2)
    units: { A:{shaft:"out", gears:{"-1":1,"1":2}}, B:{shaft:"in", gears:{"-1":3,"1":4}}, C:{shaft:"in", gears:{"-1":5}} },
    planes: { "-1":{unit:"A",up:1,down:2}, "0":{unit:"B",up:3,down:4}, "1":{unit:"C",up:5,down:"R"} },
    rev: {plane:1, dir:1},
    lockout5R: false,
    lockoutText: "",
    revHint: "Reverse: right plane, then back.",
    endHousing: "5th gear in the end cover",
    inNote: "3/4 + 5th synchros (assumed)",
    outNote: "1/2 synchro (assumed)",
    // side silhouette (nose to the right), SVG path data; compact crossover
    shape: {
      shell: "M-58 6 L-58 -12 Q-58 -16 -56 -18 L-50 -33 Q-47 -38 -40 -38 L0 -38 Q6 -38 10 -34 L26 -18 Q42 -15 53 -12 Q58 -10 58 -4 L58 6 Q58 10 54 10 L-54 10 Q-58 10 -58 6 Z",
      glass: ["M-48 -20 L-43 -33 L-14 -34 L-14 -20 Z", "M-10 -20 L-10 -34 L-1 -34 Q4 -34 7 -31 L20 -20 Z"],
      lines: "M-12 -18 L-12 6 M-44 -18 Q-46 -6 -43 4 M22 -18 L21 2 M-39 -33 L-41 -20",
      strip: "M-55 5 L55 5",
      lamp: "M44 -13 L57 -9 L57 -6 L46 -9 Z",
      tail: "M-58 -17 L-55 -18 L-55 -9 L-58 -9 Z",
    },
    body: "gx3", colour: "#f7f7f5", edge: "#7d8798", faceInk: "#1f2a3c",
  },
};
