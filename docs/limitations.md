# Known limitations

- **Resolve import is pending manual verification.** FCPXML is DTD-validated and its clip ranges are checked against approved cuts. This does not prove Resolve's media linking, sample-level audio interpretation, or channel routing.
- One file, one real video stream, and at most one audio stream per project. Attached cover art is ignored. Multiple audio tracks are rejected instead of silently dropping tracks.
- Constant-frame-rate progressive video only (up to 240 fps). Full decoded timestamps are checked. VFR/discontinuous timestamps, rotation metadata, nonzero source timecode, nonzero presentation start, materially different A/V lengths, and audio/video start offsets are rejected with an explanation. Convert/remux a separate copy before import.
- Mono, stereo, and identified 5.1 channel layouts are supported. Other/unknown multichannel layouts are rejected. Source channel count is serialized; Resolve routing needs manual verification. Silence detection requires all channels to be quiet and does not downmix.
- Browser preview is native playback, not a transcoded proxy. Supported FFmpeg/Resolve codecs may fail in a browser; the UI explains this. Preview may buffer during seeks and is not sample-perfect. Try a compatible browser or prepare a browser-compatible source copy.
- Silence detection cannot distinguish quiet speech, intentional pauses, or music. Review the suggestions. Hard cuts have no automatic fades or click suppression.
- Very short pauses can disappear after padding and inward quantization. A trailing video fraction without corresponding audio can remain retained; no artificial audio is generated.
- Entirely removed sources cannot be exported as an empty editable timeline. Restore a section first. No-silence and all-rejected projects export the full source.
- Audio-only exports use sample-precise source ranges inside a conventional 25 fps sequence format. Uncommon sample rates keep their source rate but use a 48 kHz sequence setting; inspect receiver resampling. No video asset is synthesized.
- HDR preview/color management is not normalized; configure Resolve manually. No source timecode translation, transitions, effects, or rendering.
- Import scans the complete source, which takes time. Two workers and four queued/running jobs limit simultaneous processing. Each subprocess times out after two hours. Job status is qualitative, without percentage progress or cancellation controls.
- Uploads have a configurable 20 GiB default limit and may temporarily use disk twice. Failed/partial imports remain on disk and require deliberate user cleanup.
- Use one backend process per workspace. Atomic writes protect individual project replacements; there is no cross-process coordination or database. Media size checking is not a content hash.
- Undo/redo stores decisions and adjusted boundaries in project JSON; it does not rewind settings or analysis runs. History grows with use. Older unadjusted pending candidates are retained internally for undo even if hidden from the current list.
- The interactive timeline shows cut regions and a seek slider, not a waveform or a multitrack editor. Boundary fields use integer frames/samples with a seconds readout. Overlapping regions may obscure one another visually; every cut remains accessible in the review table.
- Project JSON download is not a portable package or UI-importable project. Reopen existing projects through the local workspace list. Back up media together with JSON.
- macOS setup and Safari smoke testing were exercised here. Windows startup code and paths are provided but require manual Windows validation. Production build is tested; distribution as a packaged application is out of scope.
- Backend tests currently emit one upstream Starlette/httpx deprecation warning. It does not indicate a failing assertion.
