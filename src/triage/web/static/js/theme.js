const KEY = "triage-theme";

export function currentTheme() {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

export function applyTheme(theme) {
  const t = theme === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", t);
  localStorage.setItem(KEY, t);
  window.dispatchEvent(new CustomEvent("triage-theme", { detail: t }));
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  btn.textContent = t === "dark" ? "Light" : "Dark";
  btn.setAttribute("aria-label", t === "dark" ? "Switch to light theme" : "Switch to dark theme");
}

export function initTheme() {
  const q = new URLSearchParams(location.search).get("theme");
  const saved = q || localStorage.getItem(KEY);
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(saved === "light" || saved === "dark" ? saved : prefersDark ? "dark" : "light");
  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
  });
}
