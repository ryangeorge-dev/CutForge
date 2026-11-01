import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import type { Project } from './types';

const initial: Project = {
  id: 'test', name: 'Narration.wav', revision: 1, analyzed: true, media_path: '/workspace/test/source.wav',
  metadata: { duration_ticks: 480000, rate: '48000', has_video: false, has_audio: true, video_codec: null, audio_codec: 'pcm_s16le', width: null, height: null, sample_rate: 48000, channels: 1, channel_layout: 'mono', warnings: [] },
  settings: { threshold_db: -35, min_silence: .7, padding: .15 },
  cuts: [{ id: '48000:96000', start: 48000, end: 96000, current: true, decision: 'pending' }],
  history: [], future: [], summary: { removed_seconds: 0, final_seconds: 10 },
};

beforeEach(() => {
  localStorage.clear(); localStorage.setItem('cutforge-project', 'test');
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {});
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue();
});

it('persists accept, undo and redo through revisioned requests and renders server truth', async () => {
  let state = structuredClone(initial);
  const calls: { action: string; revision: number }[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
    if (url === '/api/projects') return Response.json([{ id: 'test', name: state.name }]);
    if (url.endsWith('/review')) {
      const body = JSON.parse(options!.body as string); calls.push(body);
      if (body.action === 'accept' || body.action === 'redo') {
        state.cuts[0].decision = 'accepted'; state.history = [{}]; state.future = [];
        state.summary = { removed_seconds: 1, final_seconds: 9 };
      } else {
        state.cuts[0].decision = 'pending'; state.history = []; state.future = [{}];
        state.summary = { removed_seconds: 0, final_seconds: 10 };
      }
      state.revision++;
    }
    return Response.json(state);
  }));
  const user = userEvent.setup(); render(<App/>);
  await user.click(await screen.findByLabelText('Accept cut 1'));
  expect(await screen.findByText('accepted')).toBeInTheDocument();
  expect(screen.getByText('0:09.000')).toBeInTheDocument();
  await user.click(screen.getByText('Undo'));
  expect(await screen.findByText('pending')).toBeInTheDocument();
  await user.click(screen.getByText('Redo'));
  expect(await screen.findByText('accepted')).toBeInTheDocument();
  expect(calls.map(c => [c.action, c.revision])).toEqual([['accept', 1], ['undo', 2], ['redo', 3]]);
});

it('keeps decisions unchanged on save failure and reports a browser codec failure', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url === '/api/projects') return Response.json([{ id: 'test', name: initial.name }]);
    if (url.endsWith('/review')) return Response.json({ detail: 'Project changed in another tab.' }, { status: 409 });
    return Response.json(initial);
  }));
  const user = userEvent.setup(); const { container } = render(<App/>);
  await user.click(await screen.findByLabelText('Accept cut 1'));
  expect(await screen.findByText('Project changed in another tab.')).toBeInTheDocument();
  expect(screen.getByText('pending')).toBeInTheDocument();
  fireEvent.error(container.querySelector('audio')!);
  expect(screen.getByText(/This browser cannot preview/)).toBeInTheDocument();
});

it('compares original playback with an edited transition', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => Response.json(url === '/api/projects' ? [{ id: 'test', name: initial.name }] : initial)));
  const user = userEvent.setup(); const { container } = render(<App/>);
  await user.click(await screen.findByLabelText('Select cut 1'));
  const audio = container.querySelector('audio')!;
  fireEvent.loadedMetadata(audio);
  await user.click(screen.getByText('Play original'));
  expect(audio.currentTime).toBe(0);
  expect(screen.getByText('Original section · no cut')).toBeInTheDocument();
  await user.click(screen.getByText('Preview edit'));
  expect(screen.getByText('Edited transition · skipping selected cut')).toBeInTheDocument();
  expect(audio.play).toHaveBeenCalledTimes(2);
  await user.click(screen.getByText('Stop preview'));
  await waitFor(() => expect(screen.getByText('Full source playback')).toBeInTheDocument());
});

it('skips approved ranges on media time updates even when animation frames are throttled', async () => {
  const state = structuredClone(initial);
  state.cuts[0].decision = 'accepted';
  state.summary = { removed_seconds: 1, final_seconds: 9 };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => Response.json(url === '/api/projects' ? [{ id: 'test', name: state.name }] : state)));
  const user = userEvent.setup(); const { container } = render(<App/>);
  await screen.findByLabelText('Accept cut 1');
  const audio = container.querySelector('audio')!;
  fireEvent.loadedMetadata(audio);
  Object.defineProperty(audio, 'paused', { value: false, configurable: true });
  await user.click(screen.getByText('Preview rough cut'));
  audio.currentTime = 1.2;
  fireEvent.timeUpdate(audio);
  expect(audio.currentTime).toBe(2);
  fireEvent.change(screen.getByLabelText('Seek source timeline'), { target: { value: '1.3' } });
  fireEvent.timeUpdate(audio);
  expect(audio.currentTime).toBe(1.3); // scrubbing deliberately returns to original playback
});
