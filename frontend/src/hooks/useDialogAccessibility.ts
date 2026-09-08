import { useEffect } from "react";

type ElementRef = { current: HTMLElement | null };

const FOCUSABLE = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex=\"-1\"])",
].join(",");

/** Keep modal keyboard behavior local and deterministic across native WebViews. */
export function useDialogAccessibility(
  dialogRef: ElementRef,
  onClose: () => void,
  initialFocusRef?: ElementRef,
): void {
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return undefined;

    const initialTarget = initialFocusRef?.current || dialog.querySelector<HTMLElement>(FOCUSABLE);
    initialTarget?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE))
        .filter((element) => !element.hasAttribute("hidden") && element.getAttribute("aria-hidden") !== "true");
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [dialogRef, initialFocusRef, onClose]);
}
