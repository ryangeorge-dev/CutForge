# Resolve import and compatibility

**Status: the user has confirmed successful verification of the updated mono WAV export through the website and DaVinci Resolve 21, following the ten-clip A/B experiment and the 265-clip production export. Other media/channel workflows remain pending manual verification. See [frame alignment and its audio trade-offs](export-alignment.md). DTD validation alone is not playback certification.**

## Interchange choice

CutForge emits the minimal FCPXML 1.7 structure: resources, one file asset, library/event/project/sequence, and sequential `asset-clip` elements. Version 1.7 has an official downloadable Apple DTD and supports the features used here without bundles or newer effect metadata.

Sources consulted before implementation:

- [Apple FCPXML 1.7 DTD](https://developer.apple.com/library/archive/documentation/Miscellaneous/Conceptual/LegacyDTDsFinalCutPro/FCPXMLDTDv1.7/FCPXMLDTDv1.7.html). The schema is vendored in `backend/cutforge/schemas/` with Apple's copyright notice. Apple explicitly says schema conformance does not guarantee successful import.
- [Blackmagic Resolve 18.6 new-features guide](https://documents.blackmagicdesign.com/es/SupportNotes/DaVinci_Resolve_18.6_New_Features_Guide.pdf) documents FCPXML import/export, including support for 1.11. This establishes format support, not verification of CutForge's 1.7 subset in every Resolve version.
- [Blackmagic Resolve reference manual](https://documents.blackmagicdesign.com/UserManuals/DaVinci_Resolve_11_Reference_Manual.pdf) documents importing Final Cut Pro XML timelines. The current installed Resolve 21.0.0 UI also exposes File → Import → Timeline and an FCPXML file filter.
- [FFmpeg silencedetect documentation](https://www.ffmpeg.org/ffmpeg-filters.html#silencedetect) defines the detector's thresholds and timestamps.

## Import steps

1. Leave CutForge's workspace media in place. Export FCPXML after reviewing cuts. Pending or rejected cuts are retained.
2. Open DaVinci Resolve and create a new local project for the first test.
3. Choose **File → Import → Timeline…**. On macOS the shortcut is **Shift+Command+I**; on Windows use the menu.
4. Select the downloaded `cutforge.fcpxml`. Choose the FCPXML filter if needed, then **Import**.
5. In the timeline import options, enable automatic source-clip import. Match the video's frame rate and use sizing information from the source/timeline. For audio-only exports, the sequence timebase is 25 fps; source audio remains at its original sample rate, but exported edit boundaries are frame-aligned and can differ from saved sample-accurate decisions.
6. Confirm the import. If media is offline, locate the project `source.ext` in CutForge's displayed persistent media location and relink it in the Media Pool.
7. Check source in/out ranges, overall duration, rejected silence retention, and A/V synchronization. Scrub and trim an imported clip to verify that it is editable source media.
8. Save the Resolve project. CutForge can be closed; references still point to the persistent workspace.

If the native file picker disables Import, do not assume the timeline was imported. Retry manually in your Resolve version and record any error. No fallback rendered video is substituted.

## Reproducible verification fixtures

Run `.venv/bin/python scripts/generate_samples.py --projects` (Windows: `.venv\Scripts\python`). This creates five-second recordings with silence at 0–1, 2–3, and 4–5 seconds, plus all-silent, continuous-tone, and video-only cases. Example projects accept the leading/trailing cuts and **reject the middle silence**, leaving it audible/visible in the exported timeline. Files are in `samples/exports/`; their media references point into persistent `workspace/`, not `samples/`.

For split-clip verification, open a generated project in CutForge, restore suggestions, accept the middle cut only, and export. Expect two editable clips whose source ranges exclude the middle silence, separated by a contiguous timeline edit.

Manual matrix:

| Fixture | Inspect in Resolve | Status |
|---|---|---|
| WAV 48 kHz mono with BWF origin | Website export and Resolve 21 import after frame alignment | User-confirmed |
| WAV 44.1 kHz mono | Exact in/out timing, source reference, no video source | Pending |
| WAV 48 kHz stereo | Both channels and rejected middle silence retained | Pending |
| MP3 | Decoder delay, in/out alignment and duration | Pending |
| MP4 25 fps + AAC | Linked A/V, frame-aligned in/out, editable trims | Pending |
| MOV 30000/1001 + AAC | Rational timebase and A/V sync across edits | Pending |
| Video-only MP4 | Video clips, no artificial audio tracks | Pending |
| 5.1-channel recording | Source channel order and Resolve routing | Pending |

## Limits

No effects, transitions, fades, color-management transforms, or complex track routing are serialized. Broadcast Wave source time references are preserved at export; nonzero video timecode is still rejected on import. Hard cuts can click; padding reduces aggressive speech cuts but is not a crossfade. Audio-only exports shift source edges to make the timeline frame-aligned; saved decisions and CutForge playback/estimates remain sample-accurate. Export blocks a segment that collapses to zero frames instead of silently discarding it. See the alignment report in the XML comment/backend log and the [documented limits](export-alignment.md). Multichannel source counts are preserved; confirm channel routing manually. HDR sources are flagged for manual color management. Moving media or exporting to another computer requires relinking.
