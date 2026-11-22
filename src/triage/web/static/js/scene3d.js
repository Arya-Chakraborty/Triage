import * as THREE from "three";

const KIND = {
  event: 0xffc14d,
  asset: 0xc8c8c8,
  terminal: 0x8ec8e8,
  incident: 0xff4330,
  action: 0xff9e1b,
  agent: 0x00c853,
};

const N = 320;
let renderer;
let scene;
let camera;
let mesh;
let tubes = [];
let nodes = [];
let curves = [];
let dummy;
let parts;
let raf = 0;
let last = 0;
let reduced = false;
let dark = true;

function themeColors() {
  dark = document.documentElement.getAttribute("data-theme") !== "light";
  return {
    clear: dark ? 0x000000 : 0xf4f4f1,
    tube: dark ? 0x2a2418 : 0xb9b09a,
    grid: dark ? 0x2a2a2a : 0xcfc8b8,
    fog: dark ? 0x000000 : 0xf4f4f1,
    node: dark ? 0xff9e1b : 0xc45c00,
  };
}

function makeCurve(z) {
  return new THREE.CatmullRomCurve3([
    new THREE.Vector3(-5.4, 0.04, z),
    new THREE.Vector3(-2.7, 0.22 + Math.abs(z) * 0.15, z * 0.45),
    new THREE.Vector3(0.0, 0.08, z * 0.12),
    new THREE.Vector3(2.7, 0.2 + Math.abs(z) * 0.1, z * 0.45),
    new THREE.Vector3(5.4, 0.04, z),
  ]);
}

function applyTheme() {
  const t = themeColors();
  if (!renderer) return;
  renderer.setClearColor(t.clear, 1);
  scene.fog.color.setHex(t.fog);
  tubes.forEach((m) => {
    m.material.color.setHex(t.tube);
    m.material.emissive.setHex(dark ? 0x1a1408 : 0x3a2a10);
  });
  nodes.forEach((m) => {
    m.material.color.setHex(t.node);
    m.material.emissive.setHex(t.node);
  });
}

function spawn(kind, boost) {
  let slot = -1;
  for (let i = 0; i < N; i++) {
    if (parts[i].t >= 1) {
      slot = i;
      break;
    }
  }
  if (slot < 0) slot = Math.floor(Math.random() * N);
  const map = { event: 0, asset: 0, terminal: 1, incident: 2, action: 2, agent: 3 };
  const p = parts[slot];
  p.t = 0;
  p.curve = map[kind] ?? 0;
  p.speed = (boost ? 0.22 : 0.08) + Math.random() * 0.12;
  p.rev = kind === "agent";
  p.alive = true;
  const c = new THREE.Color(KIND[kind] || KIND.event);
  if (!boost) c.multiplyScalar(0.55);
  mesh.setColorAt(slot, c);
  mesh.instanceColor.needsUpdate = true;
}

function tick(now) {
  const dt = Math.min(0.05, (now - last) / 1000 || 0.016);
  last = now;
  if (!reduced) {
    if (Math.random() < 0.08) spawn("event", false);
    if (Math.random() < 0.02) spawn("asset", false);
    const t = now * 0.00012;
    camera.position.x = Math.sin(t) * 0.55;
    camera.position.y = 1.85 + Math.cos(t * 0.7) * 0.08;
    camera.lookAt(0, 0.15, 0);
  }
  const pos = new THREE.Vector3();
  for (let i = 0; i < N; i++) {
    const p = parts[i];
    if (!p.alive) {
      dummy.scale.setScalar(0);
      dummy.position.set(0, -4, 0);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      continue;
    }
    p.t += p.speed * dt;
    if (p.t >= 1) {
      p.alive = false;
      dummy.scale.setScalar(0);
      dummy.position.set(0, -4, 0);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      continue;
    }
    const u = p.rev ? 1 - p.t : p.t;
    curves[p.curve].getPointAt(u, pos);
    dummy.position.copy(pos);
    dummy.scale.setScalar(0.9 + Math.sin(p.t * 12) * 0.15);
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);
  }
  mesh.instanceMatrix.needsUpdate = true;
  renderer.render(scene, camera);
  raf = requestAnimationFrame(tick);
}

