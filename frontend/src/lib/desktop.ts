import { getBridge } from "./bridge";
import { apiUrl } from "./backend";

function host(): any { return typeof window !== "undefined" ? (window as any) : (globalThis as any); }

/**
 * Every helper returns a boolean instead of throwing: a native save dialog the user cancels and a
 * bridge call that rejects are both "did not happen", and callers only need to know which.
 */
export async function saveTextFile(filename: string, text: string, mime = "text/csv"): Promise<boolean> {
  const api = getBridge();
  if (api) {
    try {
      return (await api.save_file({ filename, content: text, encoding: "text", mime })).saved;
    } catch (e) {
      console.warn("save_file failed:", e);
      return false;
    }
  }
  try {
    const blob = new Blob([text], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return true;
  } catch (e) {
    console.warn("browser download failed:", e);
    return false;
  }
}

export interface DownloadOutcome {
  saved: boolean;
  status?: number;
}

/**
 * Status-aware download used where the caller must distinguish "the user
 * cancelled the save dialog" from "the backend refused the artifact".  The
 * boolean `downloadFromBackend` keeps its existing contract for other callers.
 */
export async function downloadFromBackendDetailed(path: string, filename?: string, query = ""): Promise<DownloadOutcome> {
  const api = getBridge();
  if (api) {
    try {
      const result = await api.download({ path, query, filename });
      return { saved: result?.saved === true, status: result?.status };
    } catch (e) {
      console.warn("download failed:", e);
      return { saved: false };
    }
  }
  try {
    const separator = query ? (path.includes("?") ? "&" : "?") : "";
    host().open(`${apiUrl(path)}${separator}${query}`, "_blank");
    return { saved: true, status: 200 };
  } catch (e) {
    console.warn("browser download failed:", e);
    return { saved: false };
  }
}

export async function downloadFromBackend(path: string, filename?: string, query = ""): Promise<boolean> {
  return (await downloadFromBackendDetailed(path, filename, query)).saved;
}

export async function copyText(text: string): Promise<boolean> {
  const api = getBridge();
  if (api) {
    try {
      const r = await api.copy_text(text);
      if (r.ok) return true;
    } catch (e) {
      // Fall through to navigator.clipboard rather than rejecting into the caller.
      console.warn("copy_text failed, falling back to navigator.clipboard:", e);
    }
  }
  try {
    const nav = host().navigator;
    if (nav?.clipboard?.writeText) { await nav.clipboard.writeText(text); return true; }
  } catch { /* fall through */ }
  return false;
}

export async function openPopout(label: string, title: string, width: number, height: number): Promise<boolean> {
  const api = getBridge();
  const query = `popout=${encodeURIComponent(label)}`;
  if (api) {
    try {
      // `created: false` only means the window was already open — still a success for the caller.
      await api.open_popout({ label, title, query, width, height });
      return true;
    } catch (e) {
      console.warn("open_popout failed:", e);
      return false;
    }
  }
  const url = new URL(host().location.href);
  url.search = `?${query}`;
  host().open(url.toString(), `win-${label.toLowerCase().replace(/[^a-z0-9]/g, "-")}`, `width=${width},height=${height},menubar=no,status=no,toolbar=no`);
  return true;
}
