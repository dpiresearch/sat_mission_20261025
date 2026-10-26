// Interactive 3D mockup of the DPI LTM CubeSat (1U PROVES Kit + AMSAT LTM-1).
// Units are millimetres. CubeSat +Z (antenna cap) maps to three.js +Y.
import * as THREE from "three";
import { OrbitControls } from "./vendor/OrbitControls.js";

const host = document.getElementById("mockup");
const tip = document.getElementById("mockup-tip");
const labelLayer = document.getElementById("mockup-labels");

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, 1, 1, 5000);
camera.position.set(260, 190, 300);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
host.appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 60, 0);
controls.enableDamping = true;
controls.autoRotate = true;
controls.autoRotateSpeed = 0.8;

scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 2.2);
sun.position.set(300, 500, 200);
scene.add(sun);
const fill = new THREE.DirectionalLight(0x9fb8ff, 0.6);
fill.position.set(-300, 100, -250);
scene.add(fill);

// ------------------------------------------------------------------ materials
const M = {
  alu: new THREE.MeshStandardMaterial({ color: 0xb9bec6, metalness: 0.85, roughness: 0.35 }),
  aluDark: new THREE.MeshStandardMaterial({ color: 0x8b9099, metalness: 0.8, roughness: 0.45 }),
  pcbBlack: new THREE.MeshStandardMaterial({ color: 0x1b1d22, roughness: 0.6 }),
  pcbGreen: new THREE.MeshStandardMaterial({ color: 0x1d6b3a, roughness: 0.55 }),
  pcbBlue: new THREE.MeshStandardMaterial({ color: 0x1f3f7a, roughness: 0.55 }),
  chip: new THREE.MeshStandardMaterial({ color: 0x15161a, roughness: 0.4 }),
  shield: new THREE.MeshStandardMaterial({ color: 0xd6d9de, metalness: 0.9, roughness: 0.25 }),
  gold: new THREE.MeshStandardMaterial({ color: 0xd4a640, metalness: 0.9, roughness: 0.3 }),
  header: new THREE.MeshStandardMaterial({ color: 0x222222, roughness: 0.7 }),
  cell: new THREE.MeshStandardMaterial({ color: 0x18213d, metalness: 0.4, roughness: 0.25 }),
  battery: new THREE.MeshStandardMaterial({ color: 0x2e7dd1, roughness: 0.4, metalness: 0.2 }),
  batteryCap: new THREE.MeshStandardMaterial({ color: 0xc9ccd1, metalness: 0.9, roughness: 0.3 }),
  tape: new THREE.MeshStandardMaterial({ color: 0xe0e3e8, metalness: 0.8, roughness: 0.3 }),
  tapeV: new THREE.MeshStandardMaterial({ color: 0xeb6834, metalness: 0.3, roughness: 0.4, transparent: true, opacity: 0.9 }),
  coaxTx: new THREE.MeshStandardMaterial({ color: 0x2a78d6, roughness: 0.5 }),
  coaxRx: new THREE.MeshStandardMaterial({ color: 0xeb6834, roughness: 0.5 }),
  ribbon: new THREE.MeshStandardMaterial({ color: 0x7a7a7a, roughness: 0.8 }),
  nylon: new THREE.MeshStandardMaterial({ color: 0xf2f0ea, roughness: 0.9 }),
  usb: new THREE.MeshStandardMaterial({ color: 0xaaaaaa, metalness: 0.9, roughness: 0.3 }),
};

// solar cell texture: dark cell with fine silver grid fingers and two busbars
function cellTexture() {
  const c = document.createElement("canvas");
  c.width = 128; c.height = 256;
  const g = c.getContext("2d");
  g.fillStyle = "#1a2444"; g.fillRect(0, 0, 128, 256);
  g.strokeStyle = "rgba(200,210,230,0.35)"; g.lineWidth = 1;
  for (let y = 6; y < 256; y += 8) { g.beginPath(); g.moveTo(0, y); g.lineTo(128, y); g.stroke(); }
  g.fillStyle = "rgba(220,225,235,0.8)"; g.fillRect(40, 0, 4, 256); g.fillRect(84, 0, 4, 256);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
M.cell.map = cellTexture();

function textTexture(text, bg = "#1d6b3a", fg = "#f2f2f2") {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 128;
  const g = c.getContext("2d");
  g.fillStyle = bg; g.fillRect(0, 0, 512, 128);
  g.fillStyle = fg; g.font = "bold 44px Helvetica, Arial, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText(text, 256, 64);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// ------------------------------------------------------------------ helpers
const parts = [];          // {group, info, home: Vector3, explode: Vector3}
const pickables = [];
const labels = [];

function box(w, h, d, mat) { return new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); }
function cyl(r, h, mat, seg = 24) { return new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, seg), mat); }

