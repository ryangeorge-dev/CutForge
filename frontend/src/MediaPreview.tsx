import { useCallback, useEffect, useRef, useState } from 'react';
import type { Cut, Project } from './types';
import { ticksPerSecond, time } from './types';
import { mergeRanges, previewStep, previewWindow, roughCutStep, type Preview, type Range } from './preview';
import { SourceTimeline } from './SourceTimeline';

export function MediaPreview({ project, selected, select }: { project: Project; selected?: Cut; select: (cut: Cut) => void }) {
  const media = useRef<HTMLVideoElement | HTMLAudioElement | null>(null);
  const preview = useRef<Preview | null>(null);
  const roughCut = useRef<Range[] | null>(null);
  const [mode, setMode] = useState('Full source playback');
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  const [position, setPosition] = useState(0);
  const rate = ticksPerSecond(project.metadata.rate);
  const duration = project.metadata.duration_ticks / rate;

  const advancePreview = useCallback(() => {
    const element = media.current;
    if (!element || element.paused || element.seeking || (!preview.current && !roughCut.current)) return;
    const step = preview.current ? previewStep(element.currentTime, preview.current) : roughCutStep(element.currentTime, roughCut.current!, duration);
    if (step.stop) {
      element.pause(); preview.current = null; roughCut.current = null; setMode('Preview finished');
    } else if (step.seek !== undefined) element.currentTime = step.seek;
  }, [duration]);

  useEffect(() => {
    let frame: number;
    const tick = () => {
      advancePreview();
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [advancePreview]);

  useEffect(() => {
    media.current?.pause();
    preview.current = null;
    roughCut.current = null;
    setMode('Full source playback');
  }, [selected?.id, project.revision]);

  async function play(edited: boolean) {
    if (!selected || !media.current) return;
    const plan = previewWindow(selected.start / rate, selected.end / rate, duration, edited);
    if (edited && plan.cutStart <= 0 && plan.cutEnd >= duration) {
      setMode('This cut removes the entire recording; there is no retained media to preview.');
      return;
    }
    preview.current = plan;
    roughCut.current = null;
    media.current.currentTime = edited && plan.start >= plan.cutStart ? plan.cutEnd : plan.start;
    setMode(edited ? 'Edited transition · skipping selected cut' : 'Original section · no cut');
    try { await media.current.play(); } catch { setError('Playback could not start. Try the native play control or a different browser.'); }
  }

  async function playRoughCut() {
    if (!media.current) return;
    const cuts = mergeRanges(project.cuts.filter(c => c.decision === 'accepted').map(c => ({ start: c.start / rate, end: c.end / rate })));
    const first = roughCutStep(0, cuts, duration);
    if (first.stop) { setMode('No retained media to preview. Restore or reject a cut.'); return; }
    preview.current = null;
    roughCut.current = cuts;
    media.current.currentTime = first.seek ?? 0;
    setMode('Rough cut · skipping all accepted removals');
    try { await media.current.play(); } catch { setError('Playback could not start. Try the native play control or a different browser.'); }
  }

  function seek(seconds: number) {
    if (!media.current) return;
    preview.current = null; roughCut.current = null;
    media.current.currentTime = seconds; setPosition(seconds); setMode('Full source playback');
  }

  const props = {
    src: `/api/projects/${project.id}/media`, controls: true, preload: 'metadata',
    onLoadedMetadata: () => { setReady(true); setError(''); },
    onError: () => { setReady(false); setError('This browser cannot preview the media, or the workspace copy is missing. Analysis and export can still work for codecs supported by FFmpeg and Resolve. Try another browser and check the media path below.'); },
    onEnded: () => { preview.current = null; roughCut.current = null; setMode('Playback finished'); },
    // Safari/background tabs can throttle animation frames. Media timeupdate
    // still supplies a coarser fallback for the same skip/stop logic.
    onTimeUpdate: () => { advancePreview(); if (media.current) setPosition(media.current.currentTime); },
    className: 'w-full rounded-lg bg-black',
  };
  return <section className="panel" aria-label="Media preview">
    <h2>Preview</h2>
    {project.metadata.has_video
      ? <video {...props} ref={el => { media.current = el; }} className={`${props.className} max-h-96`} />
      : <audio {...props} ref={el => { media.current = el; }} />}
    {error && <p role="alert" className="notice">{error}</p>}
    <p className="muted mt-3">{selected ? `Selected cut: ${time(selected.start / rate)}–${time(selected.end / rate)}` : 'Select a cut below to compare the transition.'}</p>
    <div className="flex flex-wrap gap-2 my-3">
      <button disabled={!selected || !ready} onClick={() => void play(false)}>Play original</button>
      <button disabled={!selected || !ready} onClick={() => void play(true)}>Preview edit</button>
      <button disabled={!ready || project.summary.final_seconds <= 0} onClick={() => void playRoughCut()}>Preview rough cut</button>
      <button onClick={() => { preview.current = null; roughCut.current = null; media.current?.pause(); setMode('Full source playback'); }}>Stop preview</button>
    </div>
    <p role="status" className="text-sm">{mode}</p>
    <p className="muted mt-2">Preview includes up to 3 seconds on each side. Browser seeking is approximate; export uses exact source boundaries.</p>
    <SourceTimeline cuts={project.cuts} rate={rate} duration={duration} position={position} selected={selected?.id} select={select} seek={seek} ready={ready}/>
  </section>;
}
