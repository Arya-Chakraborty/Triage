export function paintChrome(state, route) {
  const conn = document.getElementById("conn");
  if (conn) {
    const live = state.connected;
    conn.dataset.state = live ? "live" : "off";
    conn.textContent = live ? "SSE LIVE" : state.mock ? "Disconnected · mock" : "Disconnected";
  }
  const n = state.overview?.open_incidents ?? 0;
  const inc = document.getElementById("inc-count");
  if (inc) {
    inc.dataset.n = String(n);
    inc.textContent = `${n} open`;
  }
  const sse = document.getElementById("sb-sse");
  if (sse) sse.textContent = state.connected ? "SSE LIVE" : "SSE DOWN";
  const agent = document.getElementById("sb-agent");
  if (agent) agent.textContent = state.overview?.agent_busy ? "AGENT BUSY" : "AGENT IDLE";
  const feed = document.getElementById("sb-feed");
  if (feed) {
    const rate = state.overview?.event_rate_per_min ?? 0;
    feed.textContent = `FEED ${rate}/min`;
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
