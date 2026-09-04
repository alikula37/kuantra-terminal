import { getBridge, type StreamSnapshot } from "./bridge";

type Handler = (msg: any) => void;
const handlers = new Set<Handler>();

function host(): any { return typeof window !== "undefined" ? (window as any) : (globalThis as any); }

/** Called by Python as window.__kuantraPush([...]) — each item is a message object or its JSON text. */
export function installPushSink(): void {
  host().__kuantraPush = (batch: unknown) => {
    const items = Array.isArray(batch) ? batch : [batch];
    for (const raw of items) {
      let msg = raw;
      if (typeof raw === "string") {
        try { msg = JSON.parse(raw); } catch { continue; }
      }
      handlers.forEach((h) => { try { h(msg); } catch (e) { console.error("push handler failed", e); } });
    }
  };
}

export function subscribePush(handler: Handler): () => void {
  handlers.add(handler);
  return () => { handlers.delete(handler); };
}

export async function openStream(): Promise<StreamSnapshot | null> {
  const api = getBridge();
  if (!api) return null;
  return api.stream_open();
}
