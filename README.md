# CutForge

A local rough-cut assistant for DaVinci Resolve. Import one WAV, MP3, MP4, or MOV recording; detect silence with FFmpeg; audition transitions; approve edits; export an editable FCPXML timeline referencing a persistent copy of your media.

**Implementation status:** audio/video pipelines and review UI are implemented with automated tests. The user has verified the updated mono WAV export through the website and DaVinci Resolve 21. Other media/channel workflows still need manual Resolve verification. See [validation results](docs/validation.md), [requirement checklist](docs/checklist.md), and [known limitations](docs/limitations.md).

## Install

Use Python **3.11–3.14** (3.14 tested), Node **22.12+** (26 tested), npm, and FFmpeg/ffprobe on PATH. A normal FFmpeg build needs WAV, MP3, H.264 and AAC decoding; sample generation additionally uses `libx264` and `libmp3lame`.

### macOS

Install Python, Node and FFmpeg using your preferred installer; with Homebrew:

```sh
brew install python@3.14 node ffmpeg
python3.14 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
ffmpeg -version
ffprobe -version
```

### Windows (PowerShell)

Install Python from python.org, Node LTS from nodejs.org, and an FFmpeg Windows build linked from [ffmpeg.org/download.html](https://ffmpeg.org/download.html). Add the folder containing `ffmpeg.exe` and `ffprobe.exe` to PATH and reopen PowerShell. If using winget, `winget install Gyan.FFmpeg` is another option.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
npm --prefix frontend ci
ffmpeg -version
ffprobe -version
```

Activation is optional; the instructions use the virtual environment's Python directly. `backend/requirements.lock.txt` records the exact tested Python environment; `requirements.txt` provides portable version ranges. The frontend lockfile pins its dependencies.

## Run both servers with one command

From the repository root:

```sh
python3 scripts/dev.py
```

Windows: `py scripts/dev.py`.

Open **http://127.0.0.1:5173**. The backend binds to **127.0.0.1:8000**. Use that exact frontend address; other browser origins are blocked. The launcher checks dependencies and occupied ports. It does not start publicly accessible services.

Press **Ctrl+C once** in the launcher terminal to stop both servers. Active jobs finish before shutdown, so a large recording may take time. Forced termination preserves imported bytes and previous saved decisions; interrupted jobs are reported as failed at the next startup. Do not close the terminal during an upload if you want the complete file copied.

## Use

1. Import a recording. CutForge copies it before decoding/probing; the original is untouched. Import is asynchronous after the upload completes.
2. Check duration, codecs, sample rate/channels, and video metadata. Unsupported cases report an error; VFR is rejected after full timestamp inspection.
3. Start with the defaults: **−35 dBFS**, **0.7 s minimum silence**, **0.15 s speech padding**. Adjust to the recording and rerun as needed.
4. Select a cut in the table or colored source timeline. Use the seek slider to scrub. **Play original** includes the silence. **Preview edit** plays up to three seconds around the cut. **Preview rough cut** plays the entire recording while skipping all accepted removals, merging overlaps.
5. **Accept** means remove; **reject** or **pending** means keep. Adjust a selected cut with the exact start/end frame or sample fields; the seconds readout shows the corresponding source time. End boundaries are exclusive. Save boundaries preserves its decision. Decisions and adjustments save automatically and support Undo/Redo. Restore all suggestions returns decisions to pending while keeping manual boundaries. Earlier decisions and adjustments survive reanalysis.
6. Export FCPXML. Empty timelines are blocked with an explanation. Import using [these Resolve instructions](docs/resolve.md).

Opening a saved project restores decisions and undo history. Browser local storage only remembers the last project/job ID; the authoritative data is in local JSON files.

Schema 1 projects from the initial implementation remain readable and upgrade to schema 2 on their next save. Schema 2 includes boundary-aware undo history; older CutForge versions cannot open it.

## Workspace and backups

Default layout:

```text
workspace/
  jobs.json
  <project-id>/
    source.wav           # or .mp3, .mp4, .mov: canonical imported copy
    project.json         # metadata, suggestions, decisions, history
```

**Never rename, modify, move, or delete `source.ext` while a project or exported timeline uses it.** Closing/restarting CutForge never removes it. Failed and partial imports are retained too; remove unwanted project folders manually only when no timeline references them. CutForge provides no automatic deletion.

Back up the entire workspace, not just the downloaded JSON. JSON download is an inspection/backup aid, not a portable media package or a file you can upload through the UI. The `CUTFORGE_WORKSPACE` environment variable selects another directory **before startup**. Existing exports contain absolute percent-encoded `file:` URLs; moving the workspace requires re-exporting from its new location or relinking in Resolve. A missing/size-changed copy produces a useful error. Filenames with spaces, Unicode, and special characters are handled; imported disk filenames are generated safely and the original display name is retained.

The default import limit is 20 GiB; set `CUTFORGE_MAX_UPLOAD_BYTES` before startup to change it. HTTP upload handling may spool to OS temporary storage before the persistent copy is written, so allow temporary disk space as well as workspace space. Those temporary files are never referenced by exports.

## Tests and synthetic media

```sh
.venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
.venv/bin/python scripts/generate_samples.py
```

Windows: replace `.venv/bin/python` with `.\.venv\Scripts\python.exe`.

Add `--projects` to generate persistent demo projects and FCPXML examples. The script creates its own synthetic tones and test-pattern video; no external media downloads are needed. Production build output is `frontend/dist/`; the one-command launcher uses Vite development mode with its local API proxy. A packaged deployment is out of scope.

## Repository

```text
backend/
  cutforge/
    api.py                 # endpoints, local-origin/revision checks
    media.py               # import inspection and frame scan
    analysis.py            # FFmpeg silence analysis
    engine.py              # independent integer interval algebra
    models.py              # validated project/request schemas
    review.py              # decisions, reanalysis merge, undo/redo
    store.py               # atomic JSON persistence and safe paths
    jobs.py                # background jobs and restart status
    export.py              # FCPXML serialization and validation
    schemas/FCPXMLv1_7.dtd  # Apple's schema, bundled for offline use
  tests/
  requirements.txt
  requirements.lock.txt
frontend/
  src/                     # React UI, preview logic, Vitest tests
  package.json
  package-lock.json
  vite.config.ts
scripts/
  dev.py
  generate_samples.py
docs/
  architecture.md
  checklist.md
  limitations.md
  resolve.md
  validation.md
```

API documentation is available locally at `http://127.0.0.1:8000/docs`. Main endpoints: `POST /api/import`, `GET /api/jobs/{id}`, `GET /api/projects`, `GET /api/projects/{id}`, `/metadata`, `/media`, `/project.json`, `POST /analysis`, `POST /review`, and `GET /export?revision=N` under a project URL.

Read [architecture.md](docs/architecture.md) for the timing model, module boundaries, concurrency rules, and design trade-offs.
