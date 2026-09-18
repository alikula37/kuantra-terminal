import type { Trade } from "../types";

/**
 * Merge live position updates (websocket feed) into the server-loaded rows.
 *
 * The live feed carries only price fields and must never strip metadata such
 * as `record_mode`, `qty_unit`, `sizing` or stop/target levels from the rows
 * the journal/dashboard already loaded.  Rows without a matching live update
 * are kept as-is so a dashboard refresh never loses an open position.
 */
export function mergePositionUpdates(existing: Trade[], updates: unknown): Trade[] {
  if (!Array.isArray(updates) || updates.length === 0) return existing;
  const byId = new Map<string, Record<string, unknown>>();
  for (const update of updates) {
    if (update && typeof update === "object" && typeof (update as Record<string, unknown>).id === "string") {
      byId.set(String((update as Record<string, unknown>).id), update as Record<string, unknown>);
    }
  }
  if (byId.size === 0) return existing;
  return existing.map((row) => {
    const update = byId.get(String(row.id));
    return update ? ({ ...row, ...update } as Trade) : row;
  });
}
