let ticks = 0;

function clock() {
  const el = document.getElementById("hud-clock");
  if (!el) return;
  el.textContent = new Date().toISOString().slice(11, 19) + "Z";
}

export function mount() {
  clock();
  setInterval(clock, 1000);
}

export function pulse() {
  ticks += 1;
  const el = document.getElementById("sb-ticks");
  if (el) el.textContent = `${ticks} msg`;
}
