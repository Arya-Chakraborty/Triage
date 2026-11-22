const state = {
  mock: false,
  connected: false,
  banner: "",
  loading: {},
  error: {},
  overview: null,
  assets: [],
  events: { items: [], total: 0 },
  incidents: [],
  incident: null,
  terminals: [],
  telemetry: null,
  ticker: [],
  paused: {},
  filters: {
    level: "",
    asset: "",
    source: "",
    fingerprint: "",
    q: "",
    limit: 25,
    offset: 0,
  },
};

const subs = new Set();

export function get() {
  return state;
}

export function patch(partial) {
  Object.assign(state, partial);
  for (const fn of subs) fn(state);
}

export function setLoading(key, on) {
  patch({ loading: { ...state.loading, [key]: on } });
}

export function setError(key, msg) {
  patch({ error: { ...state.error, [key]: msg || "" } });
}

export function subscribe(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}

export function upsert(list, item, idKey = "id") {
  if (!item || item[idKey] == null) return list;
  const i = list.findIndex((x) => x[idKey] === item[idKey]);
  if (i === -1) return [item, ...list];
  const next = list.slice();
  next[i] = { ...list[i], ...item };
  return next;
}

export function pushTicker(ev) {
  const ticker = [ev, ...state.ticker].slice(0, 40);
  patch({ ticker });
}
