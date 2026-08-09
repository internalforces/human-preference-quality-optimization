# StringArtio vs spejamchr/string_art Reference Comparison

Date: 2026-06-29

Reference repository: https://github.com/spejamchr/string_art

Reference commit inspected: `9fd71fe2f297be6d325e3b2cfca37f9bc2a6e5e9`

Scope note: this report treats the open-source project as a reference implementation only. It does not recommend copying code. Recommendations are incremental and preserve the StringArtio app, harness, and Preference Lab boundaries.

Status note: the companion Preference Lab implementation plan that was derived
from this comparison has been retired. Lab-owned follow-up work is now reflected
in the active README, architecture, data-flow, preference-schema, and visibility
failure documents. This comparison remains as research context and as a list of
StringArtio-owned or future experiment ideas.

## Source Evidence

Primary reference files:

- [`src/string_art.rs`](https://github.com/spejamchr/string_art/blob/9fd71fe2f297be6d325e3b2cfca37f9bc2a6e5e9/src/string_art.rs)
- [`src/style.rs`](https://github.com/spejamchr/string_art/blob/9fd71fe2f297be6d325e3b2cfca37f9bc2a6e5e9/src/style.rs)
- [`src/optimum.rs`](https://github.com/spejamchr/string_art/blob/9fd71fe2f297be6d325e3b2cfca37f9bc2a6e5e9/src/optimum.rs)
- [`src/imagery.rs`](https://github.com/spejamchr/string_art/blob/9fd71fe2f297be6d325e3b2cfca37f9bc2a6e5e9/src/imagery.rs)
- [`src/pins.rs`](https://github.com/spejamchr/string_art/blob/9fd71fe2f297be6d325e3b2cfca37f9bc2a6e5e9/src/pins.rs)
- [`src/auto_color.rs`](https://github.com/spejamchr/string_art/blob/9fd71fe2f297be6d325e3b2cfca37f9bc2a6e5e9/src/auto_color.rs)
- [`src/cli_app.rs`](https://github.com/spejamchr/string_art/blob/9fd71fe2f297be6d325e3b2cfca37f9bc2a6e5e9/src/cli_app.rs)

Primary StringArtio files:

- `/path/to/stringartio/src/stringArt.js`
- `/path/to/stringartio/modules/string-art-native/rust/src/lib.rs`
- `/path/to/stringartio/src/features/stringArt/imageSampling.js`
- `/path/to/stringartio/src/features/stringArt/generatePattern.js`
- `/path/to/stringartio/src/features/stringArt/stringArtSettings.js`
- `/path/to/stringartio/src/components/StringArtCanvas.js`
- `/path/to/stringartio/src/features/stringArt/exportResult.js`
- `/path/to/stringartio/scripts/stringArtMetrics.mjs`
- `/path/to/stringartio/scripts/stringArtTuningCore.mjs`
- `/path/to/stringartio-preference-lab/src/stringartio_preference_lab/*.py`

Verification performed:

- `cargo test` in the reference repo passed: 66 tests, 0 failures.
- No generator execution was run in StringArtio. No project source or experiment output was modified by this report.

## Executive Summary

Fact: the reference project is a compact Rust CLI. Its core architecture is easy to understand: parse CLI args, decode an image, generate pins, choose line segments by residual score improvement, render a raster output, optionally write JSON and GIF artifacts.

Fact: StringArtio is a larger product system: Expo app, JS fallback generator, Rust native generator, image normalization, app preview/export, experiment harness, metrics, promotion gates, and a separate Human Preference Learning sidecar.

Opinion: StringArtio is more scalable as a product and research platform. It has the right high-level separation between app runtime, experiment harness, and preference learning. The reference is more scalable as a small algorithmic kernel because its scoring/rendering model is much simpler and easier to test.

Most useful ideas and current status:

1. Adopt reference-style score-delta invariants as tests: still StringArtio-owned
   generator work.
2. Add a simple residual-only diagnostic score lane: Preference Lab now accepts
   and exports residual diagnostic fields when StringArtio emits them, and
   excludes residual fields from reward-model training by default.
3. Tighten render/model calibration: Preference Lab now extracts rendered SVG
   stroke opacity/width diagnostics from existing artifacts and uses them in
   queue and suggestion risk scoring. StringArtio still owns any rasterized
   preview/export calibration metric.
4. Treat the reference add/remove loop as a bounded local-search experiment:
   Preference Lab now records handoff intent and future trace fields only;
   generator execution remains StringArtio-owned.
5. Consider reference-style auto color selection as an app/harness suggestion
   layer: Preference Lab records a conservative auto-color handoff intent only.

Most unsuitable ideas:

1. Do not replace StringArtio's crop/preprocessing/target-map pipeline with the reference pipeline. The reference has almost no image preprocessing.
2. Do not adopt full all-pairs scoring every step on mobile without candidate limits. It is clean but expensive.
3. Do not expose grid/random/perimeter pins as app defaults for a physical circular-board product.
4. Do not treat RGB residual score as human preference. It is a useful diagnostic, not the quality objective.

## 1. Overall Architecture

### Reference Architecture

Fact: the reference code is organized into small Rust modules:

| Module | Role |
|---|---|
| `main.rs` | Calls `string_art::create_string()` |
| `cli_app.rs` | CLI argument parsing, image decode, color/background option normalization |
| `pins.rs` | Perimeter, grid, circle, and random pin generation |
| `geometry.rs` | Vectors, points, line iterator with configurable step size |
| `imagery.rs` | RGB math, pixel-line rasterization, reference image score and score deltas |
| `optimum.rs` | Parallel best-line and worst-line selection |
| `style.rs` | Main optimization loop, output raster, GIF capture, JSON data |
| `auto_color.rs` | Dominant foreground/background color selection |

The main flow is visible in `string_art::create_string`: parse args, generate pins, optionally draw pin crosshairs, run `style::color_on_custom`, and write JSON data if requested (`src/string_art.rs:7-31`).

### StringArtio Architecture

Fact: StringArtio is split across app runtime, native runtime, harness, and Preference Lab:

| Layer | Key Files | Role |
|---|---|---|
| App flow | `src/features/stringArt/generatePattern.js` | normalize image, preprocess source, choose settings, call native-first generator, attach timings/debug maps |
| JS generator | `src/stringArt.js` | target map, residual map, path cache, line scoring, JS fallback |
| Native generator | `modules/string-art-native/rust/src/lib.rs` | production mono generator with progress, Rayon scoring, refinement, pruning, opacity calibration |
| Rendering/export | `src/components/StringArtCanvas.js`, `src/features/stringArt/exportResult.js` | SVG preview, SVG export, pin sequence, metadata |
| Tuning harness | `scripts/stringArtTuningCore.mjs`, `scripts/stringArtMetrics.mjs` | search, metrics, review HTML, score lanes |
| Preference Lab | `src/stringartio_preference_lab/` | ingest, features, blind queue, Bradley-Terry model, constrained suggestions |

The documented runtime chain is image picker/prepared asset -> `normalizeImageForSampling` -> `preprocessStringArtSourceJpegBase64` -> `createStringArtPatternNativeFirstFromJpegBase64` -> render/export.

### Scalability Judgment

Fact: StringArtio is more scalable at the system level. It supports mobile runtime concerns, native fallback, tuning, human review, and constrained suggestion generation. The reference project does not have a separate evaluation or preference-learning loop.

Fact: the reference is more scalable at the kernel-comprehension level. Its residual score is small, testable, and directly tied to rendering (`imagery.rs:217-233`, `style.rs:98-214`).

Opinion: the best direction is not architectural replacement. Preserve StringArtio's system boundaries, but extract more testable kernel invariants from the reference model.

## 2. Image Preprocessing

### Stage Comparison

| Stage | Reference | StringArtio | Missing / Opportunity |
|---|---|---|---|
| Decode | Uses Rust `image` reader in `Cli::image` (`cli_app.rs:119-145`) | JPEG base64 decode via `jpeg-js` and native image normalize paths | Both have decode. StringArtio has more app-safe fallback behavior. |
| Resize/downsample | No explicit resize in the core. Runs at decoded image size. | `sampleSize` defaults to 384, supports 256/384/512; native decode max 2048; prepared image max 1536 (`stringArtSettings.js:8-15`) | Keep StringArtio approach. Reference offers no improvement here. |
| Crop | None. Pins use full image dimensions. | Center crop, composition-preserve mode, saliency focus crop with confidence (`imageSampling.js:43-121`, `171-227`) | Keep. Add better crop validation rather than borrowing reference. |
| Grayscale/luminance | No preprocessing grayscale. Scoring is RGB residual against chosen foreground/background. | Luminance/darkness target map for mono; RGB channels retained for sampled/palette color modes (`stringArt.js:1533-1555`) | No gap. |
| Contrast | Only auto-color applies very high contrast before ranking colors (`auto_color.rs:72-90`) | Source preprocess contrast and gamma (`stringArt.js:1078-1157`, `1159-1191`) | Reference contrast is useful only for color quantization, not image quality. |
| Gamma | None | Source preprocess gamma (`stringArt.js:1085-1089`, `1166-1175`) | Already present. |
| CLAHE/local equalization | None | Local luminance equalization controlled by `claheStrength`/`claheRadius` (`stringArt.js:1364-1435`) | Present, though implementation is local min/max rather than full CLAHE histogram bins. |
| Histogram equalization | None | Local luminance equalization only | A true clipped histogram equalizer could be a P2 experiment, but current local equalization may be enough. |
| Blur | None | Heavy use of `blurMap` for target features; tunable blur in harness search | Present in target-map construction. |
| Denoise | None | No formal denoise, but quiet detail suppression and background suppression reduce texture noise (`stringArt.js:1193-1249`, `1974-2026`) | A mild bilateral/edge-preserving denoise could be tested, but risk blurring facial detail. |
| Edge extraction | None for generation score | Sobel, Laplacian, DoG, canny-like edge candidate values (`stringArt.js:1610-1665`, `1720-1745`) | StringArtio is much stronger. |
| Edge enhancement | None | Chromatic edge darkening (`stringArt.js:1277-1354`) and edge-weighted target construction | Already present. |
| Detail enhancement | None | Interest-guided detail enhancement (`stringArt.js:1193-1249`) | Already present. |
| Background suppression | None | Foreground/background/quiet gates, adaptive suppression (`stringArt.js:1941-2017`) | Already present. |
| Foreground extraction | None | Heuristic subject/interest/ROI maps, not segmentation (`stringArt.js:1715-1972`) | True segmentation is missing but likely outside current low-risk scope. |
| ROI handling | None | Saliency crop plus face/hair/background density summaries (`stringArt.js:5922-5987`; `stringArtTuningCore.mjs:5336-5400`) | Current ROI is heuristic and portrait-biased. Better named generic ROIs would reduce hidden assumptions. |
| Masking | None | Circular board mask (`stringArt.js:1446-1450`) | Appropriate for physical circular-board product. |

### Preprocessing Conclusion

Fact: the reference has very little preprocessing. Its main preprocessing-like behavior is auto-color ranking after extreme contrast adjustment. It does not implement resize, crop, CLAHE, denoise, edge extraction, ROI, or masks.

Opinion: the reference should not drive StringArtio preprocessing changes except for color selection ideas. StringArtio's current preprocessing/target-map stack is much more relevant to portrait quality.

## 3. String Generation Algorithm

### Reference Algorithm

Fact: the reference generates candidate lines from all pin pairs and all foreground colors. `find_best_points` uses Rayon parallel iterators over pins and colors, computes `score_change_on_add`, filters score improvements, sorts by score, and takes the best batch (`optimum.rs:9-30`).

Fact: after adding batches, the reference searches existing lines for harmful lines. `find_worst_points` computes `score_change_on_sub`, filters removals that improve score, sorts, and removes them (`optimum.rs:32-50`).

Fact: the main loop alternates adding and removing. It adjusts `max_at_once`, captures GIF frames if requested, stops when no add/remove improves the residual or max strings is reached (`style.rs:98-214`).

Algorithm classification:

| Method | Reference |
|---|---|
| Greedy | Yes, best immediate score improvements |
| Batch greedy | Yes |
| Local search | Yes, via removal of bad existing lines |
| Beam search | No |
| Simulated annealing | No |
| Evolutionary runtime search | No |
| Bayesian optimization | No |
| Pruning | Yes, removal pass |
| Caching | Minimal explicit caching; residual image is maintained, but candidate PixLines are recomputed |
| Parallelism | Yes, Rayon over candidate pairs/colors |

### StringArtio Algorithm

Fact: the JS path creates nails, target map, residual map, path cache, then starts from a best starting line and walks from current nail to next nail with periodic global reseeds (`stringArt.js:263-591`).

Fact: candidate generation is bounded by current/global/starting candidate limits (`stringArt.js:617-647`). It does not score every pair on every step in JS.

Fact: StringArtio adds penalties and steering for recent nails, similar lines, direction crowding, pin cooldown, endpoint reuse, and line-length balance (`stringArt.js:5663-5823`).

Fact: the native Rust path mirrors the production generation strategy and adds post passes: opacity calibration, residual refinement lines, residual basis lines, replacement, low-contribution pruning, final-line-cap pruning, and final opacity calibration (`lib.rs:842-955`).

Algorithm classification:

| Method | StringArtio |
|---|---|
| Greedy | Yes, best scored candidate at each step |
| Batch greedy | Mostly no in JS main walk; native post passes add/refine groups |
| Local search | Yes in native post-processing and pruning; less explicit in JS fallback |
| Beam search | No |
| Simulated annealing | No |
| Evolutionary methods | Not in runtime; harness has random/evolutionary-style search actions (`stringArtTuningCore.mjs:764-814`) |
| Bayesian optimization | Preference Lab has constrained BO skeleton for suggestions only (`src/stringartio_preference_lab/optimizer.py`) |
| Pruning | Yes in native, plus final cap / visual post-processing |
| Caching | Yes, line path cache (`stringArt.js:3535-3584`) |
| Parallelism | Yes in native Rust via Rayon; JS path is more constrained |

### Algorithmic Difference

Fact: the reference explores more globally inside the core loop: all pair/color candidates can compete for each batch.

Fact: StringArtio is more app-runtime friendly: it samples candidate pools, caches paths, tracks repeated/crowded lines, and keeps progress/timing metadata.

Opinion: the reference add/remove loop is the main algorithmic idea worth adapting. It should be tried as a bounded experiment in the harness, especially for JS fallback parity and for explaining negative-contribution lines. It should not replace the native pipeline wholesale because the native core already has refinement/pruning passes.

## 4. Scoring System

### Reference Scoring

Fact: reference scoring is pure squared RGB residual. `RefImage::score` sums `r*r + g*g + b*b` over pixels (`imagery.rs:217-260`).

Fact: line scoring predicts the delta from adding or subtracting a line by applying pixel-level RGB differences to only the pixels touched by the candidate line (`imagery.rs:221-233`).

Fact: `style::color_on_custom` converts the target image into a residual space relative to the chosen background and foreground colors (`style.rs:25-38`).

Strengths:

- Very clear objective.
- Add/remove score changes are easy to test.
- Rendering and scoring use the same line rasterization model.
- Multi-color line selection is naturally included because color is part of each candidate.

Weaknesses:

- RGB residual does not understand perceived string-art quality.
- No explicit edge similarity, subject saliency, clump penalty, overdraw penalty, line distribution, or human preference signal.
- It can overfit the source image as reconstruction rather than artwork.

### StringArtio Scoring

Fact: StringArtio's line score starts from squared-error reduction but multiplies it by edge/detail/tone/focus/interior/ROI terms and subtracts or scales penalties for overdraw, density, dark saturation, quiet background, and unstructured ink (`stringArt.js:4461-4990`).

Fact: StringArtio summarizes reconstruction with `reconstructionRate`, `coverageRate`, `overdrawRate`, `positiveCoverageRate`, `underdrawReductionRate`, `visualReconstructionRate`, and ROI density (`stringArt.js:5856-6042`).

Fact: the harness adds SSIM, edge similarity, MAE, MSE, contrast, detail, face detail, localized detail, line clump penalty, noise penalty, and target score (`stringArtTuningCore.mjs:5207-5270`).

Fact: Preference Lab turns metrics/config columns into a Bradley-Terry-style pairwise preference model and treats `tie` and `both_bad` specially (`model.py:74-137`, `187-257`).

Strengths:

- Better aligned with the product goal of clean, legible string art.
- Captures failure modes the reference ignores: clumping, overdraw, quiet background ink, weak hair/face density, app readiness.
- Supports human preference learning.

Weaknesses:

- Harder to reason about because many heuristics interact.
- Higher risk of reward hacking in tuning.
- Rendering/generation calibration can drift because generation line ink and SVG preview/export opacity are separate layers.

### Scoring Recommendation

Opinion: do not simplify StringArtio's primary score to the reference score. Instead add a reference-like residual score lane as a diagnostic. Use it to catch contradictions, not to promote candidates.

## 5. Rendering

### Reference Rendering

Fact: the reference renderer is the same model used for scoring. A `PixLine` maps a geometric line to touched pixels, scales RGB contribution by `step_size * string_alpha`, and accumulates repeated samples (`imagery.rs:175-192`).

Fact: final output is built as a `RefImage` from line segments and saved as a raster image (`imagery.rs:284-297`, `style.rs:54-56`).

Fact: there is no separate preview/export style layer. The image buffer is the output.

Strength: model/render agreement is high.

Weakness: output is raster-first; physical/SVG styling controls are limited to alpha, step size, background, and foreground colors.

### StringArtio Rendering

Fact: generation applies ink into a residual approximation with a 5-sample cross kernel (`stringArt.js:6490-6527`).

Fact: selected lines store opacity and width derived from `renderWeight`, then app preview draws SVG lines with round caps inside a circular clip (`StringArtCanvas.js:43-65`).

Fact: export writes an SVG, pin-sequence text, and metadata (`exportResult.js:12-39`, `116-170`).

Strengths:

- Better for a mobile app, user preview, physical guide, and scalable export.
- SVG with round caps and per-line opacity/width can look cleaner than raw pixel accumulation.
- Export metadata and pin sequence are product-ready.

Weakness:

- Generation uses line ink while rendering uses opacity/width mapping. That creates calibration risk.
- Clean preview mode can alter opacity/width after generation (`renderStyle.js:29-69`).

Recommendation:

Add a rasterized-export/preview scoring pass in the harness. It should render the same SVG/line style that users see, convert it to a comparable darkness map, and compare it to target/residual metrics. This borrows the reference's model/render alignment without giving up SVG.

## 6. Performance

### Reference

Fact: performance strategy is simple parallel brute force:

- all pin pairs and colors are scored with Rayon (`optimum.rs:17-27`);
- existing lines are scored for removal with Rayon (`optimum.rs:39-49`);
- no GPU path;
- no mobile progress contract;
- likely higher per-iteration cost as pin count and color count grow.

Potential bottlenecks:

- Recomputing `PixLine` for candidate lines during add/remove scoring.
- Sorting all improving candidates every batch.
- Full pair search is costly at high pin counts.

### StringArtio

Fact: performance strategy is product-oriented:

- native Rust first, JS fallback (`stringArt.js:107-175`);
- candidate limits for current/global/starting selection (`stringArt.js:617-647`);
- path cache with summary metadata (`stringArt.js:3535-3584`);
- native progress phases (`lib.rs:491-529`, `615-624`);
- performance snapshots expose detailed timings (`imageNormalizePipeline.js:115-229`);
- Preference Lab enforces runtime and line-count constraints before suggestions
  (`src/stringartio_preference_lab/optimizer.py`).

Potential bottlenecks:

- Path cache memory for high pin counts.
- Complex target-map construction and many feature maps.
- Native post passes and repeated opacity calibration.
- Keeping JS fallback behavior close to native behavior.

Performance recommendations:

1. Keep current candidate limits for app runtime.
2. Add a full-pair/reference-style scoring mode only for low pin counts or offline harness diagnostics.
3. Use reference-style score-delta tests to make future optimizations safer.
4. Consider path-cache compression and two-stage candidate prefilters before increasing pin counts.
5. Keep GPU out of scope unless profiling shows a clear target-map/render bottleneck.

## 7. Engineering Quality

### Reference

Strengths:

- Small modules with clean responsibilities.
- Strong unit tests for geometry, pins, CLI, auto-color, and score delta behavior.
- Simple CLI and data output.
- Easy to read and modify.

Limitations:

- Limited documentation beyond README examples.
- No mobile/app boundary.
- No evaluation harness for perceptual quality.
- No human-review or preference-learning workflow.
- No export metadata designed for physical product workflows beyond JSON line segments.

### StringArtio

Strengths:

- Strong system documentation and operating boundaries.
- App/runtime/harness/Preference Lab separation.
- Native-first production path with JS fallback.
- Detailed performance, metrics, and review artifacts.
- Preference Lab has tests for ingest, features, review queue, preference model, suggestions, and constraints.

Limitations:

- `src/stringArt.js` and `modules/string-art-native/rust/src/lib.rs` are both large algorithm modules.
- Many tuning parameters make behavior hard to audit.
- Some ROI naming is portrait-specific.
- Native and JS parity is costly to maintain.

Engineering recommendation:

Do not rewrite. Instead, extract small testable seams around residual scoring, line application, render calibration, and candidate pruning. The reference is useful mainly as evidence that simple kernel invariants pay off.

## 8. Feature Comparison

| Feature | Open Source | StringArtio / Preference Lab | Recommendation |
|---|---|---|---|
| Primary form | Rust CLI | Expo mobile app plus Rust native module plus Python sidecar | Keep StringArtio architecture. |
| Image input | File path | Device assets, JPEG base64, native normalize | Keep. |
| Output image | Raster image | App SVG preview/export, captured result, metadata | Keep; add rasterized-preview metric. |
| Pin sequence export | JSON line segments | Pin sequence text and SVG metadata | Keep StringArtio export. |
| Data export | JSON with args, scores, pins, line segments | Metadata, metrics, experiment artifacts, Preference Lab manifests | Consider adding a compact per-run algorithm trace for native pruning/calibration. |
| GIF/time-lapse | Yes | No obvious app export | P3 nice-to-have. |
| Pin crosshair debug image | Yes | Show nails in SVG/app preview | Already covered. |
| Pin arrangements | Perimeter, grid, circle, random | Circular board pins | Test variants only in harness; do not default in app. |
| Physical board diameter | No | Yes, board diameter and pin spacing | StringArtio stronger. |
| Resize/downsample | No explicit core resize | Yes | Keep. |
| Saliency crop | No | Yes | Keep and validate. |
| Composition-preserve mode | No | Yes | Keep. |
| Source contrast/gamma | No, except auto-color contrast | Yes | Keep. |
| CLAHE/local equalization | No | Local luminance equalization | Keep, optionally test true CLAHE later. |
| Edge/detail target map | No | Yes | StringArtio stronger. |
| Background suppression | No | Yes | StringArtio stronger. |
| Foreground/subject focus | No | Yes, heuristic | Keep, rename generic parts where possible. |
| Circular mask | No | Yes | Keep. |
| RGB color scoring | Yes | JS sampled/palette color; native mono only | P2 native palette experiment if color output matters. |
| Auto foreground/background | Yes | Manual thread color options, sampled/palette internals | P1 auto-suggest board/thread colors. |
| Multi foreground colors | Yes | JS palette/sample support; app/native defaults mono | P2 native color v2, not default now. |
| Candidate generation | All pairs/colors | Current nail candidates plus global reseeds and path cache | Keep app path; add diagnostic full-pair mode offline. |
| Add/remove local search | Yes | Native refinement/pruning, JS less explicit | P1 bounded local-search experiment. |
| Beam search | No | No | Not recommended now. |
| Simulated annealing | No | No | Not recommended now. |
| Evolutionary search | No | Harness random/evolutionary-style actions | Keep in harness. |
| Bayesian optimization | No | Preference Lab constrained BO skeleton | Keep suggestion-only. |
| Parallelism | Rayon | Native Rayon; JS constrained | Keep native path. |
| Path cache | Minimal explicit | Yes | Keep; optimize memory if needed. |
| Score model | Squared RGB residual | Weighted residual, edge/detail/tone, penalties, SSIM harness, HPL | Add simple residual diagnostic, do not replace. |
| SSIM | No | Harness metric | Keep. |
| Edge similarity | No | Harness metric | Keep. |
| Line clump penalty | No | Harness metric | Keep. |
| Overdraw metric | No explicit output metric | Reconstruction summary | Keep. |
| Human preference learning | No | Yes | Major StringArtio advantage. |
| Review queue | No | Blind same-source queue | Major StringArtio advantage. |
| App-ready gates | No | Yes | Keep. |
| Runtime constraints | CLI max strings only | Runtime limit and app gates | Keep. |
| No target-aware constraint | Not applicable | Enforced in Preference Lab suggestions | Keep. |
| Tests | Rust unit tests | JS tests, Rust checks, Python tests | Add reference-style kernel invariants. |
| Docs | README examples | Extensive docs/runbooks | Keep current docs. |

## 9. Current Status And Remaining Opportunities

### Implemented In Preference Lab

- Rendered SVG diagnostics are extracted from existing output SVG artifacts and
  stored under `metadata.rendered_svg`.
- Rendered SVG diagnostics are exported to `features.csv` as
  `rendered_svg_*` columns.
- Config-level visible ink is exported as `derived_visible_ink_score`.
- Review queue risk scoring uses rendered SVG visibility diagnostics when they
  are available.
- Suggestion base scoring uses rendered SVG visibility risk and records rendered
  SVG provenance in suggestion output.
- Residual diagnostic fields such as `residualLumaScore`,
  `residualRgbScore`, `renderedResidualLumaScore`, and
  `renderedResidualRgbScore` are accepted and exported when present.
- Residual diagnostic fields are excluded from reward-model training by
  default.
- `better_visibility` is an allowed preference reason flag and maps to rendered
  SVG visibility, visible-ink, and contrast-related feature columns.
- Suggestions include `experiment_intent: "preference_tuning_suggestion"` plus
  supported handoff intents for
  `render_model_calibration`, `bounded_add_remove_local_search`, and
  `conservative_auto_color`.

### Still StringArtio-Owned Or Future Research

Reference-style score-delta tests remain useful for StringArtio JS/native
generator code:

- applying a line should update approximation/error exactly as predicted;
- removing or pruning a line should improve or preserve the chosen diagnostic
  score;
- opacity calibration should not make reconstruction metrics worse beyond a
  small tolerance;
- JS and native should agree on small synthetic fixtures.

StringArtio or its harness still owns producing any new residual, calibration,
local-search, or color-analysis artifacts. Preference Lab may ingest those
fields after they exist, but it must not execute generator runs or treat
diagnostics as human labels.

Useful future experiments:

- rasterize the exact preview/export SVG style and score that raster against the
  target map;
- run bounded add/remove local search in the harness after normal generation;
- use conservative source-color summaries as suggestion metadata;
- explore native palette or multi-color v2 only if color string art becomes a
  product goal;
- test non-circular pin arrangements only in harness research, not as app
  defaults.

## 10. Risks And Unsuitable Ideas

| Idea | Why It Looks Useful | Why It Is Risky / Unsuitable |
|---|---|---|
| Replace target-map pipeline with reference residual | Simpler, testable | Loses crop, saliency, background suppression, edge/detail/tone heuristics that StringArtio needs for portraits. |
| Full all-pairs scoring every app step | Better global search | Likely too expensive at 600-768 pins and 6000 lines; current candidate limits exist for a reason. |
| Use RGB residual as main score | Easy to reason about | Can optimize photo reconstruction rather than string-art legibility and human preference. |
| Adopt grid/random/perimeter app pins | More arrangements | App is a circular physical-board product; these could break craft feasibility and UI assumptions. |
| Auto-color as default | Nice examples in reference | May choose visually odd colors for portraits; current app/native path is mono-first. |
| GIF export in app | Reference supports it | Battery, memory, storage, and UX cost on mobile. Better as P3/export option. |
| Directly port reference code | Faster implementation | Violates goal and likely conflicts with architecture, native contracts, and licensing/review expectations. |
| Treat Preference Lab suggestions as executed results | Speeds tuning loop | Explicitly outside project constraints. Suggestions must be re-run and reviewed. |

## 11. Remaining Roadmap

This roadmap is intentionally scoped to work outside Preference Lab's completed
documentation and implementation updates.

### P0 - StringArtio Diagnostics And Tests

| Recommendation | Expected benefit | Owner |
|---|---|---|
| Add score-delta invariant tests for line apply/scoring in JS and Rust | Regression protection for generator changes | StringArtio |
| Emit simple residual diagnostic fields from the harness | Stable sanity-check lane for Lab ingestion | StringArtio |
| Emit same-run render/export raster calibration metrics | Better detection of preview/export mismatch | StringArtio |
| Surface native pruning/refinement/calibration metrics in review summaries | Easier clutter/faintness diagnosis | StringArtio |

### P1 - Harness Experiments

| Recommendation | Expected benefit | Owner |
|---|---|---|
| Bounded add/remove local-search experiment | Reduce clutter and overdraw in difficult outputs | StringArtio |
| Calibrate generator line ink against preview/export opacity and width | Improve app-upload visibility | StringArtio |
| Add conservative source-color summaries | Let Lab carry color suggestion metadata safely | StringArtio |
| Add JS fallback parity tests against native on small fixtures | Protect fallback quality | StringArtio |

### P2 - Product Or Research Options

| Recommendation | Expected benefit | Owner |
|---|---|---|
| Native palette/multi-color v2 experiment | Better colorful artwork if color becomes a product goal | StringArtio |
| Path-cache compression or two-stage global candidate prefilter | Performance headroom | StringArtio |
| True CLAHE or edge-preserving denoise experiment | Potential quality gains on difficult sources | StringArtio |
| Pin arrangement research in harness only | Research data without changing app defaults | StringArtio |

### P3 - Nice To Have

| Recommendation | Expected benefit | Owner |
|---|---|---|
| GIF/time-lapse export outside default app flow | Shareability | StringArtio |
| Reference-style CLI export/import adapter for experiments | Easier offline comparison | StringArtio |
| More compact algorithm trace JSON per generated pattern | Debugging and calibration context | StringArtio |

## Final Recommendation

Keep StringArtio's architecture. It is already the more scalable system for a production app and preference-driven tuning.

Borrow the reference project's engineering discipline, not its whole algorithm:

- make line scoring and line application provably consistent;
- keep residual metrics diagnostic-only;
- align generation metrics with what preview/export actually renders;
- use add/remove local search as a bounded harness experiment;
- use auto-color only as a conservative suggestion path.

The highest-return work is calibration and testing around the existing generator, not a rewrite.
