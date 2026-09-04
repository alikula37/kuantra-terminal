import { afterEach, beforeEach, expect, it, vi } from "vitest";

declare const globalThis: any;

beforeEach(() => {
  vi.resetModules();
  vi.stubGlobal("window", globalThis);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it("saveTextFile uses the bridge when present", async () => {
  const save_file = vi.fn(async () => ({ saved: true, path: "/tmp/x.csv" }));
  vi.stubGlobal("pywebview", { api: { request: async () => ({}), save_file } });
  const { saveTextFile } = await import("../desktop");
  expect(await saveTextFile("x.csv", "a,b")).toBe(true);
  expect(save_file).toHaveBeenCalledWith({ filename: "x.csv", content: "a,b", encoding: "text", mime: "text/csv" });
});

it("saveTextFile returns false instead of rejecting when the bridge call fails", async () => {
  const save_file = vi.fn(async () => { throw new Error("dialog crashed"); });
  vi.stubGlobal("pywebview", { api: { request: async () => ({}), save_file } });
  const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
  const { saveTextFile } = await import("../desktop");
  await expect(saveTextFile("x.csv", "a,b")).resolves.toBe(false);
  expect(warn).toHaveBeenCalled();
  warn.mockRestore();
});

it("downloadFromBackend falls back to window.open in the browser", async () => {
  const open = vi.fn();
  vi.stubGlobal("open", open);
  const { downloadFromBackend } = await import("../desktop");
  expect(await downloadFromBackend("/api/v1/journal/template-csv", "t.csv")).toBe(true);
  expect(open).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/journal/template-csv", "_blank");
});

it("downloadFromBackend returns false instead of rejecting when the bridge call fails", async () => {
  const download = vi.fn(async () => { throw new Error("no route"); });
  vi.stubGlobal("pywebview", { api: { request: async () => ({}), download } });
  const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
  const { downloadFromBackend } = await import("../desktop");
  await expect(downloadFromBackend("/api/v1/telemetry/export-logs")).resolves.toBe(false);
  expect(warn).toHaveBeenCalled();
  warn.mockRestore();
});

it("copyText prefers the bridge, then navigator.clipboard", async () => {
  const copy_text = vi.fn(async () => ({ ok: true }));
  vi.stubGlobal("pywebview", { api: { request: async () => ({}), copy_text } });
  const { copyText } = await import("../desktop");
  expect(await copyText("hi")).toBe(true);

  vi.unstubAllGlobals();
  vi.resetModules();
  vi.stubGlobal("window", globalThis);
  vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn(async () => undefined) } });
  const mod = await import("../desktop");
  expect(await mod.copyText("hi")).toBe(true);
});

it("copyText falls back to navigator.clipboard when the bridge call rejects", async () => {
  const copy_text = vi.fn(async () => { throw new Error("no clipboard owner"); });
  const writeText = vi.fn(async () => undefined);
  vi.stubGlobal("pywebview", { api: { request: async () => ({}), copy_text } });
  vi.stubGlobal("navigator", { clipboard: { writeText } });
  const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
  const { copyText } = await import("../desktop");
  await expect(copyText("hi")).resolves.toBe(true);
  expect(copy_text).toHaveBeenCalledOnce();
  expect(writeText).toHaveBeenCalledWith("hi");
  warn.mockRestore();
});

it("copyText returns false when neither the bridge nor the clipboard works", async () => {
  vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn(async () => { throw new Error("denied"); }) } });
  const { copyText } = await import("../desktop");
  await expect(copyText("hi")).resolves.toBe(false);
});
