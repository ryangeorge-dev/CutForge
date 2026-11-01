import type { Cut, Project, ReviewAction } from './types';
import { ticksPerSecond, time, visibleCuts } from './types';
import { CutEditor } from './CutEditor';

export function ReviewPanel({ project, busy, selected, select, decide }: {
  project: Project; busy: boolean; selected?: string;
  select: (cut: Cut) => void; decide: (action: ReviewAction, cut?: string, boundaries?: { start: number; end: number }) => void;
}) {
  const cuts = visibleCuts(project.cuts);
  const rate = ticksPerSecond(project.metadata.rate);
  const editing = project.cuts.find(cut => cut.id === selected);
  return <section className="panel">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2>Review suggested cuts <span className="muted">({cuts.length})</span></h2>
      <div className="flex gap-2">
        <button disabled={busy || !project.history.length} onClick={() => decide('undo')}>Undo</button>
        <button disabled={busy || !project.future.length} onClick={() => decide('redo')}>Redo</button>
      </div>
    </div>
    <p className="muted mb-4">Accepted = remove from export. Rejected or pending = keep. Decisions save automatically.</p>
    <div className="flex flex-wrap gap-2 mb-4">
      <button disabled={busy || !cuts.length} onClick={() => decide('accept_all')}>Accept all cuts</button>
      <button disabled={busy || !cuts.length} onClick={() => decide('reject_all')}>Reject all cuts</button>
      <button disabled={busy || !cuts.length} onClick={() => decide('restore')}>Restore all suggestions</button>
    </div>
    {cuts.some(c => !c.current) && <p className="notice mb-3">Decisions from an earlier analysis are retained and still apply. Review the marked rows to change them.</p>}
    {!cuts.length && <p className="muted py-5">{project.analyzed ? 'No silence cuts suggested. The complete source will be exported.' : 'Run silence detection to find suggested cuts.'}</p>}
    {!!cuts.length && <div className="overflow-x-auto max-h-[34rem]">
      <table className="w-full text-sm">
        <thead><tr><th>Preview</th><th>Start</th><th>End</th><th>Removed</th><th>Decision</th><th>Review</th></tr></thead>
        <tbody>{cuts.map((cut, index) => <tr key={cut.id} className={selected === cut.id ? 'selected-row' : ''}>
          <td><button aria-label={`Select cut ${index + 1}`} aria-pressed={selected === cut.id} onClick={() => select(cut)}>Cut {index + 1}</button></td>
          <td className="tabular-nums">{time(cut.start / rate)}</td><td className="tabular-nums">{time(cut.end / rate)}</td>
          <td className="tabular-nums">{((cut.end - cut.start) / rate).toFixed(3)} s</td>
          <td><span className={`badge ${cut.decision}`}>{cut.decision}</span>{!cut.current && <small className="block mt-1">Earlier analysis</small>}{cut.adjusted && <small className="block">Adjusted boundaries</small>}</td>
          <td><div className="flex gap-2">
            <button aria-label={`Accept cut ${index + 1}`} disabled={busy || cut.decision === 'accepted'} onClick={() => decide('accept', cut.id)}>Accept</button>
            <button aria-label={`Reject cut ${index + 1}`} disabled={busy || cut.decision === 'rejected'} onClick={() => decide('reject', cut.id)}>Reject</button>
          </div></td>
        </tr>)}</tbody>
      </table>
    </div>}
    {editing && <CutEditor key={`${editing.id}:${editing.start}:${editing.end}`} cut={editing} metadata={project.metadata} busy={busy} save={(start, end) => decide('adjust', editing.id, { start, end })}/>}
  </section>;
}
