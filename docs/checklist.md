# MVP requirement checklist

`[x]` implemented with relevant automated coverage; `[ ]` incomplete or manual verification pending. Details and actual runs are in [validation.md](validation.md).

## Phase 1: audio

- [x] Browser WAV/MP3 selection and persistent canonical source copy
- [x] ffprobe metadata and full audio decode/sample counting
- [x] WAV 44.1/48 kHz, MP3, mono/stereo and identified 5.1 handling
- [x] Real FFmpeg `silencedetect`, configurable threshold/minimum/padding
- [x] Leading, middle, trailing, no-silence and all-silence behavior
- [x] Pure normalization, clamping, merging, complementary keep intervals
- [x] Integer sample timing and rational FCPXML serialization
- [x] Audio-only FCPXML with DTD/source-range validation
- [x] Reject malformed/unsupported media with useful errors
- [ ] Actual Resolve audio import and subframe timing verification

## Phase 2: video

- [x] MP4/MOV metadata, resolution, codec and exact rational frame rate
- [x] Decode full timestamp sequence and reject VFR/discontinuities
- [x] Frame-aligned cuts and one shared embedded A/V asset per clip
- [x] Video-only analysis yields no suggestions; export has no fake audio
- [x] Reject unsupported stream counts, timing offsets, layouts, timecodes and rotation
- [x] Exact 30000/1001 timing tested; stable media URLs tested
- [ ] Actual Resolve MP4/MOV import and audible/visible sync verification
- [ ] Actual Resolve video-only and multichannel routing verification

## Phase 3: review

- [x] Native audio/video preview with explicit codec-failure message
- [x] Candidate start/end/duration and decision controls
- [x] Original-versus-edited transition preview with three-second context
- [x] Full rough-cut preview skips all accepted removals, merging overlaps
- [x] Interactive source timeline with cut selection, playhead and seek slider
- [x] Adjust source boundaries by frames/samples; validate, persist and undo/redo adjustments
- [x] Read existing schema 1 projects/history and upgrade on save
- [x] Parameter changes and background reanalysis
- [x] Approved removal and final duration from backend interval union
- [x] Accept/reject, accept/reject all, restore suggestions
- [x] Undo/Redo persisted in project JSON
- [x] Reanalysis preserves prior decisions and marks older ranges
- [x] Revision conflicts do not overwrite saved decisions
- [x] Project reopening, export download, JSON download, errors and job state
- [ ] Listening-based narration quality and broad cross-browser preview validation

## Local service and delivery

- [x] FastAPI import, metadata, analysis, jobs, decisions, persistence and export routes
- [x] Long processing in bounded workers; restart marks interrupted jobs failed
- [x] Loopback-only launcher; exact frontend CORS and Origin checks; Host checks
- [x] ID-based path confinement; generated safe filenames; no arbitrary-path endpoint
- [x] FFmpeg protocol/container allowlists; no shell interpolation
- [x] Persistent original copy retained, including failed imports; movement/relinking documented
- [x] One-command startup with dependency/port checks and shutdown handling
- [x] Source, README, architecture, tests, sample generator, limitations and Resolve instructions
- [x] Backend tests, frontend tests and production build executed
- [ ] Windows installation/start/stop test on a real Windows machine
- [ ] All acceptance criteria signed off in Resolve; MVP compatibility acceptance remains open
