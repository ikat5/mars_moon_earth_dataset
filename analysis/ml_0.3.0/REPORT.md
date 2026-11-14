# ML 0.3.0 results (experimental, not promoted)

Implements plan WP2 to WP5 without labels. Code and reproduction steps are in [`ml/README.md`](../../ml/README.md). The full numbers are in `evaluation.json`, and the fixture top-10s are in `fixtures_top10.json`. The serving release stays **0.2.0**.

**This report contains no analog-relevance measurement.** There are no reviewed judgments, so NDCG and precision cannot be computed. The numbers below are data checks, agreement between methods, physical mismatch, diversity, bias probes and runtime. The promotion gate in plan section 7 cannot be evaluated yet.

## Data (WP2/WP3)

| Body | Valid patches | Train / val / test cells |
|---|---:|---|
| Earth (ETOPO 2022 15s) | 1,079,622 | 753,296 / 131,709 / 194,617 |
| Moon (LOLA LDEM_64) | 230,400 | 164,000 / 28,400 / 38,000 |
| Mars (MOLA MEGDR 128 ppd) | 921,600 | 617,600 / 161,600 / 142,400 |

Each patch is 32x32 samples at 500 m spacing (about 16 km) on a local tangent plane. Coverage is every eligible 0.2.0 cell with |lat| <= 80. Splits use 10x10-degree blocks hashed by SHA-256. Cells whose patch crosses a block edge are excluded from the SSL and evaluation samples.

**Independent correctness check.** Pearson correlation between patch values and the 0.2.0 table:

| Body | Mean elevation | Relief | Median slope | p90 slope | RMS roughness |
|---|---:|---:|---:|---:|---:|
| Earth | 1.000 | 0.982 | 0.993 | 0.992 | 0.984 |
| Moon | 0.999 | 0.940 | 0.969 | 0.969 | 0.936 |
| Mars | 1.000 | 0.977 | 0.985 | 0.985 | 0.973 |

Georeferencing and units agree with the table. The remaining differences come from the different window shape and slope baseline.

## Models (WP4/WP5)

- **B0:** the frozen four-term formula from `profiles.json`.
- **B1:** Wasserstein-1 distance over 19 quantiles of slope (tolerance 5 deg) and hypsometry (250 m), plus RMS roughness (100 m). Each term is capped at 1. The tolerances were declared before evaluation.
- **U1:** MiniBatchKMeans with k=32 on standardized B1 descriptors, fitted on the training split. 30 of the 32 clusters contain at least 5% of two or more bodies.
- **F1:** a frozen ImageNet ResNet18 on [z/500, slope, standardized z] at 64 px, reduced by PCA-128 fitted on the training split.
- **S1:** a small 7-conv CNN trained with SimCLR (NT-Xent, temperature 0.2, batch 512, 40 epochs) on 63,999 training-block patches, on a Kaggle T4. Seeds 0, 1 and 2 reached best validation top-1 of 0.506, 0.509 and 0.506. Seed 1 was selected.

**Held-out test-block view retrieval** (5,000 patches). An augmented view must retrieve its own clean patch. This is a sanity check, not relevance.

| Representation | top-1 | top-10 |
|---|---:|---:|
| S1 | 0.485 | 0.921 |
| B1 descriptors | 0.386 | 0.783 |
| F1 | 0.139 | 0.417 |

S1 by body: Earth 0.405 / 0.827, Mars 0.522 / 0.996, Moon 0.556 / 1.000.

## Retrieval comparison (Earth candidates, same area filter, 100 km thinning, top-10)

Queries: the 2 regression fixtures (Jezero, lunar 0N 0E), plus 100 Moon and 100 Mars targets from held-out test blocks.

| Scope | Method | Mean B0 fit | Mean B1 fit | \|Δrelief\| m | \|Δslope p50\| deg | Jaccard@100 vs B0 | U1 clusters in top-10 |
|---|---|---:|---:|---:|---:|---:|---:|
| Mars test | B0 | 97.8 | 88.5 | 11 | 0.11 | 1.00 | 3.0 |
| | B1 | 90.6 | 95.8 | 79 | 0.33 | 0.02 | 1.9 |
| | F1 | 77.2 | 80.2 | 171 | 0.88 | 0.00 | 4.8 |
| | S1 | 87.2 | 88.1 | 121 | 0.29 | 0.01 | 2.7 |
| Moon test | B0 | 90.1 | 68.3 | 199 | 0.43 | 1.00 | 3.9 |
| | B1 | 69.8 | 85.7 | 319 | 1.31 | 0.03 | 2.3 |
| | F1 | 52.1 | 55.5 | 400 | 2.68 | 0.01 | 5.1 |
| | S1 | 66.2 | 66.8 | 366 | 1.06 | 0.02 | 3.9 |
| Fixtures | B0 | 99.5 | 95.9 | 3 | 0.02 | 1.00 | 3.5 |
| | B1 | 97.4 | 99.0 | 28 | 0.08 | 0.02 | 1.5 |
| | F1 | 84.7 | 88.1 | 132 | 0.50 | 0.00 | 3.5 |
| | S1 | 97.3 | 96.8 | 26 | 0.04 | 0.01 | 2.5 |

The B0 and B1 columns favor their own method by construction. Read them as how physically consistent other methods' candidates are, not as accuracy.

## Domain bias and runtime

- **Body predictability** (logistic regression, train blocks to test blocks, chance 0.33): B1 0.66, F1 0.79, S1 0.84. The learned embeddings encode which body or instrument a patch came from more strongly than the physical descriptors do. This is a known risk for cross-body retrieval (plan section 7, "Domain bias").
- **Exact cosine search** over 1,079,622 Earth cells on CPU, single query: S1 (256-d, 1.1 GB float32) p50 0.029 s, p95 0.030 s. F1 (128-d, 0.55 GB) p50 0.017 s. This is well inside the 2 s p95 target, before loading and filtering.

## Conclusions

1. The harmonized patches are trustworthy enough to build on. B1 is the strongest label-free physical baseline: it agrees with B0 on mismatch magnitudes while comparing full distributions.
2. S1 learns stable terrain morphology and beats F1 and B1 on held-out view retrieval. Its candidates are physically closer than F1's on every scope. On Mars and the fixtures it stays near B1's physical consistency while returning different, more diverse candidates (Jaccard < 0.03).
3. S1 embeddings carry a strong body signature (0.84). Do not use S1 alone for cross-body ranking. Use it as an additional candidate pool fused with the physical method (plan section 6), and keep the physical fallback.
4. **Next step (WP3/WP6):** reviewers judge pooled B0, B1 and S1 candidates for the test queries using the plan section 8 rubric. Only then can NDCG decide promotion or supervised ranking (R1). F1 shows no advantage and can be dropped.

## Compute ledger

| Stage | Kaggle resource | Kernels |
|---|---|---:|
| Patches/descriptors | CPU, internet | 11 (+2 reruns on other accounts after DNS failures on two accounts) |
| SimCLR training (3 seeds) + F1 PCA | 1 session, NvidiaTeslaT4 shape (2xT4 allocated, 1 used) | 1 |
| Encoding | NvidiaTeslaT4 shape | 11 |

Artifacts live on Kaggle and in the git-ignored `ml_work/`. Their SHA-256 hashes are in `evaluation.json` under `artifacts_sha256`.
