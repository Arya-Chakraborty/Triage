let impl = { pulse() {}, setTheme() {} };

export async function mount(el) {
  try {
    impl = await import("./scene3d.js");
    impl.mount(el);
  } catch (err) {
    el.classList.add("flow-off");
    console.warn("three.js unavailable", err);
  }
}

export function pulse(kind) {
  impl.pulse?.(kind);
}

export function setTheme() {
  impl.setTheme?.();
}
