# Glossary

> Stable project terminology. Consistent definitions reduce misunderstanding across AI sessions and agents.
> Add new terms when they become stable. Do not rewrite existing definitions without a good reason.

---

**HPL (Human Preference Learning):** The process of collecting pairwise human judgments between candidates and training a preference model from those labels. In this project, HPL covers steps 1–7 of the pipeline.

**Candidate:** A single StringArtio rendering of one source image using one experiment config. Identified by `candidate_id`. Multiple candidates can share the same `run_id` (same config, different source images).

**Source ID (`source_id`):** The identifier for the source image used in a rendering. Pairwise comparisons must share the same `source_id` so the reviewer is comparing the same content rendered differently.

**Preference label:** A human judgment recorded in `preferences.jsonl`. Allowed values: `A` (candidate A is better), `B` (candidate B is better), `tie` (candidates are similar enough that the difference is negligible), `both_bad` (neither candidate is acceptable).

**Reward model / Preference model:** A trained model that predicts which of two candidates a human would prefer. The baseline is a Bradley-Terry-style pairwise logistic ranking model trained on feature differences.

**Blind review:** A review session where the reviewer sees only the rendering artifacts — no config values, metrics, or provenance — before making a preference judgment. Diagnostic artifacts are revealed only after the blind choice is recorded.

**Both-bad:** A preference outcome where neither candidate in a pair meets acceptable quality. Recorded as a failure signal; not treated as an A-vs-B winner by the model.

**Tie:** A preference outcome where two candidates are similar enough that no meaningful preference exists. Treated as a weak equality loss by the model, not as evidence that either candidate is good.

**Reason flag:** An optional annotation on a preference label indicating which visual quality dimension drove the judgment (e.g., `less_clumping`, `better_contrast`, `better_visibility`). Used by the model as lower-weight auxiliary training signal.

**Constraint:** A hard requirement that optimization suggestions must satisfy. Defined by the StringArtio generation-quality contract. Includes `app_ready == true`, runtime limit, line-count limit, visibility floors, and prohibition of target-aware logic.

**Generation-quality contract:** A JSON file owned by StringArtio that defines the constraint set for valid experiment configs. The lab reads this file during `ingest` and `suggest` to apply up-to-date constraints without hardcoding them.

**BO (Bayesian Optimization):** The optimization strategy used by the `suggest` step. Explores the config space by balancing predicted preference score with uncertainty, constrained to the app-ready, visibility-safe region.

**Sidecar:** This repository's role. It reads StringArtio artifacts and writes research outputs alongside them without modifying the app or running generator experiments.

**Pipeline step:** One of the seven owned steps: `ingest`, `features`, `queue`, `validate-preferences`, `train-model`, `suggest`, and the `validate-config` setup command.

**Fallback model:** A preference model emitted when human labels are missing or insufficient. Reports clearly that it is a fallback. Real HPL begins after `preferences.jsonl` contains human pairwise labels.

**Rendered SVG diagnostics:** Stroke opacity, stroke width, and line count extracted from output SVG artifacts by the `ingest` step. Used as visual risk signals in queue generation and optimizer base selection. Not a human preference label.

**Visible-ink score:** A derived metric combining `lineInk`, `visualOpacityScale`, and `visualWidthScale`. Used as a proxy for how visible the thread rendering will appear in the app or export. Not a human preference label.
