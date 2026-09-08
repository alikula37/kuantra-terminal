// @vitest-environment jsdom
import React, { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  useTelemetry: vi.fn(),
}));

vi.mock("../../hooks/useTelemetry", () => ({ useTelemetry: mocks.useTelemetry }));
vi.mock("../../context/I18nContext", () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      const values: Record<string, string> = {
        "settings.privacy_title": "PRIVACY TELEMETRY",
        "settings.pii_redaction_active": "PII Redaction: Active",
        "settings.telemetry_label": "Anonymous Error Reporting",
        "settings.telemetry_enabled": "OPT-IN ENABLED",
        "settings.telemetry_description": "Secrets are scrubbed before local spooling.",
        "settings.telemetry_queue_title": "Offline Crash Spool Queue",
        "settings.telemetry_queue_no_transport": "{count} reports are retained locally; external delivery is not configured.",
        "settings.telemetry_refresh": "Refresh",
        "settings.telemetry_export_description": "Package rotating logs with verified redaction.",
        "settings.telemetry_export_btn": "EXPORT REDACTED LOGS (.ZIP)",
      };
      return (values[key] || key).replace("{count}", String(params?.count ?? ""));
    },
  }),
}));

import { createRoot } from "react-dom/client";
import { SystemHealthSettings } from "../settings/SystemHealthSettings";

describe("SystemHealthSettings privacy truth", () => {
  let host: HTMLDivElement;
  let root: ReturnType<typeof createRoot>;

  beforeEach(() => {
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    mocks.useTelemetry.mockReturnValue({
      isOptedIn: true,
      queuedCrashes: 2,
      deliveryStatus: "NO_TRANSPORT",
      isLoading: false,
      updateConsent: vi.fn(),
      exportRedactedLogs: vi.fn(),
      refreshStatus: vi.fn(),
    });
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    mocks.useTelemetry.mockReset();
  });

  it("states that queued reports stay local when no delivery transport exists", async () => {
    await act(async () => root.render(<SystemHealthSettings />));

    expect(host.textContent).toContain("retained locally");
    expect(host.textContent).toContain("external delivery is not configured");
    expect(host.textContent).not.toContain("network reconnect");
  });
});
