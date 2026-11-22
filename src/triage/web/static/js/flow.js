const NS = "http://www.w3.org/2000/svg";
const PATHS = {
  event: "M 28 22 H 210",
  asset: "M 28 22 H 210",
  terminal: "M 28 22 H 210",
  incident: "M 210 22 H 392",
  action: "M 392 22 H 574",
  agent: "M 392 22 V 40 H 210 V 22",
};

let root = null;
let busy = 0;

export function mount(el) {
  root = el;
  el.innerHTML = `<svg viewBox="0 0 600 44" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
    <path class="pipe-line" d="M 28 22 H 574"/>
    <path class="pipe-line dim" d="M 301 22 V 40 H 210"/>
    <g class="node" transform="translate(28,22)"><circle r="3.5"/><text y="14">sources</text></g>
    <g class="node" transform="translate(210,22)"><circle r="3.5"/><text y="14">ingest</text></g>
    <g class="node" transform="translate(392,22)"><circle r="3.5"/><text y="14">agent</text></g>
    <g class="node" transform="translate(574,22)"><circle r="3.5"/><text y="14">desk</text></g>
  </svg>`;
}

export function pulse(kind) {
  if (!root || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  if (busy > 14) return;
  const svg = root.querySelector("svg");
  if (!svg) return;
  const d = PATHS[kind] || PATHS.event;
  const pkt = document.createElementNS(NS, "rect");
  pkt.setAttribute("width", "5");
  pkt.setAttribute("height", "5");
  pkt.setAttribute("x", "-2.5");
  pkt.setAttribute("y", "-2.5");
  pkt.setAttribute("class", `pkt pkt-${kind}`);
  const motion = document.createElementNS(NS, "animateMotion");
  motion.setAttribute("dur", "1.25s");
  motion.setAttribute("fill", "freeze");
  motion.setAttribute("path", d);
  pkt.appendChild(motion);
  svg.appendChild(pkt);
  busy += 1;
  try {
    motion.beginElement();
  } catch {
    /* ignore */
  }
  setTimeout(() => {
    pkt.remove();
    busy -= 1;
  }, 1300);
}
