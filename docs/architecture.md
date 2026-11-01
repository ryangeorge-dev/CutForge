# CutForge architecture

The main flow is `upload → persistent copy → probe → project JSON → analysis → review → keep intervals → FCPXML`.

## Boundaries

| Module | Responsibility | Depends on |
|---|---|---|
| `media.py` | Inspect containers/streams, validate decoded audio and video timestamps | FFmpeg, ffprobe |
| `analysis.py` | Turn silence logs into padded, source-relative candidate intervals | FFmpeg, engine |
| `engine.py` | Clamp, sort, merge, complement and place retained ranges | Python standard library only |
| `review.py` | Explicit decisions, undo/redo, preservation across reanalysis | Project models |
| `store.py` | Atomic project writes and workspace path confinement | Local filesystem |
| `export.py` | Serialize retained ranges, validate DTD and decisions | Engine, lxml, vendored Apple DTD |
| `jobs.py` | Two workers, four active/queued jobs, persisted status | Thread pool, local JSON |
| `api.py` | Validate requests, revisions, origins and identifiers | All backend services |
| `frontend/src/` | Controls and browser playback; render server-confirmed review state | React, typed HTTP requests |

## Timing model

A project has an exact rational tick rate: frames/second for video, samples/second for audio. Every saved edit uses integer source ticks. FFmpeg timestamps are parsed as rational seconds and removal boundaries snap inward (ceil start, floor end). Padding is applied before quantization. The engine merges overlapping/adjacent removals, then produces their complement. The export's placement offset is the cumulative length of prior retained ranges.

Video/audio share a single `asset-clip` referencing the source's embedded streams. There is no separate rounding step for audio, hence no drift introduced by independent edit calculations. Audio-only source intervals use sample precision; their FCPXML sequence has a conventional 25 fps video format because the schema requires a sequence format. This creates no video source. Resolve's interpretation of subframe audio edits remains a manual verification item.

## Review invariants

- A suggestion starts `pending`. Only `accepted` cuts remove media. `rejected` and `pending` do not.
- Rerunning analysis marks older suggestions noncurrent and adds new ranges. Exact matches retain their existing decision.
- Noncurrent decisions remain visible and continue to apply. Hidden noncurrent pending suggestions remain stored so undo can recover them.
- Undo/redo snapshots decisions and manually adjusted boundaries; it does not rewind analysis settings. Restore sets all decisions to pending and is itself undoable; manual boundaries remain unless undone.
- Adjustments use exact source frames/samples and preserve the cut's decision and identity. Reanalysis never overwrites adjusted boundaries. Adjusted pending cuts remain visible even if no longer detected.
- Project schema 2 records boundary-aware history. Schema 1 projects and their decision-only history remain readable; the next save upgrades the project to schema 2. Older application versions cannot open schema 2 files.
- The backend is the source of truth. The UI does not optimistically claim a save succeeded.
- Revision checks reject stale review/export requests. One project's analysis excludes simultaneous review writes. Export cannot race an active analysis.

## Persistence and jobs

Each project directory contains `source.ext` and `project.json`. Imported bytes are copied without transcoding. Project JSON replacement is atomic and flushed before replacement. Job status is stored at the workspace root. On restart, interrupted jobs are marked failed; they are not silently restarted. Decisions from completed jobs survive browser/app restarts. Failed/partial imports are also retained; only the user removes files.

The media copy's size is checked before playback, analysis and export. This detects many accidental replacements, but is not a cryptographic integrity guarantee. Do not alter workspace sources. One backend process owns a workspace; file locking across multiple processes is not implemented.

## Deliberate trade-offs

Full video frame inspection costs decode time but catches timestamp irregularities beyond a short initial sample. It streams timestamps to a temporary scan file to bound RAM; that file is never an exported media source. Audio import counts decoded samples, handling MP3 encoder delay/padding. Processing timeouts are two hours per subprocess. The UI reports queued/running/completed/failed states, not an invented percentage.

Browser preview seeks the same media element across the selected removal, so video and audio stay together. Full rough-cut playback merges all accepted ranges before skipping them; rejected and pending cuts have no effect. An interactive source strip selects cuts and provides a seek slider. Animation callbacks give finer foreground timing; media time-update events provide a coarser fallback when animation callbacks are throttled. Seeking can buffer and is not gapless or sample accurate. It is a review aid; exported instructions come from the integer engine, not browser playback time.

There is no general XML import, project JSON upload, arbitrary-path endpoint, cloud processing, authentication, AI model, render pipeline, or database.