function part(name, desc, explodeOffset, build, labelAnchor, internal = false) {
  const g = new THREE.Group();
  build(g);
  g.userData = { name, desc };
  g.traverse((o) => { if (o.isMesh) { o.userData.part = g; pickables.push(o); } });
  scene.add(g);
  const rec = { group: g, home: g.position.clone(), explode: new THREE.Vector3(...explodeOffset) };
  parts.push(rec);
  if (labelAnchor) addLabel(name, g, new THREE.Vector3(...labelAnchor), internal);
  return rec;
}

function addLabel(text, obj, local, internal = false) {
  const el = document.createElement("div");
  el.className = "mockup-label";
  el.textContent = text;
  labelLayer.appendChild(el);
  labels.push({ el, obj, local, internal });
}

// small board furniture
function chipOn(g, x, y, z, w, d, h = 1.4, mat = M.chip) { const m = box(w, h, d, mat); m.position.set(x, y + h / 2, z); g.add(m); return m; }
function standoffs(g, y0, h, inset = 41) {
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
    const s = cyl(1.8, h, M.gold, 6); s.position.set(sx * inset, y0 + h / 2, sz * inset); g.add(s);
  }
}

const H = 113.5, W = 100;
const RAIL = 8.5;

// ------------------------------------------------------------------ structure
part("PROVES 1U structure", "1.6 mm 5052 aluminium half-U panels and brackets, PA-12 feet, M2.5 fasteners. 100 × 100 × 113.5 mm.",
  [0, 0, 0], (g) => {
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
      const r = box(RAIL, H, RAIL, M.alu);
      r.position.set(sx * (W / 2 - RAIL / 2), H / 2, sz * (W / 2 - RAIL / 2));
      g.add(r);
      // feet (rail ends) in nylon
      for (const y of [-3.5, H + 3.5]) { const f = box(RAIL, 7, RAIL, M.nylon); f.position.set(r.position.x, y, r.position.z); g.add(f); }
    }
    // horizontal frame members top and bottom
    for (const y of [2, H - 2]) for (const [sx, sz, w, d] of [[0, 1, W - 2 * RAIL, 4], [0, -1, W - 2 * RAIL, 4], [1, 0, 4, W - 2 * RAIL], [-1, 0, 4, W - 2 * RAIL]]) {
      const b = box(w, 4, d, M.aluDark); b.position.set(sx * (W / 2 - 2), y, sz * (W / 2 - 2)); g.add(b);
    }
  }, [W / 2, H + 12, W / 2]);

// ------------------------------------------------------------------ internal stack
const batt = part("Battery pack v2", "PROVES battery_pack_v2: 4 × 18650 Li-ion cells in 2S2P (~48 Wh, 7.2 V nominal), R5460 protector, TMP112 sensors. Heaviest item, mounted low.",
  [0, -70, 0], (g) => {
    const b = box(90, 1.6, 90, M.pcbBlack); b.position.y = 12; g.add(b);
    for (let i = 0; i < 4; i++) {
      const c = cyl(9, 65, M.battery); c.rotation.z = Math.PI / 2; c.position.set(0, 12 + 1.6 + 9.2, -30 + i * 20); g.add(c);
      for (const sx of [-1, 1]) { const cap = cyl(9.05, 1.2, M.batteryCap); cap.rotation.z = Math.PI / 2; cap.position.set(sx * 32.5, c.position.y, c.position.z); g.add(cap); }
    }
    standoffs(g, 13.6, 20);
  }, [-45, 34, 45], true);

const fc = part("Flight controller (FC V5d LTM)", "Modified PROVES V5d: RP2350 MCU, IMU + magnetometer, RTC, SD NAND, LT3652 solar charger, 3.3 V and switched 5 V LTM rails, MCP25625 CAN controller, J30 harness connector to the LTM.",
  [0, -25, 0], (g) => {
    const y = 40;
    const b = box(90, 1.6, 90, M.pcbBlack); b.position.y = y; g.add(b);
    chipOn(g, 0, y + 0.8, 0, 7, 7);                       // RP2350
    chipOn(g, 14, y + 0.8, -8, 5, 6);                     // flash
    chipOn(g, -18, y + 0.8, 14, 6, 6);                    // MCP25625 CAN
    chipOn(g, -26, y + 0.8, -22, 10, 8, 2.2, M.shield);   // DC/DC
    chipOn(g, 26, y + 0.8, 22, 4, 4);                     // IMU
    const j30 = box(16, 4, 4, M.header); j30.position.set(30, y + 2.8, -36); g.add(j30);   // J30 2x10 1.27 mm
    const pc = box(78, 7, 5, M.header); pc.position.set(0, y + 4.3, 40); g.add(pc);       // stack connector
    standoffs(g, y + 0.8, 12);
  }, [-45, 46, -45], true);

