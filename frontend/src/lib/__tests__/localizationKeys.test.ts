import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { instrumentUnitBasis } from "../positionMath";

const locales = ["en", "tr", "de"] as const;
const read = (lang: string) => JSON.parse(readFileSync(join(process.cwd(), "src", "locales", `${lang}.json`), "utf-8"));

describe("dynamic localization keys resolve for every verification value", () => {
  it("has a non-empty order_ticket.verification_* text for every unit basis", () => {
    const values = new Set([
      instrumentUnitBasis("BTCUSDT", { qtyUnit: "USD" }).verification,
      instrumentUnitBasis("BTCUSDT", { qtyUnit: "BASE" }).verification,
      instrumentUnitBasis("BTCUSDT", { serverVerified: true }).verification,
      instrumentUnitBasis("BTCUSDT").verification,
    ]);
    for (const lang of locales) {
      const orderTicket = read(lang).order_ticket;
      for (const value of values) {
        const text = orderTicket[`verification_${value}`];
        expect(text, `${lang} order_ticket.verification_${value}`).toBeTruthy();
        expect(text).not.toContain("verification_");
      }
    }
  });

  it("has texts for the monitor waiting reasons shown in the tracking panel", () => {
    const reasons = [
      "MARKET_DATA_DISABLED", "PROVIDER_RATE_LIMIT", "PROVIDER_ERROR",
      "WAITING_FRESH_PROVIDER_EVENT", "WAITING_PROVIDER_OBSERVATION",
    ];
    for (const lang of locales) {
      const tracking = read(lang).tracking;
      for (const reason of reasons) {
        expect(tracking[`wait_reason_${reason}`], `${lang} tracking.wait_reason_${reason}`).toBeTruthy();
      }
    }
  });
});
