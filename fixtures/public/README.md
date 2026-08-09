# Public reduced-evaluation fixture

This fixture is a deterministic, anonymized subset of real human review data.
It contains 9 preference records, 17 candidate feature rows, and 3 labeled
sources. Candidate, source, run, preference, and reviewer-field values were
replaced with sequential aliases; timestamps, notes, source hashes, and artifact
paths to private source/comparison files were removed.

Run the complete reduced evaluation from a clean checkout:

```bash
stringart-lab demo
```

The generated files are written to `examples/demo-output/`. The fixture includes
17 generated SVG outputs derived from the three open-license sources described
in [`portfolio/assets/ATTRIBUTION.md`](../../portfolio/assets/ATTRIBUTION.md).
It does not include the source photographs or diagnostic comparison images.

The three `reviewer-alias-*` values preserve distinct values that appeared in
the original `reviewer` field. They are not evidence of three independent human
reviewers. No candidate pair in this subset—or in the current private working
dataset—has overlapping ratings from two reviewer identifiers, so agreement is
reported as unavailable rather than invented.

This reduced fixture demonstrates ingestion-ready normalization, feature/model
inputs, blind-queue creation, constrained suggestions, and evaluation. It is not
the full private experiment dataset and does not meet the recommended threshold
of 10 labeled sources. See `fixture-manifest.json` for machine-readable
provenance and limitations.
