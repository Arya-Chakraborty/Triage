export function paintChrome(state, route) {
  const conn = document.getElementById("conn");
  if (conn) {
    const live = state.connected;
    conn.dataset.state = live ? "live" : "off";
    conn.textContent = live ? "SSE live" : state.mock ? "Disconnected · mock" : "Disconnected";
  }
  const n = state.overview?.open_incidents ?? 0;
  const inc = document.getElementById("inc-count");
  if (inc) {
    inc.dataset.n = String(n);
    inc.textContent = `${n} open`;
  }
  document.querySelectorAll(".nav a").forEach((a) => {
    const page = (a.getAttribute("href") || "").replace("#/", "").split("/")[0];
    const on = page === (route.page || "overview");
    a.setAttribute("aria-selected", on ? "true" : "false");
    if (on) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  const view = document.getElementById("view");
  if (view) view.setAttribute("aria-label", route.page || "overview");
}
