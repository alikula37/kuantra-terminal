export interface TargetDraft { price: string; percent: string }
export interface TrackingClosure {
  target_id: string; qty: string; price: string; gross_pnl: string;
  observed_at: string; plan_revision: number;
}
export interface TrackingState {
  trade_id: string; symbol: string; side: string; revision: number; enabled: boolean;
  source_id: string | null; source_symbol: string | null;
  entry_price: string; initial_qty: string; remaining_qty: string; gross_pnl: string;
  targets: Array<TargetDraft & { id: string }>; closures: TrackingClosure[];
  stop_loss: string | null; basis: "LOCAL_ESTIMATE"; external_status?: string;
  qty_unit?: "USD" | "BASE" | "UNKNOWN";
  tracking_status?: string; armed_at?: string; unit_status?: "BASE_UNIT" | "USD_NOTIONAL" | "UNVERIFIED";
  monitor?: {
    enabled: boolean; wait_reason: string; last_error?: string | null;
    last_attempt_at?: number | null; last_observation_at?: number | null;
    next_poll_in_seconds?: number | null;
  };
  last_quote?: { price: string; observed_at: string } | null;
}

export function targetPayload(drafts: TargetDraft[]) {
  return drafts.filter(t => t.price !== "" || t.percent !== "").map(t => ({
    price: Number(t.price), percent: Number(t.percent),
  }));
}

export function validTargets(drafts: TargetDraft[], entry: number, side: string, stop: number | null) {
  if (!Number.isFinite(entry) || entry <= 0) return false;
  const long = side === "BUY" || side === "LONG";
  if (stop !== null && (!Number.isFinite(stop) || stop <= 0 || (long ? stop >= entry : stop <= entry))) return false;
  const targets = targetPayload(drafts);
  if (targets.length > 0 && drafts.some(t => t.price === "" || t.percent === "")) return false;
  if (targets.length > 3) return false;
  let previous = entry;
  for (const target of targets) {
    if (!Number.isFinite(target.price) || !Number.isFinite(target.percent) || target.price <= 0
        || target.percent <= 0 || target.percent > 100 || (long ? target.price <= previous : target.price >= previous)) return false;
    previous = target.price;
  }
  return targets.length === 0 || Math.abs(targets.reduce((n, t) => n + t.percent, 0) - 100) < 1e-9;
}

export function isTrackingState(value: unknown): value is TrackingState {
  if (!value || typeof value !== "object") return false;
  const s = value as TrackingState;
  return s.basis === "LOCAL_ESTIMATE" && typeof s.trade_id === "string"
    && typeof s.symbol === "string" && Number.isInteger(s.revision) && s.revision > 0
    && typeof s.enabled === "boolean" && Array.isArray(s.targets) && s.targets.length <= 3
    && ["BUY", "SELL", "LONG", "SHORT"].includes(s.side)
    && s.targets.every(t => typeof t.id === "string" && Number.isFinite(Number(t.price)) && Number(t.price) > 0
      && Number.isFinite(Number(t.percent)) && Number(t.percent) > 0 && Number(t.percent) <= 100)
    && Array.isArray(s.closures) && s.closures.every(c => typeof c.target_id === "string"
      && typeof c.observed_at === "string" && Number.isFinite(Number(c.qty)) && Number(c.qty) > 0
      && Number.isFinite(Number(c.price)) && Number(c.price) > 0)
    && [s.entry_price, s.initial_qty, s.remaining_qty, s.gross_pnl].every(v => typeof v === "string" && Number.isFinite(Number(v)))
    && Number(s.remaining_qty) >= 0;
}
