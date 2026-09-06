import React, { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Download, FileCheck2, Hash, X, XCircle } from "lucide-react";
import { apiFetch, apiUrl } from "../lib/backend";
import { EvidenceEvent, TradeEvidencePack } from "../types";

interface TradeEvidencePanelProps {
  tradeId: string;
  onClose: () => void;
}

type PolicyReference = {
  kind: "risk" | "playbook" | "unknown";
  label: string;
  version?: string;
  snapshot?: string;
};

function shortHash(value: string | undefined | null): string {
  if (!value) return "—";
  return value.length > 18 ? `${value.slice(0, 10)}…${value.slice(-6)}` : value;
}

function policyReference(event: EvidenceEvent): PolicyReference | null {
  const payload = event.normalized_payload || {};
  const provenance = event.provenance || {};
  const decision = typeof payload.decision === "object" && payload.decision !== null
    ? payload.decision as Record<string, unknown>
    : null;
  const riskPolicy = typeof payload.risk_policy === "object" && payload.risk_policy !== null
    ? payload.risk_policy as Record<string, unknown>
    : null;
  const playbookVersion = typeof payload.playbook_version === "object" && payload.playbook_version !== null
    ? payload.playbook_version as Record<string, unknown>
    : null;

  const riskSource = decision || riskPolicy;
  if (riskSource?.policy_id || provenance.policy_id) {
    return {
      kind: "risk",
      label: String(riskSource?.policy_id || provenance.policy_id),
      version: String(riskSource?.policy_version || riskSource?.version || provenance.version || "—"),
      snapshot: String(riskSource?.policy_snapshot_sha256 || riskSource?.snapshot_sha256 || provenance.snapshot_sha256 || ""),
    };
  }
  if (playbookVersion?.playbook_id || provenance.playbook_id) {
    return {
      kind: "playbook",
      label: String(playbookVersion?.playbook_id || provenance.playbook_id),
      version: String(playbookVersion?.version || provenance.version || "—"),
      snapshot: String(playbookVersion?.snapshot_sha256 || provenance.snapshot_sha256 || ""),
    };
  }
  return null;
}

function eventLabel(event: EvidenceEvent): string {
  const payload = event.normalized_payload || {};
  if (payload.decision_kind === "PRE_EXECUTION_RISK") return "Risk decision";
  if (payload.policy_kind === "RISK_POLICY_VERSION") return "Risk policy snapshot";
  if (payload.policy_kind === "PLAYBOOK") return "Playbook snapshot";
  if (payload.review_kind === "PLAYBOOK_AUDIT") return "Playbook audit review";
  return event.event_type;
}

function sourceLabel(pack: TradeEvidencePack): { label: string; className: string } {
  if (pack.read_source === "typed_projection" && pack.coverage.ready) {
    return { label: "Typed projection", className: "text-gain border-gain/40 bg-gain/10" };
  }
  return { label: "Compatibility legacy read", className: "text-amber-300 border-amber-400/40 bg-amber-400/10" };
}

