import { useCallback, useEffect, useRef, useState } from 'react';
import { download, post, request } from './api';
import { AnalysisSettings } from './AnalysisSettings';
import { MediaPreview } from './MediaPreview';
import { ReviewPanel } from './ReviewPanel';
import { ticksPerSecond, time, type Cut, type Job, type Project, type ProjectInfo, type ReviewAction, type Settings } from './types';

export default function App() {
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selectedId, setSelectedId] = useState<string>();
  const selected = project?.cuts.find(cut => cut.id === selectedId);
  const select = (cut: Cut) => setSelectedId(cut.id);
  const operation = useRef(false);
  const busy = working || !!job;

  const load = useCallback(async (id: string) => {
    const p = await request<Project>(`/projects/${id}`);
    setProject(p); setSelectedId(undefined);
    localStorage.setItem('cutforge-project', id);
  }, []);

  useEffect(() => {
    let active = true;
    async function init() {
      try {
        const list = await request<ProjectInfo[]>('/projects');
        if (!active) return;
        setProjects(list);
        const remembered = localStorage.getItem('cutforge-project');
        if (remembered && list.some(p => p.id === remembered)) await load(remembered);
        const rememberedJob = localStorage.getItem('cutforge-job');
        if (rememberedJob) {
          try { const pending = await request<Job>(`/jobs/${rememberedJob}`); if (active) setJob(pending); }
          catch { localStorage.removeItem('cutforge-job'); }
        }
      } catch (err) { if (active) setError(String(err)); }
    }
    void init();
    return () => { active = false; };
  }, [load]);

  useEffect(() => {
    if (!job) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const id = job.id;
    async function poll() {
      try {
        const status = await request<Job>(`/jobs/${id}`);
        if (!active) return;
        if (status.status === 'completed' || status.status === 'failed') {
          localStorage.removeItem('cutforge-job');
          if (status.status === 'failed') setError(status.error || 'Media job failed.');
          else {
            await load(status.project_id);
            setProjects(await request<ProjectInfo[]>('/projects'));
            setNotice(status.kind === 'import' ? 'Media copied and inspected. Ready for analysis.' : 'Analysis saved. Existing decisions have been preserved.');
          }
          if (active) setJob(null);
        } else { timer = setTimeout(poll, 700); }
      } catch (err) {
        if (active) { setError(`Job status unavailable; retrying. ${String(err)}`); timer = setTimeout(poll, 2000); }
      }
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [job?.id, load]);

  async function perform(action: () => Promise<void>) {
    if (operation.current || job) return;
    operation.current = true; setWorking(true); setError(''); setNotice('');
    try { await action(); } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { operation.current = false; setWorking(false); }
  }
  function rememberJob(value: Job) {
    localStorage.setItem('cutforge-job', value.id); setJob(value);
  }
  function importFile(file: File) {
    void perform(async () => {
      const form = new FormData(); form.append('file', file);
      rememberJob(await request<Job>('/import', { method: 'POST', body: form }));
    });
  }
  function analyze(settings: Settings) {
    if (!project) return;
    void perform(async () => rememberJob(await post<Job>(`/projects/${project.id}/analysis`, { revision: project.revision, settings })));
  }
  function decide(action: ReviewAction, cut_id?: string, boundaries?: { start: number; end: number }) {
    if (!project) return;
    void perform(async () => {
      const updated = await post<Project>(`/projects/${project.id}/review`, { revision: project.revision, action, cut_id, ...boundaries });
      setProject(updated); setNotice('Decisions saved.');
    });
  }
  const metadata = project?.metadata;
  const duration = metadata ? metadata.duration_ticks / ticksPerSecond(metadata.rate) : 0;

  return <main className="max-w-6xl mx-auto px-5 py-8 space-y-5">
    <header className="flex flex-wrap justify-between items-start gap-3">
      <div><h1 className="text-3xl font-bold tracking-tight">CutForge</h1><p className="muted mt-1">Review the pauses. Keep the story. Finish in Resolve.</p></div>
      <span className="badge">Local workspace · original media preserved</span>
    </header>
    <section className="panel flex flex-wrap gap-5 items-end">
      <label className="flex-1 min-w-56">Open saved project<select disabled={busy} value={project?.id || ''} onChange={e => { if (e.target.value) void perform(() => load(e.target.value)); }}>
        <option value="">Choose a project</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select></label>
      <label className="flex-1 min-w-56">Import one recording<input type="file" accept=".wav,.mp3,.mp4,.mov" disabled={busy} onChange={e => { const file = e.target.files?.[0]; if (file) importFile(file); e.target.value = ''; }}/></label>
    </section>
    {error && <div role="alert" className="notice error"><p>{error}</p><button className="mt-2" disabled={busy} onClick={() => { if (project) void perform(() => load(project.id)); else location.reload(); }}>Reload saved state</button></div>}
    {(busy || notice) && <p role="status" className="notice">{job ? `${job.kind === 'import' ? 'Inspecting media' : 'Detecting silences'}… You can leave this tab; completed work is saved locally.` : working ? 'Saving or transferring media…' : notice}</p>}
    {!project && <section className="panel py-12"><h2>Start with a recording</h2><p className="muted">Import WAV or MP3 narration, or an MP4/MOV video. CutForge copies it into a persistent workspace, finds silence, and exports your approved edits as an editable timeline.</p></section>}
    {project && metadata && <>
      <section className="panel">
        <h2 className="break-all">{project.name}</h2>
        <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 my-3">
          <div><dt>Source duration</dt><dd>{time(duration)}</dd></div>
          <div><dt>Approved removal</dt><dd>{time(project.summary.removed_seconds)}</dd></div>
          <div><dt>Final timeline</dt><dd>{time(project.summary.final_seconds)}</dd></div>
          <div><dt>Media</dt><dd>{[metadata.video_codec, metadata.audio_codec].filter(Boolean).join(' + ')}</dd></div>
        </dl>
        <p className="muted">{metadata.has_video && `${metadata.width} × ${metadata.height} · ${metadata.rate} fps · `}{metadata.has_audio ? `${metadata.sample_rate} Hz · ${metadata.channels} channels${metadata.channel_layout ? ` (${metadata.channel_layout})` : ''}` : 'No audio stream'}</p>
        {metadata.warnings.map(w => <p key={w} className="notice mt-2">{w}</p>)}
        <details className="mt-3 text-sm"><summary>Persistent media location</summary><p className="break-all mt-2">{project.media_path}</p><p className="muted mt-2">Export references this copy. Moving, renaming, or deleting it breaks playback and Resolve links. Keep the workspace or relink in Resolve.</p></details>
      </section>
      <div className="grid lg:grid-cols-2 gap-5 items-start">
        <MediaPreview key={project.id} project={project} selected={selected} select={select}/>
        <AnalysisSettings key={`${project.id}:${JSON.stringify(project.settings)}`} initial={project.settings} busy={busy} analyzed={project.analyzed} run={analyze}/>
      </div>
      <ReviewPanel project={project} busy={busy} selected={selected?.id} select={select} decide={decide}/>
      <section className="panel">
        <h2>Continue in DaVinci Resolve</h2>
        <p className="muted mb-4">Only accepted cuts are removed. Pending and rejected sections stay in the timeline. Export validates the XML and source ranges before downloading.</p>
        <div className="flex flex-wrap gap-3">
          <button className="primary" disabled={busy || project.summary.final_seconds <= 0} onClick={() => void perform(async () => {
            await download(`/projects/${project.id}/export?revision=${project.revision}`, 'cutforge.fcpxml'); setNotice('FCPXML validated and downloaded. Import it using File → Import → Timeline in Resolve.');
          })}>Export FCPXML</button>
          <button disabled={busy} onClick={() => void perform(() => download(`/projects/${project.id}/project.json`, 'cutforge-project.json'))}>Download project JSON</button>
        </div>
        {project.summary.final_seconds <= 0 && <p className="notice mt-3">Every section is removed. Restore or reject a cut to export a nonempty timeline.</p>}
        <p className="muted mt-3">FCPXML 1.7 · Editable source clips · See docs/resolve.md for import steps and verification status.</p>
      </section>
    </>}
  </main>;
}
