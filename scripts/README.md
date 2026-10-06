# Data utilities

Run these commands from the repository root.

| Script | Purpose |
|---|---|
| `download_data.py` | Download the execution summary and pod-hourly days 0–29. |
| `download_and_extract_pod_days.py` | Resumable selective pod-hourly downloader used by `download_data.py`. |
| `download_job_summary.py` | Resumable execution-summary downloader used by `download_data.py`. |
| `merge_pod_hourly.py` | Merge the 720 local hourly files into the team pod Parquet. |
| `package_team_data.py` | Package the two team Parquet files into one store-mode ZIP. |

Typical commands:

```powershell
python scripts/download_data.py
python scripts/merge_pod_hourly.py
python scripts/package_team_data.py
```

The analysis entry points remain at the repository root:
`data_pre_process.ipynb` for Python/DuckDB and `r_start.R` for R/Arrow.