export const TradeEvidencePanel: React.FC<TradeEvidencePanelProps> = ({ tradeId, onClose }) => {
  const [pack, setPack] = useState<TradeEvidencePack | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<"json" | "html" | null>(null);
  const [exportMessage, setExportMessage] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setPack(null);
    apiFetch(apiUrl(`/api/v1/trades/${encodeURIComponent(tradeId)}/evidence`), { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          let detail = `Evidence Pack request failed (${response.status}).`;
          try {
            const body = await response.json() as { detail?: string };
            if (body.detail) detail = body.detail;
          } catch {
            // Keep the status-based message when the server did not return JSON.
          }
          throw new Error(detail);
        }
        return response.json() as Promise<TradeEvidencePack>;
      })
      .then((data) => {
        if (!controller.signal.aborted) setPack(data);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Evidence Pack could not be loaded.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [tradeId]);

  const source = useMemo(() => (pack ? sourceLabel(pack) : null), [pack]);
  const ledgerVerified = Boolean(pack?.ledger_integrity.valid && pack.ledger_integrity.checked_events > 0);
  const contextSourceVerified = pack?.market_context.market_context?.source_verified === true;

  const downloadExport = async (format: "json" | "html") => {
    setExporting(format);
    setExportMessage(null);
    try {
      const response = await apiFetch(
        apiUrl(`/api/v1/trades/${encodeURIComponent(tradeId)}/evidence/export?format=${format}`),
      );
      if (!response.ok) {
        let detail = `Export failed (${response.status}).`;
        try {
          const body = await response.json() as { detail?: string };
          if (body.detail) detail = body.detail;
        } catch {
          // Preserve the bounded status message.
        }
        throw new Error(detail);
      }
      if (typeof URL.createObjectURL !== "function") {
        throw new Error("This desktop surface cannot create a local download.");
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = `kuantra-evidence-${tradeId}.${format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
      setExportMessage(`${format.toUpperCase()} export ready.`);
    } catch (reason: unknown) {
      setExportMessage(reason instanceof Error ? reason.message : "Export failed safely.");
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Trade Evidence Pack">
      <div className="w-full max-w-5xl max-h-[92vh] overflow-y-auto bg-[#0b0e14] border border-surface-border rounded-lg shadow-2xl font-mono">
        <div className="sticky top-0 z-10 bg-[#0d121c] border-b border-surface-border px-4 py-3 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-2"><FileCheck2 className="w-4 h-4 text-accent" />TRADE EVIDENCE PACK</h2>
            <p className="text-[11px] text-slate-400 mt-1">{tradeId} · read-only forensic view · no execution authority</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close Evidence Pack" className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded">
            <X className="w-4 h-4" />
          </button>
        </div>

        {loading && <div className="p-8 text-center text-slate-400 text-xs">Loading source-linked evidence…</div>}
        {!loading && error && (
          <div className="m-4 p-4 rounded border border-loss/50 bg-loss/10 text-loss text-xs flex items-start gap-2">
            <XCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && pack && source && (
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-xs">
              <div className="bg-[#111722] border border-surface-border rounded p-3">
                <span className="block text-[10px] text-slate-500 uppercase">Read source</span>
                <span className={`inline-flex mt-1 px-2 py-1 rounded border ${source.className}`}>{source.label}</span>
              </div>
              <div className="bg-[#111722] border border-surface-border rounded p-3">
                <span className="block text-[10px] text-slate-500 uppercase">Ledger integrity</span>
                  <span className={`inline-flex items-center gap-1 mt-1 ${ledgerVerified ? "text-gain" : "text-amber-300"}`}>
                  {ledgerVerified ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                  {ledgerVerified ? "Verified chain" : pack.ledger_integrity.valid ? "No events to verify" : "Integrity failure"}
                </span>
                <span className="block text-[10px] text-slate-500 mt-1">{pack.ledger_integrity.checked_events} events checked</span>
              </div>
              <div className="bg-[#111722] border border-surface-border rounded p-3">
                <span className="block text-[10px] text-slate-500 uppercase">Event count</span>
                <span className="block mt-1 text-white font-bold">{pack.event_count}</span>
                <span className="block text-[10px] text-slate-500 mt-1">append-only facts</span>
              </div>
              <div className="bg-[#111722] border border-surface-border rounded p-3">
                <span className="block text-[10px] text-slate-500 uppercase">Exports</span>
                <div className="flex gap-2 mt-1">
                  {(["json", "html"] as const).map((format) => (
                    <button key={format} type="button" onClick={() => downloadExport(format)} disabled={exporting !== null} className="inline-flex items-center gap-1 px-2 py-1 rounded border border-accent/50 text-accent hover:bg-accent/10 disabled:opacity-50">
                      <Download className="w-3 h-3" />{exporting === format ? "…" : format.toUpperCase()}
                    </button>
                  ))}
                </div>
                {exportMessage && <span className="block text-[10px] text-slate-400 mt-1">{exportMessage}</span>}
              </div>
            </div>

            <section className="bg-[#0d121c] border border-surface-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-xs font-bold text-white uppercase tracking-wide">Decision and policy evidence</h3>
                  <p className="text-[11px] text-slate-500 mt-1">Policy/playbook identity is shown only when present in the recorded event.</p>
                </div>
                {!pack.ledger_integrity.valid && <AlertTriangle className="w-4 h-4 text-loss" />}
              </div>
              {pack.events.length === 0 ? (
                <p className="text-xs text-slate-500">No lifecycle events are linked to this trade.</p>
              ) : (
                <div className="space-y-2">
                  {pack.events.map((event) => {
                    const reference = policyReference(event);
                    return (
                      <div key={event.event_id} className="border border-surface-border/70 bg-[#111722] rounded p-3 text-xs">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-bold text-white">{eventLabel(event)}</span>
                          <span className="text-[10px] text-slate-500">{event.occurred_at_utc}</span>
                        </div>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[10px] text-slate-400">
                          <span>{event.event_type}</span><span>{event.venue}</span><span>seq {event.chain_sequence}</span>
                          <span className="inline-flex items-center gap-1"><Hash className="w-3 h-3" />{shortHash(event.event_hash)}</span>
                        </div>
                        {reference && (
                          <div className="mt-2 text-[10px] text-accent flex flex-wrap gap-x-3 gap-y-1">
                            <span>{reference.kind === "risk" ? "Risk policy" : "Playbook"}: {reference.label}</span>
                            <span>v{reference.version}</span>
                            <span>snapshot {shortHash(reference.snapshot)}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="bg-[#0d121c] border border-surface-border rounded-lg p-4">
              <h3 className="text-xs font-bold text-white uppercase tracking-wide">Market context provenance</h3>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                <span className={pack.market_context.status === "READY" ? "text-gain" : "text-amber-300"}>Status: {pack.market_context.status}</span>
                <span className="text-slate-400">{pack.market_context.candles?.length || 0} recorded candles</span>
                <span className="text-slate-400">{contextSourceVerified ? "Source verified" : "Source unverified / descriptive"}</span>
              </div>
              {pack.market_context.message && <p className="text-[11px] text-slate-500 mt-2">{pack.market_context.message}</p>}
            </section>

            {pack.ledger_integrity.errors.length > 0 && (
              <div className="p-3 rounded border border-loss/50 bg-loss/10 text-[11px] text-loss">
                {pack.ledger_integrity.errors.join(" · ")}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
