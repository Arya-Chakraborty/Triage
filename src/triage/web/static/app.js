import { fixtures, emptyFixtures } from "./fixtures.js";
import * as api from "./js/api.js";
import { connect as connectSse } from "./js/sse.js";
import * as store from "./js/state.js";
import { initTheme } from "./js/theme.js";
import { mount as mountFlow, pulse as pulseFlow } from "./js/flow.js";
import { paintChrome } from "./js/views/shell.js";
import { renderOverview } from "./js/views/overview.js";
import { renderSystems } from "./js/views/systems.js";
import { renderTerminals } from "./js/views/terminals.js";
import { renderEvents } from "./js/views/events.js";
import { renderIncidents } from "./js/views/incidents.js";
import { renderTelemetry } from "./js/views/telemetry.js";

const views = {
  overview: renderOverview,
  systems: renderSystems,
  terminals: renderTerminals,
  events: renderEvents,
  incidents: renderIncidents,
  telemetry: renderTelemetry,
};

const qs = new URLSearchParams(location.search);
const forceMock = qs.get("mock") === "1";
const forceEmpty = qs.get("empty") === "1";
const forceError = qs.get("error") === "1";
const data = forceEmpty ? emptyFixtures : fixtures;

api.setToken(qs.get("token") || "");

function parseRoute() {
  const raw = (location.hash || "#/overview").replace(/^#\/?/, "");
  const [path, query] = raw.split("?");
  const parts = (path || "overview").split("/").filter(Boolean);
  const params = new URLSearchParams(query || "");
  return { page: parts[0] || "overview", id: parts[1] || "", params };
}

function filtersFrom(route) {
  const p = route.params;
  const prev = store.get().filters;
  return {
    level: p.get("level") || "",
    asset: p.get("asset") || (route.page === "systems" ? route.id : ""),
    source: p.get("source") || "",
    fingerprint: p.get("fingerprint") || "",
    q: p.get("q") || "",
    limit: Number(p.get("limit") || prev.limit || 25),
    offset: Number(p.get("offset") || 0),
  };
}

function render() {
  const state = store.get();
  const route = parseRoute();
  paintChrome(state, route);
  const fn = views[route.page] || views.overview;
  const view = document.getElementById("view");
  try {
    view.innerHTML = fn(state, route);
  } catch (err) {
    view.innerHTML = `<div class="state err" role="alert">${String(err)}</div>`;
  }
  document.querySelectorAll("pre[data-term]").forEach((el) => {
    if (el.dataset.paused === "1") return;
    el.scrollTop = el.scrollHeight;
  });
}

function applyFixtures() {
  store.patch({
    mock: true,
    connected: false,
    banner: "fixture",
    overview: data.overview,
    assets: data.assets,
    events: pageEvents(data.events, store.get().filters),
    incidents: data.incidents,
    incident: detailIncident(store.get().incident?.id || parseRoute().id),
    terminals: data.terminals,
    telemetry: data.telemetry,
    ticker: data.events.slice(0, 12),
  });
}

function pageEvents(all, f) {
  // ponytail: fingerprint/source/q filtered on the current set; add server q= when API grows it
  const filtered = all.filter((e) => {
    if (f.level && !_sameLevel(e.level, f.level)) return false;
    if (f.asset && e.asset_id !== f.asset) return false;
    if (f.source && !(e.source || "").toLowerCase().includes(f.source.toLowerCase())) return false;
    if (f.fingerprint && !(e.fingerprint || "").toLowerCase().includes(f.fingerprint.toLowerCase())) return false;
    if (f.q) {
      const blob = `${e.message} ${e.body || ""} ${e.fingerprint} ${e.asset_id}`.toLowerCase();
      if (!blob.includes(f.q.toLowerCase())) return false;
    }
    return true;
  });
  const offset = f.offset || 0;
  const limit = f.limit || 25;
  return { items: filtered.slice(offset, offset + limit), total: filtered.length };
}

function _sameLevel(got, want) {
  const n = (l) => (l === "warn" ? "warning" : l);
  return n(got) === n(want);
}

function detailIncident(id) {
  if (!id) return null;
  const base = data.incidents.find((i) => i.id === id);
  if (!base) return null;
  const extra = data.incidentDetails[id] || { events: [], actions: [], report_path: "" };
  const events = (extra.events || []).map((eid) =>
    typeof eid === "string" ? data.events.find((e) => e.id === eid) || eid : eid
  );
  return { ...base, ...extra, events };
}

async function loadLive(route) {
  const f = filtersFrom(route);
  store.patch({ filters: f, mock: false });

  const jobs = [];

  jobs.push(
    wrap("overview", () => api.overview(), (overview) => store.patch({ overview }))
  );
  jobs.push(
    wrap("assets", () => api.assets(), (assets) => store.patch({ assets: Array.isArray(assets) ? assets : assets.items || [] }))
  );

  if (route.page === "events" || route.page === "systems" || route.page === "overview") {
    jobs.push(
      wrap("events", () => api.events({ asset: f.asset, level: f.level, limit: f.limit, offset: f.offset }), (raw) => {
        const pack = api.normalizeEvents(raw);
        const extra = { ...f, level: "", asset: "", offset: 0, limit: pack.items.length };
        pack.items = pageEvents(pack.items, extra).items;
        store.patch({ events: pack });
        if (!store.get().ticker.length) store.patch({ ticker: pack.items.slice(0, 12) });
      })
    );
  }
  if (route.page === "incidents") {
    jobs.push(
      wrap("incidents", () => api.incidents(), (raw) => {
        store.patch({ incidents: Array.isArray(raw) ? raw : raw.items || raw.incidents || [] });
      })
    );
    if (route.id) {
      jobs.push(
        wrap("incident", () => api.incident(route.id), (incident) => store.patch({ incident }))
      );
    }
  }
  if (route.page === "terminals") {
    jobs.push(wrap("terminals", () => api.terminals(), (raw) => {
      store.patch({ terminals: Array.isArray(raw) ? raw : raw.items || [] });
    }));
  }
  if (route.page === "telemetry") {
    jobs.push(wrap("telemetry", () => api.telemetry(), (telemetry) => store.patch({ telemetry })));
  }

  await Promise.all(jobs);
}

async function wrap(key, fn, apply) {
  store.setLoading(key, true);
  store.setError(key, forceError ? "Forced error" : "");
  if (forceError) {
    store.setLoading(key, false);
    return false;
  }
  try {
    apply(await fn());
    store.setLoading(key, false);
    return true;
  } catch (err) {
    store.setLoading(key, false);
    store.setError(key, String(err.message || err));
    return false;
  }
}

function onSse(type, payload) {
  pulseFlow(type);
  const s = store.get();
  if (type === "event") {
    store.pushTicker(payload);
    store.patch({ events: { items: [payload, ...s.events.items].slice(0, 100), total: (s.events.total || 0) + 1 } });
  } else if (type === "incident") {
    store.patch({ incidents: store.upsert(s.incidents, payload) });
    if (s.incident && s.incident.id === payload.id) {
      const { events, actions, report_path, ...rest } = payload;
      store.patch({
        incident: {
          ...s.incident,
          ...rest,
          events: events || s.incident.events,
          actions: actions || s.incident.actions,
          report_path: report_path ?? s.incident.report_path,
        },
      });
    }
  } else if (type === "action") {
    if (s.incident && payload && s.incident.id === payload.incident_id) {
      const actions = s.incident.actions || [];
      if (!actions.some((a) => a.id === payload.id)) {
        store.patch({ incident: { ...s.incident, actions: [...actions, payload] } });
      }
    }
  } else if (type === "agent") {
    const overview = s.overview || {};
    store.patch({ overview: { ...overview, agent_busy: Boolean(payload && payload.busy) } });
  } else if (type === "asset") {
    store.patch({ assets: store.upsert(s.assets, payload) });
  } else if (type === "terminal") {
    store.patch({ terminals: store.upsert(s.terminals, payload) });
  }
}

function startMockTicker() {
  const all = data.events;
  if (!all.length) return;
  let i = 0;
  setInterval(() => {
    store.pushTicker(all[i % all.length]);
    i += 1;
  }, 4000);
}

async function loadRoute() {
  const route = parseRoute();
  store.patch({ filters: filtersFrom(route) });
  if (store.get().mock) {
    if (route.page === "incidents" && route.id) {
      store.patch({ incident: detailIncident(route.id) });
    }
    store.patch({ events: pageEvents(data.events, store.get().filters) });
    render();
    return;
  }
  await loadLive(route);
}

function onClick(e) {
  const el = e.target.closest("[data-act]");
  if (!el) return;
  const act = el.dataset.act;
  if (act === "goto") {
    location.hash = el.dataset.href;
  } else if (act === "pause") {
    const id = el.dataset.id;
    const paused = { ...store.get().paused, [id]: !store.get().paused[id] };
    store.patch({ paused });
  } else if (act === "page") {
    const f = store.get().filters;
    const dir = Number(el.dataset.dir);
    const next = Math.max(0, f.offset + dir * (f.limit || 25));
    writeFilters({ ...f, offset: next });
  }
}

function onSubmit(e) {
  const form = e.target.closest("form[data-act=filters]");
  if (!form) return;
  e.preventDefault();
  const fd = new FormData(form);
  writeFilters({
    ...store.get().filters,
    level: fd.get("level") || "",
    source: fd.get("source") || "",
    asset: fd.get("asset") || "",
    fingerprint: fd.get("fingerprint") || "",
    q: fd.get("q") || "",
    offset: 0,
  });
}

function writeFilters(f) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) {
    if (v === "" || v == null) continue;
    if (k === "limit" && Number(v) === 25) continue;
    if (k === "offset" && Number(v) === 0) continue;
    q.set(k, String(v));
  }
  const qs = q.toString();
  location.hash = `#/events${qs ? "?" + qs : ""}`;
}

function onKey(e) {
  const row = e.target.closest("tr[data-act=goto]");
  if (!row) return;
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    location.hash = row.dataset.href;
  }
}

async function boot() {
  initTheme();
  const bar = document.getElementById("flowbar");
  if (bar) mountFlow(bar);
  document.addEventListener("click", onClick);
  document.addEventListener("submit", onSubmit);
  document.addEventListener("keydown", onKey);

  if (forceError) {
    store.patch({
      mock: true,
      connected: false,
      error: Object.fromEntries(
        ["overview", "assets", "events", "incidents", "incident", "terminals", "telemetry"].map((k) => [k, "Forced error"])
      ),
    });
  } else if (forceMock || forceEmpty || !(await api.probe())) {
    applyFixtures();
    startMockTicker();
  } else {
    connectSse({
      onOpen: () => store.patch({ connected: true, mock: false }),
      onError: () => store.patch({ connected: false }),
      onEvent: onSse,
    });
  }

  store.subscribe(render);
  window.addEventListener("hashchange", () => loadRoute());
  if (!location.hash) {
    location.hash = "#/overview";
    return;
  }
  await loadRoute();
}

boot();
