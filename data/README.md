# Local data directory

Large raw Parquet files in this directory are intentionally ignored by Git.
Obtain them from the team's UIUC Box folder or run:

```powershell
python download_data.py
```

Expected full local structure:

```text
data/
  asi_opensource_pod_hourly/day=0/hour=00/part-000.parquet
  ...
  asi_opensource_pod_hourly/day=29/hour=23/part-000.parquet
  asi_opensource_job_execution_summary/part-000.parquet
```

Alternatively, teammates receiving the single merged file may use:

```text
data/
  asi_opensource_pod_hourly_day0_29.parquet
  asi_opensource_job_execution_summary/part-000.parquet
```

The merged pod file contains physical integer `day` and `hour` columns, and
`r_start.R` detects this layout automatically.

`samples/` contains small testing data and is tracked by Git. It must not be
used to make population-level conclusions.
