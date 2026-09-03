import { getBridge } from "./bridge";
import { apiUrl } from "./backend";

function host(): any { return typeof window !== "undefined" ? (window as any) : (globalThis as any); }

export async function saveTextFile(filename: string, text: string, mime = "text/csv"): Promise<boolean> {
  const api = getBridge();
  if (api) return (await api.save_file({ filename, content: text, encoding: "text", mime })).saved;
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return true;
}

export async function downloadFromBackend(path: string, filename?: string): Promise<boolean> {
  const api = getBridge();
  if (api) return (await api.download({ path, filename })).saved;
  host().open(apiUrl(path), "_blank");
  return true;
}

export async function copyText(text: string): Promise<boolean> {
  const api = getBridge();
  if (api) {
    const r = await api.copy_text(text);
    if (r.ok) return true;
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
    // `created: false` only means the window was already open — still a success for the caller.
    await api.open_popout({ label, title, query, width, height });
    return true;
  }
  const url = new URL(host().location.href);
  url.search = `?${query}`;
  host().open(url.toString(), `win-${label.toLowerCase().replace(/[^a-z0-9]/g, "-")}`, `width=${width},height=${height},menubar=no,status=no,toolbar=no`);
  return true;
}
