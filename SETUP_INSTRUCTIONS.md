# IS 507 setup instructions

## 1. Data setup

### Download and extract

1. Download or clone the GitHub repository and open its root folder.
2. Use the UIUC Box link in [README.md](README.md) to download `IS507_processed_data.zip`.
3. Move the ZIP into the repository root; do not rename the files inside it.
4. Extract the ZIP into the repository root so the included `data/processed/` folders are preserved.
5. Confirm that these exact paths exist:

```text
data/processed/asi_opensource_pod_hourly_processed.parquet
data/processed/asi_opensource_job_execution_summary_processed.parquet
```

Windows PowerShell can perform steps 4–5:

```powershell
Expand-Archive -Path .\IS507_processed_data.zip -DestinationPath . -Force
Test-Path .\data\processed\asi_opensource_pod_hourly_processed.parquet
Test-Path .\data\processed\asi_opensource_job_execution_summary_processed.parquet
```

Both `Test-Path` commands should return `True`.

### What the data contains

| File | Rows | Grain | Main use |
|---|---:|---|---|
| `asi_opensource_pod_hourly_processed.parquet` | 842,390,418 | One pod-server observation in one relative day/hour, covering days 0–29 and all 720 day-hour combinations | Hourly resource requests, observed utilization, workload state, and readiness |
| `asi_opensource_job_execution_summary_processed.parquet` | 40,522,321 | One execution span | Duration, scheduling/readiness outcomes, job/model categories, and GPU request |

`day` is relative to the trace start rather than a calendar date, and the two tables have different grains; aggregate each table before joining them.

### Cleaning and analysis fields

Original columns remain in both files, and cleaning is stored in additional columns so every transformation is traceable.

| Source field or group | Processed analysis field | Rule |
|---|---|---|
| `workload_id` | `workload_id_clean`, `workload_id_processed`, `workload_id_missing` | Trim whitespace and convert blanks to missing; retain missing IDs and add an explicit indicator; no rows were dropped |
| `schedule_delay_sec` | `schedule_delay_sec_clean` | Convert negative sentinel values to missing; preserve the raw field |
| `ready_delay_sec` | `ready_delay_sec_clean` | Convert negative sentinel values to missing; preserve the raw field |
| `duration_hours` | `duration_hours_clean` | Convert invalid negative values to missing; retain valid extreme durations |
| `state_public` | `state_public_clean` | Replace null or blank labels with `Unknown` |
| `gpu_spec_public`, `priority_class` | Corresponding `*_clean` fields | Replace null or blank labels with `Unknown` |
| `job_type_public`, `model_type_public` | Corresponding `*_clean` fields | Replace null or blank labels with `unknown` |
| `gpu_request` | `is_gpu_request` in the pod table | Flag observations requesting more than zero GPUs |
| GPU utilization fields | `gpu_utilization_observed` in the pod table | Retain structural missing values and flag whether utilization was observed |
| Outcomes and numeric extremes | Original and clean fields as applicable | Do not apply global mean imputation, clipping, or silent row deletion |

Use the `*_clean` fields for analysis, `workload_id_processed` for the configured workload identifier, and the missingness flags when missing values are analytically relevant.

## 2. R setup

Open `IS507.Rproj` in RStudio, or set the working directory to the repository root, then run the single setup script; the first run uses the internet to install missing packages into the project-local `.r-library/` folder and may take several minutes:

```r
setwd("PATH/TO/IS507")
source("r_setup.R")
```

The script verifies both Parquet files, prints the field guide and row counts, reads small analysis samples, and displays a job-type check plot without loading the complete pod table into memory. It creates the objects `pod`, `summary`, `field_guide`, `dataset_check`, `pod_sample`, `summary_sample`, and `job_type_plot`; use the same `source("r_setup.R")` command at the beginning of later sessions.

Example analysis:

```r
# One pod-hour in memory.
pod_hour <- read_pod(days = 5, hours = 12)

# A lazy summary query; collect only the small result.
duration_by_job <- summary |>
  group_by(job_type_public_clean) |>
  summarise(
    executions = n(),
    median_hours = median(duration_hours_clean, na.rm = TRUE),
    .groups = "drop"
  ) |>
  collect()
```

Do not run `collect(pod)` or `collect(summary)` directly; filter, select, sample, or aggregate first.
