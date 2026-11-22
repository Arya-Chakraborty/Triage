const IN = [
  { id: "process", label: "process", y: 30, d: "M 144 30 C 270 30, 350 80, 428 80" },
  { id: "server", label: "server", y: 62, d: "M 144 62 C 270 62, 350 80, 428 80" },
  { id: "terminal", label: "terminal", y: 94, d: "M 144 94 C 270 94, 350 80, 428 80" },
  { id: "deploy", label: "deploy", y: 126, d: "M 144 126 C 270 126, 350 80, 428 80" },
];
const OUT = [
  { id: "incidents", label: "open", y: 40, d: "M 532 72 C 640 40, 720 40, 816 40" },
  { id: "agent", label: "agent", y: 80, d: "M 532 80 H 816" },
  { id: "rate", label: "rate", y: 120, d: "M 532 88 C 640 120, 720 120, 816 120" },
];
const KIND = {
  event: "process",
  asset: "server",
  terminal: "terminal",
  incident: "incidents",
  action: "agent",
  agent: "agent",
};

const VB = { w: 960, h: 156 };
let root = null;
let canvas = null;
let ctx = null;
let paths = {};
let parts = [];
let raf = 0;
let last = 0;
let pingTimer = 0;

function reduced() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function node(x, y, id, label) {
  return `<g>
    <rect class="pad" x="${x}" y="${y - 11}" width="132" height="22"/>
    <text class="lbl" x="${x + 8}" y="${y + 4}">${label}</text>
    <text class="val" id="n-${id}" x="${x + 124}" y="${y + 4}" text-anchor="end">—</text>
  </g>`;
}

export function mount(el) {
  root = el;
  el.className = "pipeboard";
  el.innerHTML = `<svg viewBox="0 0 ${VB.w} ${VB.h}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
    ${IN.map((p) => `<path id="p-${p.id}" class="pipe" d="${p.d}"/>`).join("")}
    ${OUT.map((p) => `<path id="p-${p.id}" class="pipe" d="${p.d}"/>`).join("")}
    ${IN.map((p) => node(12, p.y, p.id, p.label)).join("")}
    ${OUT.map((p) => node(816, p.y, p.id, p.label)).join("")}
    <circle class="hub-ring r1" cx="480" cy="80" r="46"/>
    <circle class="hub-ring r2" cx="480" cy="80" r="46"/>
    <rect class="hub" x="428" y="52" width="104" height="56"/>
    <text class="hub-t" x="480" y="84">TRIAGE</text>
  </svg>`;
  canvas = document.createElement("canvas");
  canvas.className = "pipe-fx";
  el.appendChild(canvas);
  ctx = canvas.getContext("2d", { alpha: true });
  const svg = el.querySelector("svg");
  [...IN, ...OUT].forEach((p) => {
    paths[p.id] = svg.querySelector(`#p-${p.id}`);
  });
  size();
  new ResizeObserver(size).observe(el);
}

export function sync(state) {
  if (!root) return;
  const assets = state.assets || [];
  const o = state.overview || {};
  const n = (k) => assets.filter((a) => a.kind === k).length;
  set("n-process", n("process"));
  set("n-server", n("server") + n("url"));
  set("n-terminal", n("terminal"));
  set("n-deploy", n("deploy"));
  set("n-incidents", o.open_incidents ?? 0);
  set("n-agent", o.agent_busy ? "busy" : "idle");
  const rate = o.event_rate_per_min;
  set("n-rate", rate == null ? "—" : `${rate}/m`);
  root.classList.toggle("busy", Boolean(o.agent_busy));
}

function set(id, val) {
  const el = root.querySelector(`#${id}`);
  if (el) el.textContent = String(val);
}

function size() {
  if (!canvas || !root) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = root.clientWidth;
  const h = root.clientHeight;
  canvas.width = Math.max(1, Math.floor(w * dpr));
  canvas.height = Math.max(1, Math.floor(h * dpr));
  canvas.style.width = w + "px";
  canvas.style.height = h + "px";
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function cssVar(name, fallback) {
  if (!root) return fallback;
  return getComputedStyle(root).getPropertyValue(name).trim() || fallback;
}

function start() {
  if (raf || reduced()) return;
  last = 0;
  raf = requestAnimationFrame(tick);
}

function map(pt) {
  const w = root.clientWidth;
  const h = root.clientHeight;
  const s = Math.min(w / VB.w, h / VB.h);
  return {
    x: (w - VB.w * s) / 2 + pt.x * s,
    y: (h - VB.h * s) / 2 + pt.y * s,
    s,
  };
}

function tick(now) {
  const dt = last ? Math.min(0.032, (now - last) / 1000) : 0.016;
  last = now;
  const w = root.clientWidth;
  const h = root.clientHeight;
  ctx.clearRect(0, 0, w, h);
  const next = [];
  for (const p of parts) {
    p.t += p.speed * dt;
    if (p.t >= 1) continue;
    const el = paths[p.path];
    if (!el) continue;
    const pt = el.getPointAtLength(p.t * el.getTotalLength());
    const m = map(pt);
    ctx.beginPath();
    ctx.fillStyle = p.color;
    ctx.arc(m.x, m.y, (p.hot ? 3.2 : 2.4) * Math.min(1.2, m.s), 0, Math.PI * 2);
    ctx.fill();
    next.push(p);
  }
  parts = next;
  if (parts.length) raf = requestAnimationFrame(tick);
  else {
    raf = 0;
    last = 0;
    ctx.clearRect(0, 0, w, h);
  }
}

export function pulse(kind) {
  if (!root || reduced()) return;
  const path = KIND[kind] || "process";
  const hot = kind === "incident" || kind === "action";
  const color = hot ? cssVar("--danger", "#ff4330") : cssVar("--accent", "#ff9e1b");
  if (parts.length > 5) parts.shift();
  parts.push({ path, t: 0, speed: 0.95, color, hot });
  start();
}

export function ping() {
  if (!root) return;
  root.classList.remove("ping");
  void root.offsetWidth;
  root.classList.add("ping");
  clearTimeout(pingTimer);
  pingTimer = setTimeout(() => root.classList.remove("ping"), 700);
}
