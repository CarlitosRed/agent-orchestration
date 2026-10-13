---
name: record-demo
description: Produce one shareable demo recording of a project - a scripted walkthrough of its feature map (or a chosen subset) captured as paced screenshots and, where the environment can, a short video or gif, with one caption paragraph per feature and an index, in one output folder. Built on the project's generated verification skill; requires `.orchestration/verify/` with a feature map. Read-only on product code. Synthetic or redacted data only.
---

# Record a demo

## Requires (check first; stop if missing)
- `.orchestration/verify/SKILL.md` and `.orchestration/verify/features/` in the project. If missing, run **create-verification-skill** first. Each feature you will show must be proven at the current sha: its status line says `proven at <current sha>`, or a maintain run manifest (`evidence/*-maintain/manifest.json`) at the current sha shows it `pass`. Otherwise run **maintain-verification-skill** first. A demo of an unproven feature is not made.
- From the requester: which features (default: every `proven` feature, map order), the audience (team or outside), the output format (screenshots plus captions always; video or gif if wanted), and target length (default: at most 3 minutes).

## Ground rules
- **Read-only on product code, tests and data.** You write only the demo output folder. You launch, drive and clean up exactly as the verification skill says; its Terms (session, doctor, drive, cleanup, invariant, evidence survives cleanup) apply unchanged.
- **Synthetic or redacted data only; ask rather than record.** Never record or transcribe real customer or private data. See "Data check" below; if anything looks real, stop and ask the requester, and record nothing until they answer.
- **Nothing staged or faked.** Every frame comes from a real drive of the running app at the recorded sha. If a feature's drive does not `pass`, it is left out and the index says so; it is never mocked, edited in, or replaced by an older capture.
- **No secrets on screen**: no tokens in address bars, no keys in terminals, no environment dumps. Hide or crop before capture, never after the fact on a frame that will be shared.
- **You do not publish.** Sharing outside the team is the project owner's decision; you hand over a folder.
- **Capabilities, not product names**: "a browser automation tool", "a screen or window recorder", "an image-sequence-to-video encoder", "a PTY or terminal-multiplexer harness" mean whatever your environment provides. If there is no recorder or encoder, deliver the screenshot sequence and say which capability was missing.

## Data check (before the first frame, and again whenever a new screen shows data)
1. The doctor's data marker must match the declared synthetic set.
2. Look at every screen, transcript and response that will be captured for: personal names paired with real-looking emails or phone numbers, street addresses, account, order, invoice or card numbers, signatures, scanned documents, anything the project's docs call customer data. Synthetic data that the fixtures declare as synthetic is fine.
3. If anything looks real or you cannot tell: stop, describe what you saw (field and screen, not the value), and ask. Options to offer: switch to the synthetic set, redact by changing the fixture (not the frame), or drop the feature.

## Steps
1. **Plan the script.** For each chosen feature, from its feature file: the steps from "How to reach it" and "How to drive it", the frames to capture (start state, each meaningful step, end state, one frame of the side effect where it is visible to a user or through a read-only view), and its caption: the feature's "Demo caption" if present, else one paragraph written from "How to reach it" and "Proof" (what the user does, what they see, what it proved). Captions: plain language, at most four sentences, no internal names. Estimate time per feature; cut features to fit the target length and say which were cut.
2. **Launch and doctor** per the verification skill. Use a clean, synthetic data state. Set a fixed window or terminal size (default 1280x800 for screens, 100x30 for terminals) so frames line up.
3. **Data check** (above).
4. **Record, feature by feature.** Run the feature's drive with capture on. Pacing: hold each frame at least 2 seconds in a video (3 to 4 for a frame with text to read); type at a readable speed or show the typed result as its own frame; no frame changes faster than a viewer can follow. After any drive that is not `pass`: doctor, retry once, then leave the feature out.
5. **Cleanup and teardown**; check the invariant and that every recorded file survives cleanup (size and SHA-256 unchanged).
6. **Assemble** the output folder (below). If a video or gif is wanted and an encoder exists, build it from the recorded frames or the recorder's file; put the caption text on screen as a title card before each feature or as burned-in subtitles. Narrated audio is out of scope unless the requester supplies it.
7. **Review before handover.** Look at every frame and the video once, end to end, for real data and secrets. One hit means remove the feature or re-record it on synthetic data.

## Output folder
`.orchestration/verify/evidence/<UTC yyyymmdd-hhmmss>-demo/` (git-ignored; copy elsewhere only on request):
```
index.md        title, project, sha, date, data statement, feature list with links, skipped features and why
NN-<slug>/      frames as NN-MM-<step>.png (or .txt for terminals), caption.md
demo.<mp4|gif>  optional; length and resolution in index.md
captions.md     all captions in order (also usable as narration script)
manifest.json   run id, sha, features shown and skipped, every file with size and sha256, invariant and survival results
```
`index.md` must state, in its first lines: "Recorded from <project> at <sha> on <date>. All data shown is synthetic." (or "synthetic and redacted", saying what was redacted and how).

## Hand over
Report: the folder path, features shown and skipped (with reasons), length, formats produced, capabilities missing, data check result, invariant and survival results. Nothing is shared outward by you.
