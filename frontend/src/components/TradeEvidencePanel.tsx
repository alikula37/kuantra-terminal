import React, { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Download, FileCheck2, Hash, X, XCircle } from "lucide-react";
import { useTranslation } from "../context/I18nContext";
import { apiFetch, apiUrl } from "../lib/backend";
import { EvidenceEvent, TradeEvidencePack } from "../types";
import { useDialogAccessibility } from "../hooks/useDialogAccessibility";

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
  if (payload.review_kind === "RECONCILIATION_DECISION") return "Reconciliation decision";
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
  const { t } = useTranslation();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  useDialogAccessibility(dialogRef, onClose, closeRef);
  const [pack, setPack] = useState<TradeEvidencePack | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<"json" | "html" | "csv" | null>(null);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [retryNonce, setRetryNonce] = useState(0);
  const requestControllerRef = useRef<AbortController | null>(null);
  const [cancelled, setCancelled] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    requestControllerRef.current = controller;
    setLoading(true);
    setError(null);
    setCancelled(false);
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
        if (requestControllerRef.current === controller && !controller.signal.aborted) setPack(data);
      })
      .catch((reason: unknown) => {
        if (requestControllerRef.current === controller && !controller.signal.aborted) {
          setCancelled(false);
          setError(reason instanceof Error ? reason.message : "Evidence Pack could not be loaded.");
        }
      })
      .finally(() => {
        if (requestControllerRef.current === controller) {
          requestControllerRef.current = null;
          if (!controller.signal.aborted) setLoading(false);
        }
      });
    return () => {
      controller.abort();
      if (requestControllerRef.current === controller) requestControllerRef.current = null;
    };
  }, [tradeId, retryNonce]);

  const cancelLoad = () => {
    const controller = requestControllerRef.current;
    if (!controller) return;
    controller.abort();
    requestControllerRef.current = null;
    setLoading(false);
    setPack(null);
    setCancelled(true);
    setError(t("evidence_pack.cancelled"));
  };

  const source = useMemo(() => (pack ? sourceLabel(pack) : null), [pack]);
  const ledgerVerified = Boolean(pack?.ledger_integrity.valid && pack.ledger_integrity.checked_events > 0);
  const contextSourceVerified = pack?.market_context.market_context?.source_verified === true;

  const downloadExport = async (format: "json" | "html" | "csv") => {
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
      setExportMessage(t("evidence_pack.export_ready", { format: format.toUpperCase() }));
    } catch (reason: unknown) {
      setExportMessage(reason instanceof Error ? reason.message : t("evidence_pack.export_failed"));
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Trade Evidence Pack">
      <div ref={dialogRef} className="w-full max-w-5xl max-h-[92vh] overflow-y-auto overflow-x-hidden bg-[#0b0e14] border border-surface-border rounded-lg shadow-2xl font-mono">
        <div className="sticky top-0 z-10 bg-[#0d121c] border-b border-surface-border px-4 py-3 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-2"><FileCheck2 className="w-4 h-4 text-accent" />TRADE EVIDENCE PACK</h2>
            <p className="text-[11px] text-slate-400 mt-1">{tradeId} · read-only forensic view · no execution authority</p>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} aria-label="Close Evidence Pack" className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
            <X className="w-4 h-4" />
          </button>
        </div>

        {loading && <div role="status" className="p-8 text-center text-slate-400 text-xs space-y-3"><span className="block">Loading source-linked evidence…</span><button type="button" data-testid="trade-evidence-cancel" onClick={cancelLoad} className="px-2 py-1 rounded border border-surface-border text-slate-300 hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">{t("evidence_pack.cancel_load")}</button></div>}
        {!loading && error && (
          <div role="alert" data-testid={cancelled ? "trade-evidence-cancelled" : undefined} className="m-4 p-4 rounded border border-loss/50 bg-loss/10 text-loss text-xs flex items-start gap-2">
            <XCircle className="w-4 h-4 shrink-0" />
            <div className="flex-1 space-y-2"><span className="block break-words">{error}</span><button type="button" data-testid="trade-evidence-retry" onClick={() => setRetryNonce((current) => current + 1)} className="px-2 py-1 rounded border border-loss/50 text-loss font-bold hover:bg-loss/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-loss">{t("evidence_pack.retry")}</button></div>
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
                  {(["json", "html", "csv"] as const).map((format) => (
                    <button key={format} type="button" onClick={() => downloadExport(format)} disabled={exporting !== null} className="inline-flex items-center gap-1 px-2 py-1 rounded border border-accent/50 text-accent hover:bg-accent/10 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
                      <Download className="w-3 h-3" />{exporting === format ? "…" : t(`evidence_pack.${format}_export`)}
                    </button>
                  ))}
                </div>
                {exportMessage && <span className="block text-[10px] text-slate-400 mt-1">{exportMessage}</span>}
              </div>
            </div>

            {pack.coverage_summary && (
              <section data-testid="trade-evidence-coverage" className="bg-[#0d121c] border border-amber-400/30 rounded-lg p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-xs font-bold text-white uppercase tracking-wide">{t("evidence_pack.coverage_title")}</h3>
                    <p className="text-[11px] text-slate-500 mt-1">Unknown and unavailable values remain visible; they are not complete or zero.</p>
                  </div>
                  <span className="px-2 py-1 rounded border border-amber-400/40 bg-amber-400/10 text-amber-300 text-[10px] font-bold">
                    {t("evidence_pack.overall")}: {pack.coverage_summary.overall}
                  </span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-3 text-[10px]">
                  {([
                    ["trade_snapshot", t("evidence_pack.trade_snapshot")],
                    ["realized_pnl", t("evidence_pack.realized_pnl")],
                    ["fees", t("evidence_pack.fees")],
                    ["funding_transfer", t("evidence_pack.funding_transfer")],
                    ["account_events", t("evidence_pack.account_events")],
                    ["market_context", t("evidence_pack.market_context")],
                  ] as const).map(([key, label]) => (
                    <div key={key} className="border border-surface-border/70 bg-[#111722] rounded p-2">
                      <span className="block text-slate-500">{label}</span>
                      <span className="block mt-1 text-amber-300 font-bold">{pack.coverage_summary?.[key] || "UNKNOWN"}</span>
                    </div>
                  ))}
                </div>
                {pack.snapshot_sha256 && (
                  <div className="mt-3 text-[10px] text-slate-500">
                    {t("evidence_pack.snapshot")}: <span title={pack.snapshot_sha256}>{shortHash(pack.snapshot_sha256)}</span>
                  </div>
                )}
              </section>
            )}

            <section data-testid="trade-evidence-rules" className="bg-[#0d121c] border border-surface-border rounded-lg p-4">
              <h3 className="text-xs font-bold text-white uppercase tracking-wide">{t("evidence_pack.rules_title")}</h3>
              {pack.applicable_rules?.length ? (
                <div className="mt-2 space-y-2">
                  {pack.applicable_rules.map((rule) => (
                    <div key={`${rule.kind}-${rule.rule_id}-${rule.event_hash || rule.snapshot_sha256}`} className="border border-surface-border/70 bg-[#111722] rounded p-2 text-[10px] text-slate-400">
                      <span className="text-accent font-bold">{rule.rule_id}</span>
                      <span className="ml-3">{rule.kind}</span>
                      <span className="ml-3">v{rule.version}</span>
                      {rule.snapshot_sha256 && <span className="ml-3">snapshot {shortHash(rule.snapshot_sha256)}</span>}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-[11px] text-amber-300 mt-2">{t("evidence_pack.no_rules")}</p>
              )}
            </section>

            {pack.import_review && (
              <section data-testid="trade-evidence-import-review" className="bg-[#0d121c] border border-amber-400/30 rounded-lg p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-xs font-bold text-white uppercase tracking-wide">Import review boundary</h3>
                    <p className="text-[11px] text-slate-500 mt-1">Source coverage is shown explicitly; a CSV journal snapshot is not broker order/fill reconciliation.</p>
                  </div>
                  <span className="px-2 py-1 rounded border border-amber-400/40 bg-amber-400/10 text-amber-300 text-[10px] font-bold">
                    {pack.import_review.status}
                  </span>
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-[10px] text-slate-400">
                  <span>Decision: {pack.import_review.decision}</span>
                  <span>Reconciliation: {pack.import_review.reconciliation?.status || "UNKNOWN"}</span>
                  <span>Coverage: {String(pack.import_review.coverage?.status || "UNKNOWN")}</span>
                </div>
                {pack.import_review.source_file_sha256 && (
                  <div className="mt-2 text-[10px] text-slate-500">Source SHA-256: {shortHash(pack.import_review.source_file_sha256)}</div>
                )}
              </section>
            )}

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
                        {event.normalized_payload?.review_kind === "RECONCILIATION_DECISION" && (
                          <div className="mt-2 text-[10px] text-amber-300 flex flex-wrap gap-x-3 gap-y-1">
                            <span>Decision: {String(event.normalized_payload.decision || "UNKNOWN")}</span>
                            <span>Source: {shortHash(event.normalized_payload.source_event_hash as string | undefined)}</span>
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
