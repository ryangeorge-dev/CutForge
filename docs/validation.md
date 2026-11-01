# Validation record

Last updated: **2026-11-01**, America/Toronto.

## Scope and status

Audio/video processing, source-timestamp editing, the local API, review UI, interactive source timeline, manual boundary adjustments, and editable FCPXML generation are implemented. **The user confirmed the updated mono WAV export through the website and DaVinci Resolve 21.** Other media/channel workflows remain pending manual verification. No rendered video substitutes for timeline export.

The resumed implementation preserved the existing modules and projects. Baseline checks passed before changes: 28 backend tests, 7 frontend tests, and the production build. The additions extend the existing review commands and preview component.

## Automated checks

| Command | Actual result |
|---|---|
| `.venv/bin/python -m pytest -q` | **76 passed**, including export alignment, BWF origin, channel mapping, diagnostics and the WAV/MP3/MP4/MOV/video-only HTTP workflow matrix |
| `npm --prefix frontend test` | 11 passed across 4 files, Vitest 5.0.5 |
| `npm --prefix frontend run build` | TypeScript check and Vite 8.3.5 production build passed |
| `npm audit` / patched dependency install, initial implementation | 0 advisories after updating Vite/Vitest; not a continuing security guarantee |

Backend checks use generated media and real FFmpeg/ffprobe. Coverage includes normalization/merging, random partition invariants, zero-length/boundary cases, 44.1/48 kHz audio, MP3 sample counts, multichannel silence behavior, no/all silence, malformed media, MP4/MOV and video-only export, 30000/1001 timing, VFR/timecode rejection, DTD validation, approved-only edits, stable encoded file URLs, revision conflicts, persisted undo/redo, legacy history, boundary adjustment, missing media and project-ID confinement.

Frontend tests cover explicit accept/reject requests, server-confirmed state, failed saves, revisioned undo/redo, preview-mode comparison, codec errors, merged rough-cut skip rules, media-event fallback, exact boundary controls, and timeline selection/seeking. Browser media elements are simulated in Vitest; these tests do not establish audible smoothness or codec compatibility.

One upstream Starlette/httpx deprecation warning remains in Pytest. No failed assertions are hidden or marked expected-failure.

## Local smoke testing

- The one-command launcher started both servers on 127.0.0.1. Ctrl+C shut them down cleanly; a subsequent launch reopened saved projects.
- A final immediate restart exposed a false port-in-use result from Unix TIME_WAIT sockets. The preflight check now uses SO_REUSEADDR on Unix, matching the servers; the corrected launcher started both loopback listeners successfully.
- Safari imported a synthetic stereo WAV through the file chooser, displayed 5.000 s / 48 kHz metadata, and ran real silence analysis with three suggestions.
- Accept-all changed the displayed removal to 2.400 s and retained duration to 2.600 s. Undo restored 5.000 s; redo reapplied the decisions.
- Safari reopened the MP4 demo with H.264/AAC metadata and the rejected middle silence visible.
- Selecting an accepted region in the new source timeline exposed boundary controls. Changing its endpoint from frame 21 to frame 20 saved successfully: approved removal changed 1.680 → 1.640 s, retained duration 3.320 → 3.360 s.
- Original/edited/full-rough-cut playback controls were exercised. Animation throttling prompted a media-timeupdate fallback and regression test. Listening quality, hidden-tab timing, and broad browser coverage remain manual checks.
- After reloading the updated UI, full rough-cut playback stopped at approximately source 4.307 s inside the approved trailing removal starting at 4.160 s, rather than playing to source end at 5.000 s. This demonstrates the fallback working and also its approximate browser timing; it is not sample-accurate playback certification.
- The live MP4 review exported successfully: the backend returned HTTP 200 after validation and Safari completed the FCPXML download. Importing that download into Resolve is still pending.
- Synthetic files and persistent demo projects were created with `scripts/generate_samples.py --projects`. Source media was never modified by review/export.

## Resolve verification and outstanding checks

Following the earlier attempt below, the user performed the mono ten-clip A/B experiment and confirmed that frame alignment resolves the alternating-track behavior. After the production fix and 265-clip verification export, the user reported successful verification through the website and Resolve 21. This is user-reported manual evidence for the tested mono WAV workflow; it does not establish every format/channel combination or the importer's internal rounding behavior. See [export-alignment.md](export-alignment.md).

Earlier implementation attempt: Resolve **21.0.0** was installed. A separate **CutForge MVP Verification** project was created. Its native timeline-import picker listed the generated FCPXML but left Import disabled, including with the explicit FCPXML filter. No successful import was observed in that attempt. The external scripting API returned no connection. A subsequent native-app retry timed out on 2026-11-01. These earlier observations do not establish that the file format is accepted or rejected by Resolve's importer.

Pending: other audio formats/channel layouts, video/video-only imports, A/V sync over multiple cuts, 5.1 channel routing, and source relinking after moving a workspace. Repeat source-range, duration and editable-trimming checks for those workflows. Follow [resolve.md](resolve.md) and record the exact Resolve build and results. Windows installation and shutdown also require testing on Windows.

See [checklist.md](checklist.md) and [limitations.md](limitations.md) for the remaining acceptance items and deliberately unsupported media characteristics.
