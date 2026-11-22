import { streamUrl } from "./api.js";

const TYPES = ["event", "incident", "asset", "terminal", "action", "agent"];

export function connect({ onOpen, onError, onEvent }) {
  let delay = 1000;
  let es = null;
  let stopped = false;

  function start() {
    if (stopped) return;
    es = new EventSource(streamUrl());
    es.onopen = () => {
      delay = 1000;
      onOpen && onOpen();
    };
    es.onerror = () => {
      onError && onError();
      es.close();
      const wait = delay;
      delay = Math.min(delay * 2, 30000);
      setTimeout(start, wait);
    };
    for (const type of TYPES) {
      es.addEventListener(type, (e) => {
        let data = e.data;
        try {
          data = JSON.parse(e.data);
        } catch {
          /* keep raw */
        }
        onEvent && onEvent(type, data);
      });
    }
  }

  start();
  return () => {
    stopped = true;
    if (es) es.close();
  };
}
