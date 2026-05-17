const FORMATTER = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: true,
});

export function fmtIST(iso: string | Date): string {
  const d = typeof iso === 'string' ? new Date(iso) : iso;
  if (Number.isNaN(d.getTime())) {
    // Fail loud — a bad timestamp upstream is a bug we want surfaced,
    // not silently rendered as a placeholder.
    throw new Error(`Invalid date: ${String(iso)}`);
  }
  return FORMATTER.format(d);
}
