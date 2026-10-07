# Alibaba GPU trace data guide

## Canonical file layout

```text
MID/
  data/
    asi_opensource_pod_hourly_day0_29.parquet
    asi_opensource_job_execution_summary.parquet
    processed/
      asi_opensource_pod_hourly_processed.parquet
      asi_opensource_job_execution_summary_processed.parquet
  data_pre_process.ipynb
  r_setup.R
```

The two files directly under `data/` are immutable preprocessing inputs. The
two files under `data/processed/` are the only analysis inputs for R, DuckDB,
and subsequent notebooks. The 720 original hourly files may remain as a local
rebuild source but are not required downstream.

## Table grain

- `pod_hourly`: one pod observation on a server during one relative day/hour.
  A pod may appear in multiple hours. The merged file contains physical `day`
  and `hour` columns.
- `execution_summary`: one pod/workload execution span. It contains
  GPU-requesting execution records and is not at the same grain as pod-hourly.

`day = 0` is the first released trace day, not a calendar date.

## Field groups

The notebook displays the authoritative field catalog with DuckDB type,
analytical role, measurement level, and description. The main groups are:

| Group | Representative fields | Notes |
|---|---|---|
| Identifiers | `pod_id`, `workload_id`, `server_id`, `cluster_id` | Nominal identifiers; never treat ordinal encodings as quantities. |
| Workload categories | `priority_class`, `job_type_public`, `model_type_public`, `is_genai_request` | Source `Unknown`/`unknown` labels are meaningful categories. |
| Requested resources | `gpu_request`, `gpu_mem_request`, `cpu_request_cores` | Fractional GPU requests are valid. |
| Observed usage | `used_gpu_hours`, `avg_gpu_sm_util`, `avg_gpu_mem_gib`, CPU/memory utilization | Missingness can reflect workload structure. |
| Outcomes | `ready_status`, `schedule_status`, scheduling and ready delays | Use `*_clean` delay fields for elapsed-time analysis. |
| Time and duration | `day`, `hour`, `duration_hours` | Summary duration is strongly right-skewed. |

Canonical processed fields are documented in `PREPROCESSING.md` and are added
without silently replacing the corresponding raw fields.

## R usage

Extract `IS507_processed_data.zip` into the repository root and run:

```r
source("r_setup.R")
```

This creates two lazy Arrow datasets:

```r
pod
summary
```

They can be queried like dplyr tables:

```r
one_hour <- pod |>
  filter(day == 5, hour == 12) |>
  collect()

duration_by_type <- summary |>
  group_by(job_type_public_clean) |>
  summarise(
    rows = n(),
    median_hours = median(duration_hours_clean, na.rm = TRUE)
  ) |>
  collect()
```

Opening a Parquet dataset is fast because Arrow reads metadata first. Avoid
collecting all 842 million pod rows into memory; filter, select, or aggregate
before `collect()`.

## Safe analysis rules

- Use `workload_id_processed` for the decided ID policy and retain
  `workload_id_missing` when missingness matters.
- Use the named `*_clean` fields for delays, duration, and categories.
- Do not globally drop every row containing a null value.
- Do not silently cap numeric extremes.
- Aggregate both tables to the intended grain before joining and report match
  coverage.

Official references:

- [Schema](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2026/docs/schema.md)
- [Download layout](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2026/docs/data_download.md)
