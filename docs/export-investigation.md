# Resolve 21 export investigation

This records the earlier offline-media investigation. The user subsequently confirmed online playback with the BWF correction, one-track import of frame-aligned diagnostic B, and successful verification of the updated exporter through the website and Resolve 21. See [the current alignment implementation and verification scope](export-alignment.md); the pending statements below describe the earlier investigation stage.

## Findings and confidence

The inspected saved project and downloaded FCPXML contain **265 retained clips**, not the originally reported 131. In the current Resolve window, A1 shows 132 clips and A2 shows 133: their sum is 265. This is a distribution across tracks, not evidence that every clip was duplicated. The exact earlier 131-clip export was not located.

Confirmed for the inspected export:

- Exactly one source asset, `r2`; every timeline `asset-clip` references it.
- The absolute `file:///` URL round-trips to the existing, readable canonical workspace WAV. It does not point to an upload, temporary directory, or original recording outside the workspace. No missing-file or incorrect-reference explanation was found.
- The source is 24-bit PCM, mono, 48 kHz. Its Broadcast Wave `time_reference` is **175164288 samples**, or **3649.256 seconds**. The previous export declared asset start zero and used zero-relative clip starts, omitting that source origin.
- The old sequence declared stereo despite a one-channel asset, with no explicit channel component mapping.
- XML offsets are contiguous and retained ranges are ordered. The total is **969.573833333… seconds** (`5817443/6000s`). All but the first of its 265 offsets fall between the audio sequence's 25 fps frame boundaries.

**Likely offline cause:** Resolve uses the WAV's Broadcast Wave origin when conforming source ranges; the old zero-relative ranges precede that origin. The origin omission is confirmed, but its causal connection to offline clips requires a corrected import. A valid path and a playable Media Pool asset alone do not prove that timeline source ranges conform.

**Two-track cause remains unconfirmed:** the stereo declaration was wrong and is corrected. Resolve may also distribute sample-aligned edits across tracks when interpreting them on its frame grid. We deliberately preserve approved sample boundaries instead of rounding them speculatively. Check the imported clip count, ordering and track distribution separately from channel count.

The earlier transient HTTP 500 was not reproduced by repeated direct exports or temporary-workspace API tests. There was no historical traceback establishing its cause. Restarting successfully is not evidence of a particular underlying failure.

## Changes

- Read WAV source timing using a bounded ffprobe metadata query at export, including for existing saved projects. No project schema migration or rewriting of project data is needed.
- Add the exact rational source origin to the asset and each clip's source start. Timeline offsets, retained durations and approved decisions stay zero-relative and unchanged.
- Declare mono/stereo/surround according to source channel count and emit one audio component with the corresponding source channels. Stereo is a single `srcCh="1, 2"` component, not two mono components. Video/audio remain in the same asset-clip with shared boundaries; video-only media gets no audio component.
- Extend validation of the existing FCPXML 1.7 DTD, readable canonical media, source origin/duration, asset references, channel declarations, exact ordered clip ranges and total duration.
- Unexpected export/probe/validation failures return HTTP 500 with a diagnostic ID, not a downloadable partial XML. The local backend log includes that ID, project revision and traceback. Empty timelines and missing/changed media remain actionable HTTP 400 errors. Treat backend logs as local/private because diagnostics can contain source paths.

No source recordings or project JSON need to be edited. Export does not rewrite media. No format version upgrade or separate audio/video timeline was introduced.

## Reference comparison

- [Apple's FCPXML 1.7 DTD](https://developer.apple.com/library/archive/documentation/Miscellaneous/Conceptual/LegacyDTDsFinalCutPro/FCPXMLDTDv1.7/FCPXMLDTDv1.7.html) defines the asset, asset-clip and audio-channel-source structures and mono/stereo/surround sequence layouts. The vendored DTD is checked on every export. Schema validity alone does not establish playback compatibility.
- [BWF MetaEdit's BEXT documentation](https://mediaarea.net/BWFMetaEdit/bext) reproduces the EBU definition of TimeReference as the first sample's count since midnight, in source sample-rate units.
- [FCP Cafe's FCPXML examples](https://fcp.cafe/developers/fcpxml/) distinguish source asset/clip time from timeline offset. They support the source-clock interpretation but are not a known-good Resolve mono fixture.

No independently verified Resolve-exported mono reference was available. The current Resolve project was visibly marked Edited and was left untouched; corrected imports were not performed in it. Obtain a Resolve-exported minimal mono timeline if the corrected import still fails, to compare its source origin, channel routing and subframe timing directly.

## Automated verification

Run from the repository root:

```sh
.venv/bin/python -m pytest -q
```

59 tests passed during this repair. One existing Starlette/httpx deprecation warning remains; no dependencies were changed. Added regressions cover real 48 kHz mono BWF, 44.1 kHz stereo BWF with a non-frame-aligned origin, zero-origin WAV, Unicode/space/ampersand/percent/hash/quote paths, XML escaping, duplicate/overlapping/adjacent approvals, retained-sample order, duration, invalid exports, and useful sanitized export failures followed by successful retries. Existing MP4/MOV with audio and video-only tests also pass, including linked boundaries and rational frame times. All test workspaces use temporary directories.

These are automated interchange checks, not Resolve playback certification. Frontend code was unchanged.

## Manual acceptance checklist — Resolve 21

1. Preserve the current Resolve project. Create a **new local test project** so existing Media Pool conform metadata cannot influence the result. Do not overwrite the old imported timeline.
2. With the updated backend running, open the existing CutForge project and export again **without rerunning detection or changing approvals**. Keep the workspace media in its original location. Restart CutForge normally first if its backend is still running the old code.
3. Choose **File → Import → Timeline…** (`Shift+Command+I` on macOS), select the newly exported `.fcpxml`, and enable **Automatically import source clips into media pool**. For this WAV use the XML's 25 fps timeline and 48 kHz audio. Confirm import.
4. Verify both the Media Pool source and timeline clips are online and playable. Check Clip Attributes for **one mono source channel**, not duplicated stereo channels. There should be one logical mono sequence; record any distribution across A1/A2 rather than assuming duplication. If separate tracks persist, this criterion remains open even if media is online.
5. For the inspected revision 20 snapshot, expect **265 retained clips total** and **969.573833… seconds** (about `00:16:09:14` at 25 fps). If decisions have since changed, use the new CutForge estimate instead. Record any difference larger than a single timeline frame; do not ignore accumulating per-cut drift.
6. Listen across several beginning, middle and ending edits. Confirm no gaps, repeats or lost speech; approved removals disappear and rejected/pending intervals remain. Trim a clip edge to verify source handles are editable. Compare against CutForge's rough-cut preview. Check that the imported source start reflects its BWF origin (about `01:00:49`, with a subframe remainder).
7. Repeat with a plain mono WAV, stereo WAV and MP4/MOV with embedded audio. Verify stereo channel identity, one linked video/audio edit per retained range, correct frame rate/duration, and lip-sync before and after cuts. Video-only import should have no populated audio track.
8. If offline clips remain, record the first clip's source in/out, Media Pool start timecode, track counts and any import warning. Verify the canonical workspace path and permissions; relinking alone does not fix a source-time mismatch. Export a tiny **known-online** mono timeline from Resolve as FCPXML for comparison. Do not alter the WAV's BWF header or saved CutForge cuts as a workaround.

**Completion remains pending:** a human must confirm online playback, intended track structure, duration, ordered cuts and A/V synchronization in Resolve 21.
