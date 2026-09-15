import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, apiUrl } from "../lib/backend";
import { useTranslation } from "../context/I18nContext";
import { TargetPlanFields } from "./TargetPlanFields";
import { isTrackingState, targetPayload, validTargets, type TargetDraft, type TrackingState } from "../lib/localTracking";
import { formatIstanbulDateTime } from "../lib/tradeTime";
import type { Trade } from "../types";

const sources = ["binance_public", "bybit_public", "yahoo_public", "stooq_public", "biquote_public"];

export function LocalTrackingPanel({ editTrade, onEditorClose }: {
  editTrade: Trade | null; onEditorClose: () => void;
}) {
  const { t, locale } = useTranslation();
  const [states, setStates] = useState<TrackingState[]>([]);
  const [error, setError] = useState(false);
  const [editor, setEditor] = useState<{ trade: Trade; plan: TrackingState | null; history: Array<{ state: TrackingState }> } | null>(null);
  const [targets, setTargets] = useState<TargetDraft[]>([]);
  const [enabled, setEnabled] = useState(true);
  const [stop, setStop] = useState("");
  const [source, setSource] = useState("");
  const [sourceSymbol, setSourceSymbol] = useState("");
  const [manualPrice, setManualPrice] = useState("");
  const [editorError, setEditorError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const loadRef = useRef<AbortController | null>(null);
  const editorLoadRef = useRef<AbortController | null>(null);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    if (loadRef.current) return;
    const controller = new AbortController();
    loadRef.current = controller;
    try {
      const response = await apiFetch(apiUrl("/api/v1/local-tracking"), { signal: controller.signal });
      const data: unknown = await response.json();
      if (!response.ok || !Array.isArray(data) || !data.every(isTrackingState)) throw new Error();
      if (!controller.signal.aborted) { setStates(data); setError(false); }
    } catch { if (!controller.signal.aborted) setError(true); }
    finally { if (loadRef.current === controller) loadRef.current = null; }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => { mounted.current = false; clearInterval(timer); loadRef.current?.abort(); editorLoadRef.current?.abort(); };
  }, [refresh]);

  const openEditor = useCallback(async (trade: Trade) => {
    editorLoadRef.current?.abort();
    const controller = new AbortController();
    editorLoadRef.current = controller;
    setEditorError(null);
    try {
      const res = await apiFetch(apiUrl(`/api/v1/trades/${encodeURIComponent(trade.id)}/tracking`), { signal: controller.signal });
      const data = await res.json();
      if (!res.ok || !(data.plan === null || isTrackingState(data.plan)) || !Array.isArray(data.history)
          || !data.history.every((h: { state?: unknown }) => isTrackingState(h.state))) throw new Error();
      if (controller.signal.aborted) return;
      const plan: TrackingState | null = data.plan;
      setEditor({ trade, plan, history: data.history });
      setTargets(plan ? plan.targets : [{ price: trade.take_profit ? String(trade.take_profit) : "", percent: "" }]);
      setEnabled(plan?.enabled ?? true);
      setStop(plan ? plan.stop_loss || "" : trade.stop_loss ? String(trade.stop_loss) : "");
      setSource(plan?.source_id || (sources.includes(trade.price_source || "") ? trade.price_source! : ""));
      setSourceSymbol(plan?.source_symbol || trade.price_source_symbol || "");
      setManualPrice("");
    } catch { if (!controller.signal.aborted) setError(true); }
  }, []);

  useEffect(() => { if (editTrade) void openEditor(editTrade); }, [editTrade, openEditor]);
  useEffect(() => {
    if (editor && dialog.current) {
      returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      if (typeof dialog.current.showModal === "function" && !dialog.current.open) dialog.current.showModal();
      else dialog.current.setAttribute("open", "");
      dialog.current.querySelector<HTMLButtonElement>("button")?.focus();
    }
  }, [editor]);

  const close = () => {
    if (busy) return;
    editorLoadRef.current?.abort(); setEditor(null); onEditorClose(); returnFocus.current?.focus();
  };
  const submit = async (manual: boolean) => {
    if (!editor || busy) return;
    const plan = editor.plan;
    const entry = Number(plan?.entry_price ?? editor.trade.entry_price);
    const side = plan?.side ?? editor.trade.side;
    if ((!manual && !validTargets(targets, entry, side, stop === "" ? null : Number(stop)))
        || (manual && (!plan || !Number.isFinite(Number(manualPrice)) || Number(manualPrice) <= 0))) {
      setEditorError(t("tracking.invalid")); return;
    }
    setBusy(true); setEditorError(null);
    try {
      const response = await apiFetch(apiUrl(`/api/v1/trades/${encodeURIComponent(editor.trade.id)}/tracking${manual ? "/close" : ""}`), {
        method: manual ? "POST" : "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(manual ? { expected_revision: plan!.revision, price: Number(manualPrice) } : {
          expected_revision: plan?.revision ?? 0, enabled, targets: targetPayload(targets),
          stop_loss: stop === "" ? null : Number(stop), source_id: source || null, source_symbol: sourceSymbol || null,
        }),
      });
      if (!response.ok) { setEditorError(t(response.status === 409 ? "tracking.conflict" : "tracking.invalid")); return; }
      if (!isTrackingState(await response.json())) throw new Error();
      if (mounted.current) { setEditor(null); onEditorClose(); returnFocus.current?.focus(); void refresh(); }
    } catch { if (mounted.current) setEditorError(t("tracking.error")); }
    finally { if (mounted.current) setBusy(false); }
  };

  const current = editor && states.find(s => s.trade_id === editor.trade.id);
  const shownPrice = current?.last_quote ? Number(current.last_quote.price) : null;
  const alreadyReached = editor && shownPrice !== null && (targets.some((target, index) => Number(target.price) > 0
    && !editor.plan?.closures.some(c => c.target_id === `TP${index + 1}`)
    && (["BUY", "LONG"].includes(editor.trade.side) ? shownPrice >= Number(target.price) : shownPrice <= Number(target.price)))
    || stop !== "" && (["BUY", "LONG"].includes(editor.trade.side) ? shownPrice <= Number(stop) : shownPrice >= Number(stop)));
  const completed = editor?.plan && Number(editor.plan.remaining_qty) === 0;
  const inactive = editor && (editor.trade.status !== "OPEN" || current?.external_status !== undefined && current.external_status !== "OPEN");

  return <section className="bg-[#111722] text-white border border-surface-border p-4 rounded space-y-3" data-testid="local-tracking">
    <h3 className="font-semibold text-base">{t("tracking.title")}</h3>
    <p className="k-help">{t("tracking.disclaimer")}</p>
    {error && <p role="alert" className="text-loss">{t("tracking.error")} <button onClick={() => void refresh()}>{t("tracking.reload")}</button></p>}
    {!states.length && !error && <p className="text-sm text-slate-400">{t("tracking.empty")}</p>}
    <div className="space-y-2">{states.map(state => <article key={state.trade_id} className="rounded border border-surface-border p-3 text-sm">
      <div className="flex flex-wrap justify-between gap-2">
        <span className="font-semibold">{state.symbol} · {state.side}</span>
        <span>{t(`tracking.status_${state.tracking_status || "WAITING_QUOTE"}`)}</span>
        <button className="text-accent" onClick={() => void openEditor({ id: state.trade_id, symbol: state.symbol,
          side: state.side as Trade["side"], entry_price: Number(state.entry_price), qty: Number(state.initial_qty),
          entry_time: "", status: (state.external_status || "OPEN") as Trade["status"] })}>{t("tracking.edit")}</button>
      </div>
      <p>{t("tracking.remaining")}: {state.remaining_qty} / {state.initial_qty} · {t("tracking.gross")}: {state.gross_pnl}</p>
      <p className="k-help">{t("tracking.started_at")}: {formatIstanbulDateTime(state.armed_at, locale)}</p>
      {state.unit_status === "UNVERIFIED" && <p className="k-help text-amber-300">{t("tracking.unit_unverified")}</p>}
      <p className="k-help">{state.source_id ? t(`tracking.${state.source_id}`) : t("tracking.no_source")} · {state.source_symbol}</p>
      {state.targets.map(target => <span className="inline-block mr-4" key={target.id}>
        {target.id}: {target.price} ({target.percent}%) {state.closures.some(c => c.target_id === target.id) ? t("tracking.hit") : ""}
      </span>)}
    </article>)}</div>
    {editor && <dialog ref={dialog} onCancel={e => { e.preventDefault(); close(); }}
      aria-modal="true" onKeyDown={e => {
        if (e.key === "Escape") { e.preventDefault(); close(); }
        if (e.key !== "Tab") return;
        const items = Array.from(e.currentTarget.querySelectorAll<HTMLElement>("button:not(:disabled), input:not(:disabled), select:not(:disabled), summary"));
        const first = items[0], last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
      }}
      className="bg-[#111722] text-white rounded-lg border border-surface-border p-5 w-full max-w-xl max-h-[85vh] overflow-y-auto backdrop:bg-black/60"
      aria-labelledby="tracking-editor-title">
      <div className="flex justify-between gap-3 mb-3"><h3 id="tracking-editor-title">{t("tracking.edit")} · {editor.trade.symbol}</h3>
        <button type="button" onClick={close} disabled={busy}>{t("tracking.dismiss")}</button></div>
      <p className="text-xs text-slate-400 mb-3">{t("tracking.disclaimer")}</p>
      {editor.plan && <p className="text-sm mb-2">{t("tracking.remaining")}: {editor.plan.remaining_qty} / {editor.plan.initial_qty}</p>}
      <form onSubmit={e => { e.preventDefault(); void submit(false); }} className="space-y-3">
        <fieldset disabled={busy || Boolean(completed) || Boolean(inactive)} className="space-y-3">
          <label className="flex gap-2"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />{t("tracking.enabled")}</label>
          <label className="block">{t("tracking.stop")}<input aria-label={t("tracking.stop")} className="block bg-[#0b0e14] border border-surface-border p-2 rounded w-full"
            type="number" step="any" value={stop} onChange={e => setStop(e.target.value)} /></label>
          <TargetPlanFields targets={targets} onChange={setTargets} locked={editor.plan?.closures.map(c => c.target_id)} />
          <label className="block">{t("tracking.source")}<select aria-label={t("tracking.source")} value={source}
            disabled={Boolean(editor.plan?.closures.length)} onChange={e => { setSource(e.target.value); setSourceSymbol(""); }}
            className="block w-full bg-[#0b0e14] border border-surface-border p-2 rounded">
            <option value="">{t("tracking.no_source")}</option>{sources.map(s => <option key={s} value={s}>{t(`tracking.${s}`)}</option>)}
          </select></label>
          <label className="block">{t("tracking.source_symbol")}<input aria-label={t("tracking.source_symbol")} value={sourceSymbol}
            disabled={!source || Boolean(editor.plan?.closures.length)} maxLength={128} onChange={e => setSourceSymbol(e.target.value)}
            className="block w-full bg-[#0b0e14] border border-surface-border p-2 rounded" /></label>
          <p className="text-xs text-slate-400">{t("tracking.source_help")}</p>
          {alreadyReached && <p role="status" className="text-amber-400">{t("tracking.already_reached")}</p>}
          <button type="submit" className="bg-accent/20 text-accent px-4 py-2 rounded">{t("tracking.save")}</button>
          {editor.plan && <div className="border-t border-surface-border pt-3">
            <label>{t("tracking.manual_price")}<input type="number" step="any" value={manualPrice} onChange={e => setManualPrice(e.target.value)}
              aria-label={t("tracking.manual_price")} className="block w-full bg-[#0b0e14] border border-surface-border p-2 rounded" /></label>
            <button type="button" onClick={() => void submit(true)} className="text-loss p-2">{t("tracking.manual_close")}</button>
          </div>}
        </fieldset>
        {editorError && <p role="alert" className="text-loss">{editorError} <button type="button" onClick={() => void openEditor(editor.trade)}>{t("tracking.reload")}</button></p>}
      </form>
      <details className="mt-3"><summary>{t("tracking.history")}</summary>
        {editor.history.slice(-20).map(h => <p className="text-xs my-1" key={h.state.revision}>
          {t("tracking.revision")}: {h.state.revision} · {t("tracking.remaining")}: {h.state.remaining_qty} · {t("tracking.gross")}: {h.state.gross_pnl}
          <br />{h.state.targets.map(target => `${target.id}: ${target.price} (${target.percent}%)`).join(" · ")}
          {" · "}{t("tracking.stop")}: {h.state.stop_loss ?? "—"}
        </p>)}
        {editor.plan?.closures.map((c, i) => <p className="text-sm my-1" key={i}>{c.target_id} · {c.qty} @ {c.price} · {formatIstanbulDateTime(c.observed_at, locale)}</p>)}
      </details>
    </dialog>}
  </section>;
}
