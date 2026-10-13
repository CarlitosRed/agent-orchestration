# F4 report: the verification skill generator (Platform Engineer, 2026-10-13)
Milestone F4: a model-agnostic generator that gives any project a verification skill and a feature map, plus its upkeep loop and a demo-recording skill on top. Built only inside this repo; no project repository was read or run. Nothing committed; the Orchestrator commits.

## Built
| File | What |
| --- | --- |
| `skills/create-verification-skill/SKILL.md` | Generator. Interviews the target repo (adapter files, README, manifests, CI, existing e2e tests, routes, CLI parsers) for surfaces, launch command, drive method, evidence, data source, safe mode, side-by-side. Writes `.orchestration/verify/` (SKILL.md + `features/` + `.gitignore`) from two templates, then proves itself once: launch, doctor, drive one feature with a side effect, hash evidence, cleanup, invariant check, re-hash. Outcome `proven` or `blocked`. |
| `skills/maintain-verification-skill/SKILL.md` | Upkeep. Source wave (one read-only worker per feature file, parallel, source only, `matches` or `drift` with `path:line`, plus one worker for unmapped features), required live pass (doctor before the first drive and after every non-pass drive), triage table (doc drift / harness gap / product bug; only the first two are fixed), one outcome: clean / changed (one PR of proven corrections) / blocked. |
| `skills/record-demo/SKILL.md` | One shareable recording from the feature map: requires a verification skill and features proven at the current sha; read-only on product code; data check before the first frame (ask rather than record); paced frames, captions from "Demo caption" or "How to reach it" + "Proof", optional video or gif, output folder with `index.md`, `captions.md`, `manifest.json`. Never publishes. |
| `adapters/README.md` | Edited: `verify/` added to the list, `commands.md` points at it, new section "Verification" with the folder and feature-file shape. Rest unchanged. |

## Matches the pstack reference pair (I-001)
Source for the comparison: `ideas/2026-10-13-pstack-and-advisor.md` only. The pstack repo itself was not on disk this session, so I did not re-read `create-verification-skill` / `maintain-verification-skill` at commit dbf4981; everything below is checked against the idea note, not the primary source.
- Project-local skill that drives the real app like a user: yes (`.orchestration/verify/`).
- Feature map, one file per feature (how to reach, how to drive, what proves it): yes, plus Setup, Cleanup, Pointers, Demo caption.
- Evidence capture, cleanup without deleting evidence: yes, made checkable (manifest with size and SHA-256, re-hash after cleanup).
- Maintain loop: source wave per feature, one live pass, at most one PR of proven corrections: yes.

## Deliberate differences
1. **Vendor-neutral.** pstack is Cursor-specific (its task tools, model routing). Here every tool is a capability ("a browser automation tool", "a PTY or terminal-multiplexer harness"); a missing capability is reported, never faked.
2. **Precise terms in one block** (session, doctor with five checks, drive with three outcomes, cleanup, invariant, survival, real user path, side effects, safe mode observed) copied verbatim into every generated skill, so a cold reader of the project skill needs nothing else.
3. **Product bugs are never fixed or papered over** in maintenance: when triage is unsure, it is a product bug and the feature file stays as it was.
4. **Data safety** (synthetic only, doctor checks a data marker, stop and ask) and the **demo skill** are additions for this framework's needs; the idea note asked for the recording on top.
5. **Side-by-side instances** are recorded, not required; maintenance runs one session serially.

## Not built, and the limitation
- **Nothing was proven end to end.** F1 to F3 proved their tools with real test runs (224 and 62 tests). F4's skills are prose for agents; there is no target project wired into this repo, and the brief forbids driving one in this milestone. No skill here has been executed even once, so every step is a design that may fail on contact with a real app.
- **First real trial (recommended):** run `create-verification-skill` on the first project (its web UI is the primary surface, and its CI has no browser test lane), on a branch, with its demo data set: outcome must be `proven`. Then `maintain-verification-skill` once (expect `clean`), then `record-demo` on two or three features. Measure: did the proof run need edits to the skill files, how many, which steps; time to `proven`; whether the doctor's data marker and the invariant check were actually checkable on that app. Feed every friction into a framework change proposal before the second project (F5) uses it.
- No vendor wiring: `vendors/` does not exist yet (F7). Mapping each capability to a vendor's actual tools (browser, PTY, recorder, encoder, parallel workers) is a gap until then.
- No scripts: manifest writing, hashing and the process/port check are described, not shipped as a tool. A small standard-library helper (`tools/verify-manifest/`) would make "evidence survives cleanup" and the invariant enforced instead of advice.
- Narrated audio for demos: out of scope (captions and title cards only).

## Clearly specified vs PROPOSED
| Part | Status |
| --- | --- |
| Folder shape, feature-file sections, terms block, doctor's five checks, drive outcomes, three maintenance outcomes, triage table, demo output folder | specified (as prose; no tool enforces it) |
| Adapter "Verification" section as a requirement for every project | PROPOSED until one project proves it |
| Evidence inside the repo under a nested `.gitignore` (vs outside the repo) | PROPOSED |
| Feature cap (map 10 fully when more than about 25) | PROPOSED, a guess |
| Pacing numbers (2 s per frame, 3 to 4 with text, 3 min target, 1280x800) | PROPOSED, defaults |
| Product-bug-when-unsure triage rule | specified |
| Tier of `verify/` changes | left to each project's `gate.json` |

## Unsure
1. The pstack comparison rests on our own idea note, not a re-read of the source at dbf4981; the pstack pair may have steps (for example its exact doctor or cleanup checks) I did not reproduce.
2. The terms block is duplicated in two skills and in every generated skill; drift between copies is a C6 risk. A check or a single shared file would be better, but a shared file breaks "readable cold".
3. Doctor check 3 (instance runs the checkout's sha) is hard for apps that do not expose their version; the generator may have to fall back to "launched from this checkout at this sha", which is weaker.
4. "Looks like real data" is a judgment by the agent; it will miss some and over-flag synthetic data that looks realistic.
5. Whether a parallel source wave is worth its cost on small maps; for under about 10 features one worker may be cheaper.
6. Whether evidence should ever be shareable from the repo's folder: a demo meant for outside the team lives in a git-ignored folder on one machine until someone copies it.
