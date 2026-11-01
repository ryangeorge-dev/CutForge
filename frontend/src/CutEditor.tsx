import { useState } from 'react';
import { ticksPerSecond, time, type Cut, type Metadata } from './types';

export function CutEditor({ cut, metadata, busy, save }: {
  cut: Cut; metadata: Metadata; busy: boolean; save: (start: number, end: number) => void;
}) {
  const [start, setStart] = useState(cut.start);
  const [end, setEnd] = useState(cut.end);
  const rate = ticksPerSecond(metadata.rate);
  const unit = metadata.has_video ? 'frame' : 'sample';
  const valid = Number.isSafeInteger(start) && Number.isSafeInteger(end) && start >= 0 && end > start && end <= metadata.duration_ticks;
  return <form className="mt-4 border-t border-slate-600 pt-4" onSubmit={e => { e.preventDefault(); if (valid) save(start, end); }}>
    <h3 className="font-semibold mb-2">Adjust selected cut</h3>
    <p className="muted mb-3">Boundaries use exact {unit}s, counted from zero. The end is exclusive. Changing a boundary keeps this cut's current decision and can be undone.</p>
    <div className="grid grid-cols-2 gap-3">
      <label>Start {unit}<input aria-label={`Start ${unit}`} type="number" min={0} max={metadata.duration_ticks - 1} step={1} required value={Number.isNaN(start) ? '' : start} onChange={e => setStart(e.target.valueAsNumber)}/><span>{Number.isFinite(start) ? time(start / rate) : '—'}</span></label>
      <label>End {unit}<input aria-label={`End ${unit}`} type="number" min={1} max={metadata.duration_ticks} step={1} required value={Number.isNaN(end) ? '' : end} onChange={e => setEnd(e.target.valueAsNumber)}/><span>{Number.isFinite(end) ? time(end / rate) : '—'}</span></label>
    </div>
    {!valid && <p role="alert" className="mt-2">Start must precede end, within the source duration.</p>}
    <div className="flex gap-2 mt-3">
      <button disabled={busy || !valid || (start === cut.start && end === cut.end)} type="submit">Save boundaries</button>
      <button type="button" onClick={() => { setStart(cut.start); setEnd(cut.end); }}>Reset fields</button>
    </div>
  </form>;
}
