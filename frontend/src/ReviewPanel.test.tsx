import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { ReviewPanel } from './ReviewPanel';
import type { Project } from './types';

export const fixture: Project = {
  id: 'test', name: 'Narration.wav', revision: 1, analyzed: true, media_path: '/workspace/test/source.wav',
  metadata: { duration_ticks: 480000, rate: '48000', has_video: false, has_audio: true, video_codec: null, audio_codec: 'pcm_s16le', width: null, height: null, sample_rate: 48000, channels: 1, channel_layout: 'mono', warnings: [] },
  settings: { threshold_db: -35, min_silence: .7, padding: .15 },
  cuts: [{ id: '48000:96000', start: 48000, end: 96000, current: true, decision: 'pending' }],
  history: [], future: [], summary: { removed_seconds: 0, final_seconds: 10 },
};

it('sends explicit decisions and restore actions without hiding rejected cuts', async () => {
  const decide = vi.fn(); const select = vi.fn(); const user = userEvent.setup();
  const { rerender } = render(<ReviewPanel project={fixture} busy={false} select={select} decide={decide}/>);
  await user.click(screen.getByLabelText('Select cut 1'));
  expect(select).toHaveBeenCalledWith(fixture.cuts[0]);
  await user.click(screen.getByLabelText('Accept cut 1'));
  expect(decide).toHaveBeenLastCalledWith('accept', '48000:96000');
  await user.click(screen.getByLabelText('Reject cut 1'));
  expect(decide).toHaveBeenLastCalledWith('reject', '48000:96000');
  rerender(<ReviewPanel project={{ ...fixture, cuts: [{ ...fixture.cuts[0], decision: 'rejected', current: false }] }} busy={false} select={select} decide={decide}/>);
  expect(screen.getByText('Earlier analysis')).toBeInTheDocument();
  expect(screen.getByText('rejected')).toBeInTheDocument();
  await user.click(screen.getByText('Restore all suggestions'));
  expect(decide).toHaveBeenLastCalledWith('restore');
});

it('enables undo and redo only when server history permits', async () => {
  const decide = vi.fn(); const user = userEvent.setup();
  const { rerender } = render(<ReviewPanel project={fixture} busy={false} select={vi.fn()} decide={decide}/>);
  expect(screen.getByText('Undo')).toBeDisabled(); expect(screen.getByText('Redo')).toBeDisabled();
  rerender(<ReviewPanel project={{ ...fixture, history: [{}], future: [{}] }} busy={false} select={vi.fn()} decide={decide}/>);
  await user.click(screen.getByText('Undo')); expect(decide).toHaveBeenLastCalledWith('undo');
  await user.click(screen.getByText('Redo')); expect(decide).toHaveBeenLastCalledWith('redo');
  rerender(<ReviewPanel project={{ ...fixture, history: [{}], future: [{}] }} busy={true} select={vi.fn()} decide={decide}/>);
  expect(screen.getByText('Undo')).toBeDisabled(); expect(screen.getByLabelText('Accept cut 1')).toBeDisabled();
});
