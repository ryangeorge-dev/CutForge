export type Decision = 'pending' | 'accepted' | 'rejected';
export type Cut = { id: string; start: number; end: number; decision: Decision; current: boolean; adjusted?: boolean };
export type CutState = Pick<Cut, 'decision' | 'start' | 'end' | 'adjusted'>;
export type Settings = { threshold_db: number; min_silence: number; padding: number };
export type Metadata = {
  duration_ticks: number; rate: string; has_video: boolean; has_audio: boolean;
  video_codec: string | null; audio_codec: string | null;
  width: number | null; height: number | null; sample_rate: number | null;
  channels: number | null; channel_layout: string | null; warnings: string[];
};
export type Project = {
  id: string; name: string; metadata: Metadata; settings: Settings; cuts: Cut[];
  history: Record<string, Decision | CutState>[]; future: Record<string, Decision | CutState>[];
  revision: number; analyzed: boolean; media_path: string;
  summary: { removed_seconds: number; final_seconds: number };
};
export type ProjectInfo = { id: string; name: string; revision: number };
export type Job = { id: string; project_id: string; kind: string; status: 'queued' | 'running' | 'completed' | 'failed'; error: string | null };
export type ReviewAction = 'accept' | 'reject' | 'restore' | 'accept_all' | 'reject_all' | 'undo' | 'redo' | 'adjust';

export function ticksPerSecond(rate: string): number {
  const [n, d = '1'] = rate.split('/');
  return Number(n) / Number(d);
}
export function time(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${(seconds % 60).toFixed(3).padStart(6, '0')}`;
}
export function visibleCuts(cuts: Cut[]): Cut[] {
  return cuts.filter(c => c.current || c.decision !== 'pending' || c.adjusted).sort((a, b) => a.start - b.start || a.end - b.end);
}
