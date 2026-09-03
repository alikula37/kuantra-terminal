import { beforeEach, expect, it, vi } from "vitest";
declare const globalThis: any;
beforeEach(() => { vi.resetModules(); globalThis.window = globalThis; delete globalThis.pywebview; });

it("saveTextFile uses the bridge when present", async () => {
  const save_file = vi.fn(async () => ({ saved: true, path: "/tmp/x.csv" }));
  globalThis.pywebview = { api: { request: async () => ({}), save_file } };
  const { saveTextFile } = await import("../desktop");
  expect(await saveTextFile("x.csv", "a,b")).toBe(true);
  expect(save_file).toHaveBeenCalledWith({ filename: "x.csv", content: "a,b", encoding: "text", mime: "text/csv" });
});

it("downloadFromBackend falls back to window.open in the browser", async () => {
  const open = vi.fn();
  globalThis.open = open;
  const { downloadFromBackend } = await import("../desktop");
  expect(await downloadFromBackend("/api/v1/journal/template-csv", "t.csv")).toBe(true);
  expect(open).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/journal/template-csv", "_blank");
});

it("copyText prefers the bridge, then navigator.clipboard", async () => {
  const copy_text = vi.fn(async () => ({ ok: true }));
  globalThis.pywebview = { api: { request: async () => ({}), copy_text } };
  const { copyText } = await import("../desktop");
  expect(await copyText("hi")).toBe(true);
  delete globalThis.pywebview;
  vi.resetModules();
  // Node 22 exposes `navigator` as a getter-only global, so plain assignment throws.
  Object.defineProperty(globalThis, "navigator", { value: { clipboard: { writeText: vi.fn(async () => undefined) } }, configurable: true, writable: true });
  const mod = await import("../desktop");
  expect(await mod.copyText("hi")).toBe(true);
});
