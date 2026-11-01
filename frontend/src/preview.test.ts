import { describe, expect, it } from 'vitest';
import { mergeRanges, previewStep, previewWindow, roughCutStep } from './preview';

describe('transition preview', () => {
  it('plays context and skips only in edited mode', () => {
    const plan = previewWindow(10, 12, 30, true);
    expect(plan.start).toBe(7); expect(plan.end).toBe(15);
    expect(previewStep(9.9, plan)).toEqual({});
    expect(previewStep(10.01, plan)).toEqual({ seek: 12 });
    expect(previewStep(12, plan)).toEqual({});
    expect(previewStep(15, plan)).toEqual({ stop: true });
    expect(previewStep(11, { ...plan, edited: false })).toEqual({});
  });
  it('handles leading, trailing and whole-source cuts', () => {
    expect(previewWindow(0, 2, 10, true).start).toBe(0);
    expect(previewStep(0, previewWindow(0, 2, 10, true))).toEqual({ seek: 2 });
    expect(previewStep(8, previewWindow(8, 10, 10, true))).toEqual({ stop: true });
    expect(previewStep(0, previewWindow(0, 10, 10, true))).toEqual({ stop: true });
  });
});

it('previews the merged rough cut across leading, overlapping and trailing removals', () => {
  const cuts = mergeRanges([{ start: 8, end: 10 }, { start: 4, end: 6 }, { start: 0, end: 2 }, { start: 3, end: 5 }, { start: 6, end: 6 }]);
  expect(cuts).toEqual([{ start: 0, end: 2 }, { start: 3, end: 6 }, { start: 8, end: 10 }]);
  expect(roughCutStep(0, cuts, 10)).toEqual({ seek: 2 });
  expect(roughCutStep(2.5, cuts, 10)).toEqual({});
  expect(roughCutStep(4.9, cuts, 10)).toEqual({ seek: 6 });
  expect(roughCutStep(8, cuts, 10)).toEqual({ stop: true });
  expect(roughCutStep(4, [], 10)).toEqual({});
});
