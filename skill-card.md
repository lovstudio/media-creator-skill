# 天才剪辑师 · Video Studio · Skill Card

This human-readable card mirrors `skill-card.yaml`. It is a release record, not
an implementation note. A reviewer should understand the Skill without opening
its source.

## Description

`lov-media-creator` turns flat recordings or Screen Studio source projects into a review-first Remotion delivery. It separates draft, locked and approved work, reuses source-scoped proxies across small revisions, and runs local canaries before long jobs. It preserves independent tracks, verifies micro-cuts, keeps chapter/camera state coherent, and mounts the final BGM mix only after picture and dialogue lock.

For whole-course or multi-speaker recordings, it selects independently understandable excerpts using full-recording evidence, then runs precise cuts, caption review, continuous audio, reusable packaging and actual MP4 verification. This branch does not force series numbering or chapters. The bundled MLX transcription adapter requires Apple Silicon and local weights.

For travel and documentary vlogs, it inventories footage by device, reframes 360 dual-fisheye shots, keeps the score continuous under narration, scans the encoded file for privacy issues before the first platform release, and derives a second platform version from the same locked timeline.

## Owner

Media Creator Maintainers; contact through the repository issue tracker.

## License / Terms

MIT. Users may use, modify and distribute the Skill while retaining the license notice.

## Use Case

The Skill is for creators and product teams who need to turn a long recording into a short, understandable video: establish the problem, show credible operation evidence, and finish on the actual result. It also serves authors of travel and documentary films shot on several devices, including 360 cameras, who need a first-platform cut and further platform versions derived from the same timeline.

## Deployment Geography

Global, in a local Agent Skills environment on macOS, Linux or Windows.

## Requirements / Dependencies

- Python 3.8+ and PyYAML for structural validation.
- FFmpeg and FFprobe for inspection, rendering, frame extraction and audio QC.
- Node.js and Remotion for Screen Studio source projects, Studio previews and motion packaging.
- Optional Pillow, Playwright or an image tool when a new cover asset is requested.
- User-provided media and an isolated output directory.

## Known Risks and Mitigations

- The final result or its original audio can be lost. Mark protected segments in the EDL, then spot-check the rendered result and run audio QC.
- Waiting UI can dominate the cut. Keep only the state signal needed for comprehension.
- Unverified speed or publish claims can enter the title or report. Separate rendered, uploaded, published and read-back states.
- BGM can mask speech or feedback, and a second Studio-only stem mix can diverge from the approved master. Screen recordings and knowledge series use the agreed, authorized `Screen Studio Lo-fi / Bright Lounge`; programmatic synthesis is deprecated. Narrative films score from the user's whole library with several tracks and a written reason per cue. The score runs continuously and ducks under speech instead of stopping. Same-language lyrics stay out from under dialogue by default; they are released only when the author explicitly asks for that song under the dialogue or says not to stop the music for speech, with the reason and the author's words recorded on the cue and the released lines compared as a group against the voice-only CER floor. Each moment also gets a mix intent (clear, blend or feature), and intelligibility floors: cue validation, intent-aware speech-band SMR and a Whisper CER comparison with the voice-only floor. Apply ducking, fades and a linear master, then mount the same single final mix in Studio.
- Additive revision rounds can turn a narrative cut into a mosaic of short shots and frequent music changes, even when every local gate passes. Treat the scene as the unit, write a through-line of at most five sentences, co-design cut and score so music changes only at chapter or scene boundaries, keep the agent's own fixes subtractive (additions the author asks for are made and logged against the baseline), and measure fragmentation with `cut_metrics.py` against the previous cut.
- Resampling can make accelerated dialogue sound unnaturally high or low. Use pitch-preserving time-stretch, lock the result to the frame-derived sample count, and A/B it against the 1.0x source.
- ASR mistakes can be burned into a premature final export. Preview current subtitles in Remotion Studio; create a soft-subtitle MKV only for Subtitle Edit correction, and block platform delivery until the user approves the SRT.
- Generic or misplaced chapter labels can misrepresent the content or cut speech in half. Derive each title from segment evidence, insert chapter cards only at sentence/EDL boundaries, and recompute every downstream timestamp.
- Camera discontinuities and long explanatory overlays can hide the operation being taught. Keep the webcam continuous within a layout mode and return to the real screen as soon as interaction resumes.
- Studio and final rendering can expose `OffthreadVideo` as different media tags. Style the stable wrapper or both `video` and `img`, then inspect a contact sheet extracted from the encoded deliverable.
- Small subtitle, layout, BGM or cover changes can accidentally trigger a full five-track rebuild and render. Compare revision tokens with the iteration planner, reuse unaffected cache scopes, and run seam, visual or audio canaries before locked/final work.
- A first-platform release checked only at key frames can miss a QR code, licence plate, ID number or a person who should not appear; the problem may surface only when a second platform version is reviewed. Before the first release, scan the encoded file with detectors on every frame and a manual contact sheet at 5 fps or more, covering dissolve tails. For flaws found after publication, show the author the evidence and offer options by severity; the author decides, and any takedown or re-upload goes through the publishing Skill.
- 360 reframing can cross the dual-fisheye stitch seam, and a wider derived frame can reveal people, plates, the seam or the selfie stick outside the approved vertical window. Check the angular distance from all four window corners to the lens axis, not only the horizontal field of view, and review every shot's full used range on a contact sheet with the newly revealed area marked.

## References

- [Machine-readable card](skill-card.yaml)
- [Primary Skill instructions](SKILL.md)
- [Media workflow](references/media-workflow.md)
- [Delivery contract](references/delivery-contract.md)
- [Screen Studio and Remotion QC](references/screen-studio-remotion-qc.md)
- [Incremental iteration contract](references/iteration-performance.md)
- [Narrative vlog editing](references/narrative-vlog.md)
- [360 reframing](references/360-reframe.md)
- [Platform variants](references/platform-variants.md)
- [Review page](references/review-page.md)
- [Remotion pipeline pitfalls](references/remotion-pipeline-pitfalls.md)

## Skill Output

The primary preview is Remotion Studio with the current authoritative edit state. Every round also produces an incremental run/skip/blocked plan and appends actual stage timings. Locked work upgrades the preview to continuous final media and the final mix. After explicit approval, the output adds archival and platform files plus rendered cover images. Validation covers invalidation regression tests, subtitle round-trip integrity, streams, dimensions, timeline overlap, decodability, loudness, protected results, cover safe zones, and visual inspection.

## Skill Version

0.18.0

## Ethical Considerations

Process only materials the user has the right to use. Keep credentials and account data outside the Skill and its reports. Do not invent platform read-back, success rates, or performance claims.

## LovStudio Evidence

### User Cases

See [`cases/cases.json`](cases/cases.json). The cases record real Input → Prompt → Output runs across screen recordings, Screen Studio episodes, an independent-clip regression and a travel vlog. Each case states its own publication evidence. For the travel vlog, the WeChat Channels upload was still in original-content review at the last list read-back, and the Bilibili submission had been returned by platform review, pending the author's decision.

### Dimension Map

The machine-readable card records four evidence-backed dimensions: editorial fit, audio integrity, technical delivery, and status traceability.

### Pricing Basis

See [`pricing-card.yaml`](pricing-card.yaml). The local Skill is free; its boundary excludes cloud rendering, media licensing, account credentials and platform operation.

### Distribution

Paid channels: `workbuddy` and `skillpay` are `not-published`. Free channels: `github` is `not-published`, and `lovstudio` is `local-only`. None of these states claims a live remote release.
