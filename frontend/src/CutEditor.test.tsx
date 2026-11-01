import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { CutEditor } from './CutEditor';
import { SourceTimeline } from './SourceTimeline';
import type { Metadata } from './types';

const cut = { id: '30:60', start: 30, end: 60, current: true, decision: 'accepted' as const };
const metadata: Metadata = { rate: '30000/1001', duration_ticks: 300, has_video: true, has_audio: false, video_codec: 'h264', audio_codec: null, width: 640, height: 360, sample_rate: null, channels: null, channel_layout: null, warnings: [] };

it('submits exact frame boundaries and blocks empty/reversed ranges', async () => {
  const save = vi.fn(); const user = userEvent.setup();
  render(<CutEditor cut={cut} metadata={metadata} busy={false} save={save}/>);
  expect(screen.getByText('Save boundaries')).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Start frame'), { target: { value: '31' } });
  await user.click(screen.getByText('Save boundaries'));
  expect(save).toHaveBeenCalledWith(31, 60);
  fireEvent.change(screen.getByLabelText('End frame'), { target: { value: '31' } });
  expect(screen.getByText('Save boundaries')).toBeDisabled();
  expect(screen.getByRole('alert')).toHaveTextContent('Start must precede end');
});

it('selects cuts and seeks using the interactive timeline', async () => {
  const select = vi.fn(); const seek = vi.fn(); const user = userEvent.setup();
  render(<SourceTimeline cuts={[cut]} duration={10} rate={30} position={0} select={select} seek={seek} ready/>);
  await user.click(screen.getByLabelText('Timeline cut 1: accepted'));
  expect(select).toHaveBeenCalledWith(cut);
  fireEvent.change(screen.getByLabelText('Seek source timeline'), { target: { value: '4' } });
  expect(seek).toHaveBeenCalledWith(4);
});
