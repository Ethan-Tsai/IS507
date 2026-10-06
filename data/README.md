# Local data directory

Large raw Parquet files in this directory are intentionally ignored by Git.
Obtain them from the team's UIUC Box folder or run:

```powershell
python scripts/download_data.py
```

Expected team analysis layout:

```text
data/
  asi_opensource_pod_hourly_day0_29.parquet
  asi_opensource_job_execution_summary.parquet
```

The merged pod file contains physical integer `day` and `hour` columns. The
data owner may also retain `asi_opensource_pod_hourly/` as a local backup, but
the shared notebook and R starter do not use that directory.

`samples/` contains small testing data and is tracked by Git. It must not be
used to make population-level conclusions.
