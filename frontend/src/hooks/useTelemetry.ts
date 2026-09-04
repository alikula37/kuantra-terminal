import { useState, useEffect, useCallback } from "react";
import { apiFetch, apiUrl } from "../lib/backend";
import { downloadFromBackend } from "../lib/desktop";

export const useTelemetry = () => {
  const [isOptedIn, setIsOptedIn] = useState<boolean>(false);
  const [queuedCrashes, setQueuedCrashes] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchStatus = useCallback(() => {
    apiFetch(apiUrl("/api/v1/telemetry/status"))
      .then((res) => res.json())
      .then((data) => {
        setIsOptedIn(data.opt_in);
        setQueuedCrashes(data.queued_crashes);
        setIsLoading(false);
      })
      .catch(() => {
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const updateConsent = async (optIn: boolean) => {
    setIsOptedIn(optIn);
    try {
      await apiFetch(apiUrl("/api/v1/telemetry/consent"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ opt_in: optIn }),
      });
      fetchStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const reportCrash = async (errorType: string, message: string, stackTrace: string) => {
    try {
      await apiFetch(apiUrl("/api/v1/telemetry/spool-crash"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          error_type: errorType,
          message,
          stack_trace: stackTrace,
        }),
      });
      fetchStatus();
    } catch (e) {
      console.error("Offline spool error:", e);
    }
  };

  const exportRedactedLogs = () => {
    downloadFromBackend("/api/v1/telemetry/export-logs", "kuantra_diagnostics_redacted.zip").then((ok) => {
      if (!ok) console.warn("Redacted log export was cancelled or failed.");
    });
  };

  return {
    isOptedIn,
    queuedCrashes,
    isLoading,
    updateConsent,
    reportCrash,
    exportRedactedLogs,
    refreshStatus: fetchStatus,
  };
};