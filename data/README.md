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

`samples/` contains small testing data and is tracked by Git. It must not be
used to make population-level conclusions.

