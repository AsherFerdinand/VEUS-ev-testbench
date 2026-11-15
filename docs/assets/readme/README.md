# README presentation assets

These are captures of the actual, unchanged VEUS application, not mockups or
AI-generated UI. The source is completed Phase 11 commit
`2caf8f4970ea736bd5f052ba43911d54311e0606`. This documentation branch does not change
physics, controllers, import logic, test assertions or application behaviour.

## Media inventory

| File                                                 | Dimensions |      Size | Content                                                                       |
| ---------------------------------------------------- | ---------- | --------: | ----------------------------------------------------------------------------- |
| [veus-hero.gif](veus-hero.gif)                       | 1280 × 720 | 743.2 KiB | 100 real browser frames, 10 fps, 10 seconds, infinite loop                    |
| [drive-overview.png](drive-overview.png)             | 1280 × 720 |  86.8 KiB | Illustrative sedan accelerating; live speed, SOC and battery power            |
| [investigate-overview.png](investigate-overview.png) | 1280 × 900 | 123.0 KiB | Genuine VED trip 1561, selected acceleration event at 143.0–144.1 s           |
| [compare-overview.png](compare-overview.png)         | 1280 × 900 | 121.3 KiB | Trips 1561 and 1567, independently navigable elapsed-time plots               |
| [validate-overview.png](validate-overview.png)       | 1280 × 900 | 102.5 KiB | Existing simulation configuration, controller settings and response telemetry |

Total new image payload: approximately **1.15 MiB**. Exact byte counts, dimensions,
file formats, hashes and animation metadata are in [media.json](media.json).
The existing [Phase 11 report screenshot](../../phase11-evidence/engineering-report.png)
is reused through the evidence link rather than duplicated. The focused investigation
capture scrolls to the selected event and its plots; it is not a new application layout.

## Reproduce the captures

Use an externally installed Playwright and Chromium, plus FFmpeg. These are optional
documentation tools, not new VEUS runtime dependencies. Start the application from
the repository root, then run:

```bash
# In another terminal, serve VEUS:
python -m uvicorn veus.studio.main:app --port 8770

# From the repository root; set these paths for your own tools if needed:
PLAYWRIGHT_MODULE=/path/to/node_modules/playwright \
CHROMIUM_PATH=/path/to/chromium \
node docs/assets/readme/capture.cjs

ffmpeg -framerate 10 -i /tmp/veus-readme-frames/%03d.png \
  -filter_complex '[0:v]split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle' \
  -loop 0 -y docs/assets/readme/veus-hero.gif
```

`VEUS_URL`, `MEDIA_OUTPUT` and `FRAME_OUTPUT` optionally override defaults. Capture
uses only existing UI actions, normal scrolling and screenshots: select sedan, run,
accelerate, brake, release, reset, then return to a stationary running state for the
loop. Frame pacing targets 100 ms; machine load can affect source timing. No frames
are fabricated, no source measurements are altered and no app CSS is overridden.
The GIF has a 128-colour palette and rectangle-based encoding; screenshots remain PNG.
[Capture metadata](capture.json) records readout samples and the exact selected event.

Raw frame PNGs remain outside Git in `/tmp`; no temporary videos, browser caches,
virtual environments or rendering-tool bundles are included in the commit.

## Presentation checks

- All repository-relative README links and images are checked for existence;
  internal navigation targets match headings. The preserved prior README has its
  relative links adjusted for its new location in `docs/engineering-reference.md`.
- Local GitHub-flavoured Markdown preview uses the installed Marked renderer and
  GitHub Markdown CSS 5.8.1. Light/dark desktop and mobile layouts are checked in
  Chromium, along with native `<details>` expansion and local image loading.
- Mermaid 11.12.1 actually parses and renders the two independent workflows.
  It is a check tool outside the committed repository, not a project dependency.
- PNG/GIF signatures match extensions. The GIF contains 100 frames, loops forever
  and has a 10,000 ms duration. Its decoded playback was inspected in Chromium.
- No credentials, local file paths, usernames or browser chrome appear in the media.
- Shields.io URLs use standard static badge syntax. This cloud network blocks
  `img.shields.io` and the GitHub Markdown API with HTTP 403, so badge retrieval and
  GitHub's own server-side rendering cannot be verified here. The local GFM preview
  checks rendering and local assets; it is not a claim of inspection on GitHub itself.

## Commands and engineering claims

`git ls-remote --symref origin HEAD` confirmed `main` as the default branch and
Phase 11 at `2caf8f4`; the Quick Start explicitly switches to that branch. Python
3.12.9 was used to create a fresh environment outside the checkout, install
`requirements-report.txt`, pass `pip check`, start Uvicorn, load the four-recording
catalogue and generate an HTML investigation report. PowerShell syntax and Windows
paths were checked; Windows itself was not available for an end-to-end launch.

The existing suite was rerun: **187 Python tests and 9 playback-clock tests pass**.
One existing Starlette/httpx deprecation warning remains. README counts are labelled
as the Phase 11 evidence snapshot, not a maintained status badge. Source/test files
and all prior engineering evidence remain unchanged. For physical validity, the
Phase 8 assessment remains **INCONCLUSIVE**.

See [qa.json](qa.json) for the bounded check results and media inventory.
