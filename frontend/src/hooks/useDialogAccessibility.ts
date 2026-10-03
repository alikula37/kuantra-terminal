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
  nativeTabNavigation = false,
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

      const selector = nativeTabNavigation ? `${FOCUSABLE},summary` : FOCUSABLE;
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(selector))
        .filter((element) => nativeTabNavigation
          ? !element.closest('[hidden], [aria-hidden="true"]') && element.tabIndex >= 0
          : !element.hasAttribute("hidden") && element.getAttribute("aria-hidden") !== "true");
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      // WKWebView may omit buttons from its default Tab order. Opt-in dialogs
      // traverse explicitly; never change the user's macOS keyboard preference.
      if (nativeTabNavigation) {
        event.preventDefault();
        const current = focusable.indexOf(document.activeElement as HTMLElement);
        const next = current < 0 ? (event.shiftKey ? focusable.length - 1 : 0)
          : (current + (event.shiftKey ? -1 : 1) + focusable.length) % focusable.length;
        focusable[next].focus();
        return;
      }
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
  }, [dialogRef, initialFocusRef, onClose, nativeTabNavigation]);
}
