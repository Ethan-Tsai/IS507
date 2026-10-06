# Data utilities

Run commands from the repository root.

| Script | Purpose |
|---|---|
| `download_data.py` | Download the execution summary and pod-hourly days 0–29. |
| `download_and_extract_pod_days.py` | Resumable selective pod-hourly downloader used by `download_data.py`. |
| `download_job_summary.py` | Resumable summary downloader used by `download_data.py`. |
| `merge_pod_hourly.py` | Merge 720 local hourly files into one raw pod input. |
| `package_team_data.py` | Validate and package exactly two canonical processed Parquet files. |

Typical build sequence:

```powershell
python scripts/download_data.py
python scripts/merge_pod_hourly.py
```

Then run `data_pre_process.ipynb`, confirm the preprocessing configuration, and
materialize both processed files. Finally run:

```powershell
python scripts/package_team_data.py
```

The archive is `data/IS507_processed_data.zip`. It preserves the
`data/processed/` paths and uses ZIP store mode because Parquet is already
compressed with ZSTD.
