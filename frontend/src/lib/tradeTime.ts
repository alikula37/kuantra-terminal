/**
 * Turkey-time trade date handling.
 *
 * User-entered and user-displayed trade times use Europe/Istanbul while the
 * backend stores timezone-aware UTC.  The helpers below never depend on the
 * machine's local timezone, so a pilot Mac configured elsewhere still sees and
 * enters Turkey time.
 */

export const ISTANBUL_TZ = "Europe/Istanbul";
export const MINUTE_TOLERANCE_MS = 45_000;

interface DateParts {
  year: string;
  month: string;
  day: string;
  hour: string;
  minute: string;
  second: string;
}

function partsInZone(date: Date, timeZone: string): DateParts {
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const parts: Partial<DateParts> = {};
  for (const part of formatter.formatToParts(date)) {
    if (part.type !== "literal") parts[part.type as keyof DateParts] = part.value;
  }
  return {
    year: parts.year || "1970",
    month: parts.month || "01",
    day: parts.day || "01",
    hour: parts.hour === "24" ? "00" : parts.hour || "00",
    minute: parts.minute || "00",
    second: parts.second || "00",
  };
}

export function zoneOffsetMs(date: Date, timeZone: string = ISTANBUL_TZ): number {
  const parts = partsInZone(date, timeZone);
  const asUtc = Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
    Number(parts.second),
  );
  return asUtc - date.getTime();
}

/** ``YYYY-MM-DDTHH:mm`` in Istanbul, suitable for a datetime-local input. */
export function istanbulInputValue(date: Date = new Date()): string {
  const parts = partsInZone(date, ISTANBUL_TZ);
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

/** Convert a datetime-local wall time in Istanbul into an ISO UTC string. */
export function istanbulInputToUtcIso(value: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value.trim());
  if (!match) return null;
  const [, year, month, day, hour, minute] = match;
  const wallAsUtc = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    0,
    0,
  );
  if (!Number.isFinite(wallAsUtc)) return null;
  const offset = zoneOffsetMs(new Date(wallAsUtc), ISTANBUL_TZ);
  return new Date(wallAsUtc - offset).toISOString();
}

/** Convert a stored UTC ISO string into an Istanbul datetime-local value. */
export function utcIsoToIstanbulInput(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return istanbulInputValue(date);
}

function localeTag(locale?: string): string {
  if (!locale) return "tr-TR";
  const normalized = locale.toLowerCase();
  if (normalized.startsWith("tr")) return "tr-TR";
  if (normalized.startsWith("de")) return "de-DE";
  return "en-GB";
}

export function formatIstanbulDateTime(
  iso: string | null | undefined,
  locale?: string,
): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(localeTag(locale), {
    timeZone: ISTANBUL_TZ,
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatIstanbulDate(iso: string | null | undefined, locale?: string): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(localeTag(locale), {
    timeZone: ISTANBUL_TZ,
    dateStyle: "medium",
  }).format(date);
}

/** Istanbul calendar day key (``YYYY-MM-DD``) for filters and daily grouping. */
export function istanbulDateKey(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  const parts = partsInZone(date, ISTANBUL_TZ);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

/** True when a datetime-local Istanbul value is clearly in the future. */
export function isFutureIstanbulInput(
  value: string,
  now: Date = new Date(),
): boolean {
  const utc = istanbulInputToUtcIso(value);
  if (!utc) return false;
  return new Date(utc).getTime() > now.getTime() + MINUTE_TOLERANCE_MS;
}

export function relativeAgeLabel(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return "";
  const age = Math.max(0, Math.round(seconds));
  if (age < 60) return `${age}s`;
  if (age < 3600) return `${Math.round(age / 60)}m`;
  return `${Math.round(age / 3600)}h`;
}
