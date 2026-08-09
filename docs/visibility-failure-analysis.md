# Visibility Failure Analysis

This note records why recent Preference Lab suggestions can score well while
still looking too faint to upload into the StringArtio app. It should be used
when a generated SVG is technically app-ready but visually hard to see.

## Recent Evidence

The clearest recent example is StringArtio run `20260628203605`, generated from
Preference Lab suggestions created at `2026-06-28T11:32:08Z`.

- The run completed successfully: 10/10 suggestions, 0 failures.
- The run summary still required human review:
  `action=artwork-review-required`.
- Summary scores were `artworkPrimary=0.65736`, `appReadyScore=0.481473`,
  and `pairFloor=0.443433`.
- The metric-best suggestion was `suggestion-70f19b868d55ea88`.
- That suggestion used `lineInk=0.0083`, `visualOpacityScale=0.45`,
  and `visualWidthScale=0.7`, for a visible-ink product of `0.0026145`.
- The previous optimizer floor was `0.0025`, so the metric-best suggestion was
  only barely above the old visibility floor. The current Preference Lab
  policy treats this region as too faint for optimizer anchors or upload-ready
  suggestions.

The exported SVG explains the visual result. For the metric-best `pair-1`
artifact, the rendered line opacity distribution was approximately:

- stroke opacity min/mean/max: `0.028 / 0.075 / 0.120`
- stroke width min/mean/max: `0.406 / 0.629 / 0.840`

That was enough to pass the old config-level visibility floor, but it is not
enough to read confidently in an app upload preview.

The heavier 6000-line variants were more visible, with representative `pair-1`
stroke opacity around `0.062 / 0.154 / 0.267` and stroke width around
`0.58 / 0.86 / 1.2`. Those are easier to see, but previous human review also
flagged the high-density direction as risky: later pairs were marked
`both_bad` for line clumping and messy output, and earlier pairs were described
as having somewhat improved face shape but still insufficient detail.

## Why It Keeps Happening

1. The old visibility floor was a rejection floor, not a quality target.
   `visualOpacityScale=0.45`, `visualWidthScale=0.7`, and the visible-ink
   product floor of `0.0025` prevented the worst invisible candidates, but they
   still allowed barely visible SVGs.

2. The model is optimizing preference and failure signals, not app-upload
   readability directly. After human labels penalized clumping and messy
   high-density outputs, the optimizer had a rational reason to retreat toward
   cleaner 4800-line bases. Those bases reduced clutter but also returned to
   very low rendered stroke opacity.

3. Config-level visible ink does not fully predict rendered SVG visibility.
   The final SVG renderer applies its own stroke-opacity and stroke-width
   mapping. A config can satisfy `lineInk * visualOpacityScale *
   visualWidthScale` while the exported lines still have a low average opacity.

4. More lines are not the same as better visibility. The 6000-line suggestions
   are darker, but they can trade the faintness problem for clumping,
   outline-heavy structure, and missing facial/detail information.

5. The metric summary is not a promotion decision. `artworkPrimary`,
   `pairFloor`, and `appReadyScore` are useful filters, but the runner still
   returned `artwork-review-required`. Human visual review remains the gate.

## Implemented Contract-Derived Policy

StringArtio now owns these thresholds in
`docs/string-art/generation-quality-contract.json`, and Preference Lab consumes
that contract when writing new suggestions. The optimizer separates the minimum
anchor floor from the app-upload target used when writing new suggestions.

Minimum floor for eligible optimizer anchors:

- `visualOpacityScale >= 0.60`
- `visualWidthScale >= 0.80`
- `lineInk >= 0.0085`
- `lineInk * visualOpacityScale * visualWidthScale >= 0.0040`

App-upload target for emitted suggestions:

- `visualOpacityScale >= 0.70`
- `visualWidthScale >= 0.90`
- `lineInk >= 0.0090`
- visible-ink product `>= 0.0055`

This means candidates around `visible_ink ~= 0.0025`, including the
`0.0026145` example above, no longer qualify as optimizer anchors. Suggestions
are raised above the floor instead of being allowed to sit on it.

The hard line-count limit remains `6000`, but the default suggestion policy
steers proposed `threadCount` and `finalLineCap` into a 5200 to 5800
moderate-density band. High-density 6000-line observations can still inform the
model, but new suggestions should not treat maxing out line count as the
default cure for faintness.

Suggestion files record the contract version/hash/source under
`constraints.generation_quality_contract`. If Preference Lab cannot read the
StringArtio contract, it keeps the fallback behavior but emits a warning; those
suggestions should be regenerated before being treated as contract-matched
handoff input.

## Recommended Review Checks

For the next suggestion cycle, prefer a visibility target above the current
floor instead of letting proposals sit on the floor:

- Treat `visible_ink ~= 0.0025` as too low for app-upload candidates.
- Use at least `visualOpacityScale >= 0.65` as a practical starting target.
- Use at least `visualWidthScale >= 0.85` as a practical starting target.
- Prefer `lineInk >= 0.0085`, and use the current `0.0090` suggestion target
  when preparing app-upload candidates.
- Keep target visible-ink product around `0.0045` to `0.006`, then
  validate by SVG/app preview rather than metrics alone.

Prefer moderate-density experiments over simply maxing out line count:

- Test line caps around `5200` to `5800` before defaulting to `6000`.
- Increase stroke visibility first, then add line count only if detail is still
  missing.
- Preserve a human review comparison against previous S5/S6 anchors, because
  darker output can still be worse if it becomes clumped or outline-only.

Add a rendered-output check when promoting or reviewing app candidates:

- Parse exported SVG stroke opacity and width statistics.
- Use the Preference Lab `metadata.rendered_svg` and
  `rendered_svg_*` feature columns when they are available.
- Reject app-upload candidates whose mean stroke opacity is near `0.075` or
  whose max stroke opacity is only around `0.12`.
- Prefer candidates with clearly higher rendered opacity, then verify they do
  not create clumping or lose face/detail structure.
- Record faintness as human preference evidence using `both_bad` or the
  relevant winner plus reason flags such as `better_visibility`,
  `better_contrast`, `less_blurry`, and `better_outline`.

## Do Not Do

- Do not promote the metric-best candidate when the app or blind preview is too
  faint to inspect.
- Do not treat the current visibility floor as the desired target; it is only a
  minimum rejection threshold.
- Do not lower `visualOpacityScale`, `visualWidthScale`, `lineInk`, or the
  visible-ink product floor to make more candidates eligible.
- Do not fix faintness by only raising `threadCount` or `finalLineCap` to
  `6000`; that can reintroduce line clumping, messy texture, and outline-only
  results.
- Do not use diagnostic comparison images as proof that an app-upload SVG is
  acceptable. The exported SVG and app preview are the artifacts that matter.
- Do not convert metric scores into human preference labels. If a candidate is
  too faint, record that through the preference workflow.
- Do not enable target-aware logic or automatic StringArtio generator execution
  from this repository to chase visibility improvements.
