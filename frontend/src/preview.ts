/** Playback is approximate. Exact frame/sample arithmetic belongs to the backend. */
export type Preview = { start: number; end: number; cutStart: number; cutEnd: number; edited: boolean };
export function previewWindow(start: number, end: number, duration: number, edited: boolean, context = 3): Preview {
  return { start: Math.max(0, start - context), end: Math.min(duration, end + context), cutStart: start, cutEnd: end, edited };
}
export function previewStep(current: number, preview: Preview): { seek?: number; stop?: boolean } {
  if (current >= preview.end) return { stop: true };
  if (preview.edited && current >= preview.cutStart && current < preview.cutEnd) {
    return preview.cutEnd >= preview.end ? { stop: true } : { seek: preview.cutEnd };
  }
  return {};
}

export type Range = { start: number; end: number };
export function mergeRanges(ranges: Range[]): Range[] {
  const result: Range[] = [];
  for (const range of [...ranges].filter(r => r.end > r.start).sort((a, b) => a.start - b.start)) {
    const previous = result.at(-1);
    if (previous && range.start <= previous.end) previous.end = Math.max(previous.end, range.end);
    else result.push({ ...range });
  }
  return result;
}

export function roughCutStep(current: number, cuts: Range[], duration: number): { seek?: number; stop?: boolean } {
  if (current >= duration) return { stop: true };
  // Callers merge once when playback starts, not on every animation frame.
  const cut = cuts.find(c => current >= c.start && current < c.end);
  if (!cut) return {};
  return cut.end >= duration ? { stop: true } : { seek: cut.end };
}
