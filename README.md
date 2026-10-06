# IS 507 Project: Alibaba GPU Cluster Trace

This repository contains a reproducible preprocessing and analysis workflow for
the Alibaba Cluster Trace GPU v2026 dataset. The study scope is the first 30
relative days (`day = 0` through `day = 29`) of pod-hourly observations and the
complete job-execution summary.

## Canonical analysis files

All downstream Python, R, and DuckDB analyses use exactly two processed files:

```text
data/processed/
  asi_opensource_pod_hourly_processed.parquet
  asi_opensource_job_execution_summary_processed.parquet
```

The processed files contain the original fields plus documented cleaning and
indicator fields. Raw files remain immutable inputs and are not the downstream
analysis interface.

## Reproduce the data

1. Place the two raw single-file Parquet datasets under `data/`:

   ```text
   data/asi_opensource_pod_hourly_day0_29.parquet
   data/asi_opensource_job_execution_summary.parquet
   ```

2. Open `data_pre_process.ipynb` and run it from the first cell.
3. Review the in-notebook integrity, profile, relationship, and PCA tables.
4. Confirm the preprocessing settings, set `WRITE_PROCESSED_FILES = True`,
   and rerun the materialization and validation sections.
5. Create the distribution archive:

   ```powershell
   python scripts/package_team_data.py
   ```

The result is `data/IS507_processed_data.zip`. It contains only the two files
under `data/processed/` and can be extracted directly into the repository root.
Parquet already uses ZSTD compression, so the ZIP intentionally uses store
mode to avoid slow and ineffective recompression.

## Analysis entry points

- `data_pre_process.ipynb`: integrity checks, missingness, field profiles,
  distributions, relationships, PCA, preprocessing, and final materialization.
- `r_start.R`: simple Arrow/dplyr access to the two canonical files.
- `docs/PREPROCESSING.md`: canonical rules and configuration decisions.
- `docs/DATA_README.md`: data layout, grain, fields, and usage notes.
- `docs/DATA_PROFILE.md`: profile scope and interpretation guidance.
- `scripts/`: raw-data acquisition, merge, and processed-data packaging tools.

## Python setup

Python 3.11 or newer is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## R setup

```r
install.packages(c("arrow", "dplyr"))
source("r_start.R")
```

After sourcing the file, `pod` and `summary` are lazy Arrow datasets. No
preprocessing policy needs to be repeated in R.

Official references:

- [Dataset download](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2026/docs/data_download.md)
- [Dataset schema](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2026/docs/schema.md)

## Important limitations

- `day` is relative to the trace start, not a calendar date.
- Missing `workload_id` values are common, especially in the execution summary.
- Negative delay values are retained in raw fields and converted to missing only
  in explicitly named `*_clean` fields.
- Literal `Unknown` and `unknown` are source categories, not null values.
- Aggregate each table to a declared grain before joining; joining both tables
  at raw row level can create a many-to-many expansion.