// LTM-1: three-board PC-104 stack, transponder bottom, ICR middle, LTI top. 92 x 90 x 33 mm, 130 g.
const LTM_Y0 = 56;
const ltmBoards = [
  { name: "LTM · Transponder", desc: "AMSAT LTM transponder board (bottom): 30 kHz V/u linear transponder, 144 MHz uplink, inverting 432 MHz downlink, 450 mW RF out with telemetry. RF sections under shield cans.", y: LTM_Y0, shields: [[-20, -12, 34, 30, 6], [22, 14, 30, 26, 6]], ex: 12 },
  { name: "LTM · ICR (command receiver)", desc: "AMSAT Improved Command Receiver (middle): 144 MHz-band command uplink from AMSAT and the mission ground station.", y: LTM_Y0 + 12, shields: [[-14, 6, 40, 34, 5]], ex: 34 },
  { name: "LTM · LTI (host interface)", desc: "AMSAT Linear Transponder Interface (top): microcontroller, flight software and boot loader, CAN driver to the FC, USB Mini-B umbilical, 1200 bps BPSK telemetry beacon generation.", y: LTM_Y0 + 24, shields: [], ex: 56 },
];
const ltmParts = ltmBoards.map((bd, i) => part(bd.name, bd.desc, [0, bd.ex, 0], (g) => {
  const b = box(92, 1.6, 90, M.pcbGreen); b.position.y = bd.y; g.add(b);
  // PC-104 stack-through header along the +Z (cubesat -Y) edge
  const hdr = box(80, 8.5, 5, M.header); hdr.position.set(0, bd.y + 5, 40); g.add(hdr);
  for (const [x, z, w, d, h] of bd.shields) chipOn(g, x, bd.y + 0.8, z, w, d, h, M.shield);
  if (i === 2) {
    chipOn(g, -10, bd.y + 0.8, -6, 10, 10);          // MCU
    chipOn(g, 18, bd.y + 0.8, -20, 5, 4);            // CAN transceiver
    const usb = box(8, 4, 7, M.usb); usb.position.set(-44, bd.y + 2.8, -20); g.add(usb);   // USB Mini-B
    const silk = new THREE.Mesh(new THREE.PlaneGeometry(40, 10), new THREE.MeshBasicMaterial({ map: textTexture("AMSAT LTM-1") }));
    silk.rotation.x = -Math.PI / 2; silk.position.set(14, bd.y + 0.85, 12); g.add(silk);
  }
  if (i === 0) {   // SMA/MMCX RF ports for TX and RX
    for (const [x, mat] of [[30, M.coaxTx], [38, M.coaxRx]]) { const p = cyl(2.2, 6, M.gold, 12); p.position.set(x, bd.y + 3.8, -38); g.add(p); }
  }
  if (i < 2) standoffs(g, bd.y + 0.8, 11.2, 40);
}, i === 2 ? [46, LTM_Y0 + 30, 46] : null, true));
addLabel("AMSAT LTM-1 stack", ltmParts[1].group, new THREE.Vector3(48, LTM_Y0 + 14, -46), true);

// coax leads (TX to the 70 cm antenna, RX to the 2 m element) and the J30 harness ribbon
const leads = part("RF leads + J30 harness", "Coax from the LTM transponder: blue = 432 MHz TX to the antenna top cap; orange = 144 MHz RX to the V-band element. Grey ribbon = J30 harness (power, CAN, I2C, umbilical, telemetry) from the FC to the LTM.",
  [0, 30, 0], (g) => {
    const tube = (pts, mat, r = 1.3) => {
      const curve = new THREE.CatmullRomCurve3(pts.map((p) => new THREE.Vector3(...p)));
      g.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 40, r, 8, false), mat));
    };
    tube([[30, LTM_Y0 + 6.8, -38], [32, LTM_Y0 + 20, -43], [26, LTM_Y0 + 40, -43], [20, H - 4, -36]], M.coaxTx);
    tube([[38, LTM_Y0 + 6.8, -38], [42, LTM_Y0 + 22, -42], [40, LTM_Y0 + 42, -40], [34, H - 4, -30]], M.coaxRx);
    const rib = [[30, 44.8, -36], [36, 50, -42], [40, LTM_Y0 + 30, -42], [34, LTM_Y0 + 26, -36]];
    tube(rib, M.ribbon, 1.8);
  });

