import { time, visibleCuts, type Cut } from './types';

export function SourceTimeline({ cuts, rate, duration, position, selected, select, seek, ready }: {
  cuts: Cut[]; rate: number; duration: number; position: number; selected?: string;
  select: (cut: Cut) => void; seek: (seconds: number) => void; ready: boolean;
}) {
  return <div className="mt-4" aria-label="Interactive source timeline">
    <div className="flex justify-between text-sm mb-2"><span>Source timeline</span><span className="tabular-nums">{time(position)} / {time(duration)}</span></div>
    <div className="relative h-10 rounded border border-slate-500 bg-slate-900 overflow-hidden">
      {visibleCuts(cuts).map((cut, i) => <button key={cut.id} aria-label={`Timeline cut ${i + 1}: ${cut.decision}`} aria-pressed={selected === cut.id}
        title={`${time(cut.start / rate)}–${time(cut.end / rate)} · ${cut.decision}`}
        className={`absolute top-0 h-full p-0 min-w-1 rounded-none ${cut.decision} ${selected === cut.id ? 'ring-2 ring-inset ring-white z-10' : ''}`}
        style={{ left: `${cut.start / rate / duration * 100}%`, width: `${(cut.end - cut.start) / rate / duration * 100}%` }}
        onClick={() => select(cut)} />)}
      <span aria-hidden="true" className="absolute top-0 h-full w-0.5 bg-white pointer-events-none z-20" style={{ left: `${Math.min(100, position / duration * 100)}%` }}/>
    </div>
    <input aria-label="Seek source timeline" type="range" min={0} max={duration} step={1 / rate} value={position} disabled={!ready} onChange={e => seek(Number(e.target.value))}/>
    <p className="muted">Select a colored region to review it; drag the seek bar to scrub. Green: accepted removal · purple: rejected · amber: pending.</p>
  </div>;
}
