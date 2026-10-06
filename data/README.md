# Local data directory

Large Parquet and ZIP files are intentionally ignored by Git.

Raw preprocessing inputs:

```text
data/
  asi_opensource_pod_hourly_day0_29.parquet
  asi_opensource_job_execution_summary.parquet
```

Canonical analysis outputs created by `data_pre_process.ipynb`:

```text
data/processed/
  asi_opensource_pod_hourly_processed.parquet
  asi_opensource_job_execution_summary_processed.parquet
```

Only the two processed files are used by `r_start.R` and downstream analyses.
Run `python scripts/package_team_data.py` after materialization to create
`data/IS507_processed_data.zip`.

The tracked `samples/` files are for fast code tests only and must not be used
for population-level conclusions.