function resize(el) {
  const w = Math.max(1, el.clientWidth);
  const h = Math.max(1, el.clientHeight);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
}

export function mount(el) {
  reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const t = themeColors();
  scene = new THREE.Scene();
  scene.fog = new THREE.Fog(t.fog, 6.5, 13);
  camera = new THREE.PerspectiveCamera(38, 2, 0.1, 40);
  camera.position.set(0, 1.9, 4.6);
  camera.lookAt(0, 0.15, 0);

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(t.clear, 1);
  renderer.domElement.style.display = "block";
  renderer.domElement.style.width = "100%";
  renderer.domElement.style.height = "100%";
  el.appendChild(renderer.domElement);

  scene.add(new THREE.AmbientLight(0xffffff, dark ? 0.35 : 0.55));
  const key = new THREE.DirectionalLight(0xffc14d, dark ? 0.85 : 0.45);
  key.position.set(2.4, 4.2, 3.2);
  scene.add(key);
  const fill = new THREE.PointLight(0xff9e1b, 1.1, 12);
  fill.position.set(0, 1.2, 0);
  scene.add(fill);

  const grid = new THREE.GridHelper(14, 28, t.grid, t.grid);
  grid.position.y = -0.35;
  grid.material.transparent = true;
  grid.material.opacity = 0.35;
  scene.add(grid);

  curves = [-0.62, -0.2, 0.2, 0.62].map(makeCurve);
  dummy = new THREE.Object3D();
  tubes = [];
  nodes = [];
  curves.forEach((c) => {
    const geo = new THREE.TubeGeometry(c, 96, 0.028, 10, false);
    const mat = new THREE.MeshStandardMaterial({
      color: t.tube,
      metalness: 0.88,
      roughness: 0.28,
      emissive: dark ? 0x1a1408 : 0x3a2a10,
      emissiveIntensity: 0.6,
    });
    const tube = new THREE.Mesh(geo, mat);
    scene.add(tube);
    tubes.push(tube);
    [0, 1].forEach((u) => {
      const box = new THREE.Mesh(
        new THREE.BoxGeometry(0.16, 0.16, 0.16),
        new THREE.MeshStandardMaterial({
          color: t.node,
          metalness: 0.4,
          roughness: 0.35,
          emissive: t.node,
          emissiveIntensity: 0.55,
        })
      );
      c.getPointAt(u, box.position);
      scene.add(box);
      nodes.push(box);
    });
  });

  const sphere = new THREE.SphereGeometry(0.038, 10, 10);
  const pmat = new THREE.MeshBasicMaterial({ color: 0xffffff });
  mesh = new THREE.InstancedMesh(sphere, pmat, N);
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  scene.add(mesh);
  const seed = new THREE.Color(KIND.event);
  parts = Array.from({ length: N }, () => ({ t: 1, curve: 0, speed: 0.1, rev: false, alive: false }));
  for (let i = 0; i < N; i++) {
    dummy.scale.setScalar(0);
    dummy.position.set(0, -4, 0);
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);
    mesh.setColorAt(i, seed);
  }
  mesh.instanceColor.needsUpdate = true;

  for (let i = 0; i < 40; i++) spawn("event", false);

  resize(el);
  new ResizeObserver(() => resize(el)).observe(el);
  window.addEventListener("triage-theme", applyTheme);
  last = performance.now();
  raf = requestAnimationFrame(tick);
}

export function pulse(kind) {
  const n = kind === "incident" || kind === "action" ? 10 : 6;
  for (let i = 0; i < n; i++) spawn(kind || "event", true);
}

export function setTheme() {
  applyTheme();
}
