# Resolve frame-aligned export

## Evidence and scope

The user tested two ten-clip mono timelines in Resolve 21. Sample-accurate A was contiguous in XML but appeared overlapping on two alternating tracks after import. Frame-aligned B imported onto one track with online media and waveforms. A direct WAV import also used one track. This supports an importer sensitivity to subframe boundaries; its internal rounding algorithm is not established. Following the full 265-clip production export, the user confirmed successful verification of the updated exporter through the website and Resolve 21. This confirmation covers the tested mono WAV workflow, not every supported media format.

The implementation reproduces B's timing exactly. It keeps the existing FCPXML 1.7 asset-clip structure, persistent media URL, BWF source origin, mono/stereo channel mapping and roles. No new lane assignments, retiming, rendered media or audio processing are used.

The [Apple FCPXML 1.7 DTD](https://developer.apple.com/library/archive/documentation/Miscellaneous/Conceptual/LegacyDTDsFinalCutPro/FCPXMLDTDv1.7/FCPXMLDTDv1.7.html) describes duration, offsets, nested audio and time mapping but provides no guarantee that a different representation preserves subframe edits on one Resolve track. Moving offsets alone would introduce gaps/overlaps when original durations are not frame multiples. Retiming would change playback speed. No sample-preserving alternative has been verified in Resolve; untested structural changes are not included in this fix.

## Timing rule

Saved cuts and the pure edit engine remain in original integer samples/frames. Alignment happens only in the exporter:

1. Generate the ordered retained clips from the union of approved removals.
2. Obtain the actual sequence frame rate from the same function that declares its FCPXML format: 25 fps for audio-only, exact source frame rate for video.
3. Round each **cumulative** timeline boundary to its nearest frame using integer arithmetic; exact half-frame ties go later. Do not round independent clip durations and accumulate their error.
4. For clip `i`, let `delta_i = aligned_offset_i - original_offset_i`. Add `delta_i` to its source IN; add the next boundary delta to its source OUT. Set its duration to the difference between consecutive aligned boundaries.
5. Keep the BWF source origin separate: add it to asset/source starts only, never to timeline offsets or durations.

Both source edges adjacent to a removed interval move by the same delta, preserving the removal's length while changing its position. Chronological source ranges do not overlap, so no samples are played twice. The timeline has no gaps; every clip plays at normal speed. Video edits are already on their sequence grid and remain unchanged, with shared video/audio boundaries.

## Audio trade-offs and edge cases

Frame alignment changes the intended selection of edge samples. It can exclude previously retained audio and include audio previously inside an approved cut. It does not rewrite or resample the source. There is no automatic silence insertion, fade, speed change, speech analysis or guarantee that a moved edge remains outside a spoken word. Review audible transitions, especially manually tightened cuts; existing silence padding helps but is not proof of safety.

For ordinary audio-only boundaries, maximum movement is half a sequence frame: 20 ms at 25 fps. A retained clip's duration can change by up to one frame because its two endpoints can move in opposite directions. The final duration is rounded once, so error does not accumulate across clips.

If rounding the final source OUT would exceed the recording, use the closest preceding available frame. This can shorten the total by less than one frame (40 ms at 25 fps). If a retained segment rounds to zero frames, including after that end correction, return an actionable HTTP 400; do not drop it, merge across an approved removal or silently expand the timeline to force it in. The user must explicitly adjust/reject a neighboring cut. Some short segments naturally round to one frame and change duration; these changes are included in the impact report.

Source ticks must fit exactly on the sequence frame grid. The current audio sequence rate supports common 44.1/48 kHz rates; video uses its own rational rate directly. An unusual audio sample-rate/sequence-rate combination with fractional samples per frame is explicitly rejected, rather than introducing fractional source samples. No new frame-rate setting is added.

CutForge's review preview and estimated duration still describe saved sample-accurate decisions. The exported result can differ. Each changed export includes a human-readable XML comment and local backend warning listing added/excluded source ticks, their rate, maximum edge movement and net duration change. Counts compare the entire source selections, including cases where a moved boundary crosses a very short removed interval. Do not interpret a small net duration change as a small total change in audio selection.

## Validation and tests

Every export is checked against the bundled FCPXML 1.7 DTD, canonical readable media, source metadata/origin, sequence frame rate, exact aligned clip ranges and total duration. The alignment adapter validates positive durations, source bounds and nonoverlapping ranges. Expected user-review failures return HTTP 400; unexpected failures retain diagnostic IDs and local traceback logging.

Regression tests cover the exact user-verified ten-clip timing values, mono/stereo BWF, 44.1/48 kHz, 24/25/30 fps adapter grids, 400 retained segments without cumulative drift, tiny removed intervals and whole-selection sample accounting, half-frame ties, subframe/zero-frame segments, physical source-end limits, fractional sample-grid rejection, and unchanged video boundaries at 25, 30000/1001 and 24000/1001 fps. Existing WAV/MP3/MP4/MOV, linked A/V, video-only, persistence, error and review tests remain part of the suite.

Latest backend run: `.venv/bin/python -m pytest -q` — **76 passed**, one existing Starlette/httpx deprecation warning. The initial run exposed three old assertions requiring exact sample selection; these now assert the documented one-sample alignment addition rather than silently dropping the integrity check.

## Full-project verification and repeatable checks

The user confirmed successful website/Resolve 21 verification before the commit review. The following checklist records the intended checks for repeating this workflow on future changes; it is not a separate automated playback result.

Import the new verification XML into a **fresh local Resolve 21 project** using File → Import → Timeline, with automatic source import, 25 fps and 48 kHz. Keep the workspace source at its existing path. Confirm:

- 265 clips total on one populated mono track, all online with waveforms.
- Duration **969.56 seconds**, versus the original **969.573833333…** seconds (13.833333 ms shorter).
- No gaps, overlapping playback or repeated narration; correct source order and editable handles.
- Audible beginning/middle/end transitions preserve words; inspect the per-clip CSV wherever a source edge moved.

For this revision, maximum edge movement is 956 samples (19.916667 ms). The whole source selection adds 123,528 samples (2.5735 seconds) and excludes 124,192 samples (2.587333 seconds), distributed over 265 clips. All 265 clips are retained. These differences need listening review despite the small net duration change. The verification folder contains the new XML and exact before/after timing CSV; previous exports and all saved approvals remain untouched.

The ten-clip experiment and subsequent website/Resolve verification are user-reported human evidence. Automated checks and successful serialization alone do not establish playback compatibility. Stereo, MP3 and video regression tests validate XML/timing automatically; manual Resolve checks for those workflows remain pending.
