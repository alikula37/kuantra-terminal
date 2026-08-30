import { useCallback } from "react";

export const usePopoutWindow = () => {
  const popout = useCallback(
    async (
      panelId: string,
      title: string = "Kuantra Sub-Window",
      width: number = 1024,
      height: number = 700
    ) => {
      const windowLabel = `win-${panelId.toLowerCase().replace(/[^a-z0-9]/g, "-")}`;
      const targetUrl = `/?popout=${encodeURIComponent(panelId)}`;

      // Check if Tauri runtime is available
      if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__) {
        try {
          const { invoke } = await import("@tauri-apps/api/core");
          await invoke("create_popout_window", {
            label: windowLabel,
            title: `Kuantra Terminal - ${title}`,
            url: targetUrl,
            width,
            height,
          });
          return;
        } catch (e) {
          console.warn("Tauri window pop-out fallback to browser window:", e);
        }
      }

      // Web Browser Fallback
      window.open(
        targetUrl,
        windowLabel,
        `width=${width},height=${height},menubar=no,status=no,toolbar=no`
      );
    },
    []
  );

  return { popout };
};