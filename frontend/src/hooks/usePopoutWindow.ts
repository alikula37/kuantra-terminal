import { useCallback } from "react";
import { openPopout } from "../lib/desktop";

export const usePopoutWindow = () => {
  const popout = useCallback(
    async (panelId: string, title: string = "Kuantra Sub-Window", width: number = 1024, height: number = 700) => {
      try {
        await openPopout(panelId, `Kuantra Terminal - ${title}`, width, height);
      } catch (e) {
        console.warn("pop-out failed:", e);
      }
    },
    []
  );

  return { popout };
};
