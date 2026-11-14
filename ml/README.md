# TerraTwin ML experiments (ml_0.3.0, experimental)

Implements the label-free part of `analysis/ML_MASTER_PLAN.md`: WP2 terrain patches, WP3 spatial splits, and WP4/WP5 baselines (B0, B1, U1, F1, S1). R1/R2 (supervised ranking) is **not** implemented: there are no reviewed relevance labels yet. The serving release stays `0.2.0`, and nothing here changes the API.

| File | Role |
|---|---|
| `patches.py` | 32x32 metric DEM patches at 500 m spacing (~16 km) around every eligible 0.2.0 cell with \|lat\| <= 80. Sources: ETOPO 2022 15s, MOLA MEGDR 128 ppd, LOLA LDEM_64. Also computes B1 descriptors (19 slope and hypsometry quantiles, relief, detrended RMS) and assigns immutable 10x10-degree block splits (70/15/15 by SHA-256). |
| `models.py` | S1: a small CNN trained with SimCLR (3 seeds, best chosen on the validation split). F1: a frozen ImageNet ResNet18 reduced by PCA-128 fitted on the training split. |
| `kaggle_jobs.py` | Runs the stages across Kaggle accounts using tokens in `~/.kaggle/<name>_token`. |
| `evaluate.py` | Local CPU comparison. Writes `analysis/ml_0.3.0/`. |

## Reproduce

```bash
python -m ml.kaggle_jobs patches                         # 11 CPU kernels (8 Earth bands, 2 Mars, 1 Moon)
python -m ml.kaggle_jobs fetch patches 'desc_|sample_'
python -m ml.kaggle_jobs train                           # GPU kernel on the main account
python -m ml.kaggle_jobs fetch train
python -m ml.kaggle_jobs encode                          # 11 GPU kernels, each encodes its own patch shard
python -m ml.kaggle_jobs fetch encode 'emb_'
python -m ml.evaluate
python -m pytest ml -q
```

Large artifacts (patches, embeddings, checkpoints) stay on Kaggle and in the git-ignored `ml_work/`. `analysis/ml_0.3.0/evaluation.json` records their SHA-256 hashes.

## Limits

- Augmentations assume terrain shape does not depend on orientation, which is wrong for aspect, illumination and other directional processes.
- Polar terrain (\|lat\| > 80) is excluded; it needs a polar projection.
- The evaluation reports how well methods agree, physical mismatch, diversity, domain-bias probes and runtime. None of these measure analog relevance.
- Cosine similarity is not a probability. Do not present any score here as confidence or suitability.

Results: [analysis/ml_0.3.0/REPORT.md](../analysis/ml_0.3.0/REPORT.md).