// ------------------------------------------------------------------ solar panels
function solarPanel(g, withCells = true) {
  const b = box(82, 98, 1.6, M.pcbBlack); g.add(b);
  if (!withCells) return;
  for (let c = 0; c < 3; c++) for (let r = 0; r < 2; r++) {
    const cell = box(23, 42, 0.6, M.cell);
    cell.position.set(-25 + c * 25, -22 + r * 44, 1.1);
    g.add(cell);
  }
  const led = box(2, 2, 1, new THREE.MeshStandardMaterial({ color: 0x3aa0ff, emissive: 0x1050ff, emissiveIntensity: 0.6 }));
  led.position.set(36, 44, 1); g.add(led);
}
const faceDefs = [
  ["+X solar face", [W / 2 + 0.8, H / 2, 0], [0, Math.PI / 2, 0], [60, 0, 0]],
  ["−X solar face", [-W / 2 - 0.8, H / 2, 0], [0, -Math.PI / 2, 0], [-60, 0, 0]],
  ["+Y solar face", [0, H / 2, W / 2 + 0.8], [0, 0, 0], [0, 0, 60]],
  ["−Y solar face", [0, H / 2, -W / 2 - 0.8], [0, Math.PI, 0], [0, 0, -60]],
];
const panels = faceDefs.map(([n, p, r, e]) => part(n, "PROVES XY_Faces_V2a: 6 × KXOB101K08TF mono-Si cells (2s3p), MCP9808 temperature + VEML7700 light sensors, embedded PCB magnetorquer coil (DRV2605L). ~1.6 W at normal incidence (AM0).",
  e, (g) => { const s = new THREE.Group(); solarPanel(s); s.position.set(...p); s.rotation.set(...r); g.add(s); }));
const bottom = part("−Z solar face", "−Z face: 6 more cells (5 solar faces in total; +Z is the antenna cap).", [0, -110, 0], (g) => {
  const s = new THREE.Group(); solarPanel(s); s.scale.set(1, 82 / 98, 1); s.position.set(0, -0.8, 0); s.rotation.set(Math.PI / 2, 0, 0); g.add(s);
});
panels.push(bottom);

// ------------------------------------------------------------------ antenna top cap + elements
let deployed = true;
const antParts = {};
const cap = part("Antenna top cap v2c (+Z)", "PROVES antenna_top_cap_v2c: burn-wire release, CSD17576 burn FET, balun and MMCX feed, sun + temperature sensors, RBF port.",
  [0, 70, 0], (g) => {
    const b = box(98, 1.6, 98, M.pcbBlack); b.position.y = H + 0.8; g.add(b);
    chipOn(g, 0, H + 1.6, 0, 10, 10, 2, M.chip);
    chipOn(g, 30, H + 1.6, -30, 6, 6, 3, M.gold);       // MMCX
    const rbf = box(10, 5, 6, new THREE.MeshStandardMaterial({ color: 0xc0262d })); rbf.position.set(-36, H + 4, 36); g.add(rbf);
    // 70 cm dipole: 2 × 178 mm tape-measure elements (deployed along ±X)
    antParts.uhf = [];
    for (const s of [-1, 1]) {
      const t = box(178, 0.3, 12.7, M.tape); t.position.set(s * (8 + 89), H + 3, 0);
      g.add(t); antParts.uhf.push({ m: t, s, len: 178 });
    }
    // proposed 2 m element (~490 mm quarter-wave), along +Z (cubesat +Y)
    const v = box(12.7, 0.3, 490, M.tapeV); v.position.set(0, H + 3.4, 8 + 245);
    g.add(v); antParts.vhf = { m: v, len: 490 };
  }, [0, H + 18, 0]);
addLabel("70 cm dipole (2 × 178 mm)", cap.group, new THREE.Vector3(150, H + 6, 0));
addLabel("Proposed 2 m element (~490 mm, TBD)", cap.group, new THREE.Vector3(0, H + 8, 300));

function setDeployed(on) {
  deployed = on;
  for (const a of antParts.uhf) {
    a.m.scale.x = on ? 1 : 0.06; a.m.position.x = a.s * (on ? 8 + 89 : 47);
  }
  antParts.vhf.m.scale.z = on ? 1 : 0.02; antParts.vhf.m.position.z = on ? 8 + 245 : 47;
  labels.forEach((l) => { if (l.obj === cap.group && l.el.textContent !== "Antenna top cap v2c (+Z)") l.el.style.visibility = on ? "" : "hidden"; });
}

