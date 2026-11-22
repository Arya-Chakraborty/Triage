let token = "";

export function setToken(value) {
  token = value || "";
}

function headers() {
  const h = { Accept: "application/json" };
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

function withToken(path) {
  if (!token) return path;
  const join = path.includes("?") ? "&" : "?";
  return `${path}${join}token=${encodeURIComponent(token)}`;
}

export async function get(path) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 4000);
  try {
    const res = await fetch(withToken(path), { headers: headers(), signal: ctrl.signal });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`.trim());
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

export function overview() {
  return get("/api/overview");
}

export function assets() {
  return get("/api/assets");
}

export function events({ asset = "", level = "", limit = 25, offset = 0 } = {}) {
  const q = new URLSearchParams();
  if (asset) q.set("asset", asset);
  if (level) q.set("level", level);
  if (limit != null) q.set("limit", String(limit));
  if (offset != null) q.set("offset", String(offset));
  return get(`/api/events?${q}`);
}

export function incidents() {
  return get("/api/incidents");
}

export function incident(id) {
  return get(`/api/incidents/${encodeURIComponent(id)}`);
}

export function terminals() {
  return get("/api/terminals");
}

export function telemetry() {
  return get("/api/telemetry");
}

export async function post(path, body = {}) {
  const res = await fetch(withToken(path), {
    method: "POST",
    headers: { ...headers(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`.trim());
  return res.json();
}

export function reinitiate() {
  return post("/api/agent/reinitiate");
}

export async function probe() {
  try {
    await overview();
    return true;
  } catch {
    return false;
  }
}

export function normalizeEvents(data) {
  if (Array.isArray(data)) return { items: data, total: data.length };
  const items = data.items || data.events || [];
  return { items, total: data.total ?? items.length };
}

export function streamUrl() {
  return withToken("/api/stream");
}
