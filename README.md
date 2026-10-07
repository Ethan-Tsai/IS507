# IS 507 — Alibaba GPU Cluster Analysis

This repository contains the final preprocessing workflow and the R entry points for two processed Alibaba GPU cluster datasets.

## Quick start

1. **Get the code:** on GitHub, select **Code → Download ZIP**, extract it, and open the repository folder; Git users may clone the repository instead.
2. **Get the data:** download `IS507_processed_data.zip` from [UIUC Box](ADD_UIUC_BOX_LINK_HERE), move it into the repository root, and extract it there so the two files appear under `data/processed/`.
3. **Start R:** open `IS507.Rproj` or set R to the repository root, then run `source("r_setup.R")`; the script installs missing packages, validates both files, and creates the lazy `pod` and `summary` datasets.

Use [SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md) for the exact commands and cleaning rules, and begin every R session with the same `source("r_setup.R")` command; filter or aggregate before calling `collect()`.

## Data at a glance

| R object | Rows and grain | Recommended fields |
|---|---|---|
| `pod` | 842,390,418 pod-server-hour observations across days 0–29 | `day`, `hour`, `gpu_request`, `used_gpu_hours`, utilization fields, `ready_status`, `*_clean` categories and delays |
| `summary` | 40,522,321 execution spans | `duration_hours_clean`, `gpu_request`, `ready_status`, `schedule_status`, `*_clean` categories and delays |

Use `workload_id_processed` for workload identity and the `*_clean` fields for analysis; because the datasets have different grains, aggregate them before joining.

## Main files

| File | Purpose |
|---|---|
| [SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md) | Data placement, contents, cleaning table, and R setup |
| [r_setup.R](r_setup.R) | The single R entry point: package setup, validation, lazy loading, reader functions, samples, and a check plot |
| [data_pre_process.ipynb](data_pre_process.ipynb) | Reproducible profiling, preprocessing, and final Parquet generation |
| `docs/` | Detailed technical documentation |
| `scripts/` | Download, merge, and packaging utilities |
