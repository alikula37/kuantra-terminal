import { describe, expect, it } from "vitest";
import { telemetryQueueCopy } from "../settings/SystemHealthSettings";

describe("telemetry queue truth copy", () => {
  it("keeps an empty queue explicit", () => {
    expect(telemetryQueueCopy(0, "NO_TRANSPORT")).toEqual({
      key: "settings.telemetry_queue_empty",
    });
  });

  it("does not promise delivery when no transport exists", () => {
    expect(telemetryQueueCopy(2, "NO_TRANSPORT")).toEqual({
      key: "settings.telemetry_queue_no_transport",
      params: { count: 2 },
    });
  });

  it("keeps opted-out delivery explicit", () => {
    expect(telemetryQueueCopy(1, "OPT_OUT")).toEqual({
      key: "settings.telemetry_queue_opt_out",
      params: { count: 1 },
    });
  });
});