// ------------------------------------------------------------------ controls
let explode = 0, explodeTarget = 0, showPanels = true;
const ui = (id) => document.getElementById(id);
ui("mk-explode").addEventListener("click", (e) => { explodeTarget = explodeTarget ? 0 : 1; e.target.setAttribute("aria-pressed", explodeTarget ? "true" : "false"); });
ui("mk-panels").addEventListener("click", (e) => {
  showPanels = !showPanels; panels.forEach((p) => (p.group.visible = showPanels));
  e.target.setAttribute("aria-pressed", showPanels ? "false" : "true");
});
ui("mk-antennas").addEventListener("click", (e) => { setDeployed(!deployed); e.target.setAttribute("aria-pressed", deployed ? "false" : "true"); });
ui("mk-labels").addEventListener("click", (e) => {
  labelLayer.hidden = !labelLayer.hidden; e.target.setAttribute("aria-pressed", labelLayer.hidden ? "true" : "false");
});
ui("mk-spin").addEventListener("click", (e) => { controls.autoRotate = !controls.autoRotate; e.target.setAttribute("aria-pressed", controls.autoRotate ? "false" : "true"); });
document.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => {
  const v = { iso: [260, 190, 300], top: [0, 420, 1], side: [380, 70, 0], inside: [230, 160, 260] }[b.dataset.view];
  camera.position.set(...v); controls.target.set(0, 60, 0);
  if (b.dataset.view === "inside" && showPanels) ui("mk-panels").click();
}));

// URL presets for sharing a view: ?explode=1&panels=0&antennas=0&view=inside
const qs = new URLSearchParams(location.search);
if (qs.get("explode") === "1") ui("mk-explode").click();
if (qs.get("panels") === "0") ui("mk-panels").click();
if (qs.get("antennas") === "0") ui("mk-antennas").click();
if (qs.get("view")) document.querySelector(`[data-view="${CSS.escape(qs.get("view"))}"]`)?.click();
if (qs.get("spin") === "0") ui("mk-spin").click();

// hover picking
const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
let hovered = null;
renderer.domElement.addEventListener("pointermove", (ev) => {
  const r = renderer.domElement.getBoundingClientRect();
  mouse.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const hit = ray.intersectObjects(pickables.filter((o) => o.visible && o.parent && isVisible(o)), false)[0];
  const p = hit ? hit.object.userData.part : null;
  if (p !== hovered) {
    if (hovered) setEmissive(hovered, 0);
    hovered = p;
    if (p) setEmissive(p, 0.18);
  }
  if (p) {
    tip.innerHTML = `<b>${p.userData.name}</b><br>${p.userData.desc}`;
    tip.style.display = "block";
    const hr = host.getBoundingClientRect();
    tip.style.left = Math.min(ev.clientX - hr.left + 14, hr.width - 300) + "px";
    tip.style.top = ev.clientY - hr.top + 14 + "px";
  } else tip.style.display = "none";
});
renderer.domElement.addEventListener("pointerleave", () => { tip.style.display = "none"; if (hovered) setEmissive(hovered, 0); hovered = null; });
renderer.domElement.addEventListener("pointerdown", () => (controls.autoRotate = false));

function isVisible(o) { for (let n = o; n; n = n.parent) if (!n.visible) return false; return true; }
const emissiveCache = new Map();
function setEmissive(group, k) {
  group.traverse((o) => {
    if (!o.isMesh || !o.material.emissive) return;
    if (!emissiveCache.has(o)) { emissiveCache.set(o, o.material); o.material = o.material.clone(); }
    o.material.emissive.setRGB(k, k, k * 1.3);
  });
}

// ------------------------------------------------------------------ render loop
function resize() {
  const w = host.clientWidth, h = host.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h; camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(host);
resize();

const v = new THREE.Vector3();
function tick() {
  explode += (explodeTarget - explode) * 0.08;
  for (const p of parts) p.group.position.copy(p.home).addScaledVector(p.explode, explode);
  controls.update();
  renderer.render(scene, camera);
  if (!labelLayer.hidden) {
    const w = host.clientWidth, h = host.clientHeight;
    for (const l of labels) {
      v.copy(l.local).applyMatrix4(l.obj.matrixWorld).project(camera);
      const vis = v.z < 1 && isVisible(l.obj) && (!l.internal || !showPanels || explode > 0.4)
        && l.el.style.visibility !== "hidden";
      l.el.style.display = vis ? "" : "none";
      l.el.style.transform = `translate(${(v.x * 0.5 + 0.5) * w}px, ${(-v.y * 0.5 + 0.5) * h}px) translate(-50%, -100%)`;
    }
  }
  requestAnimationFrame(tick);
}
tick();
