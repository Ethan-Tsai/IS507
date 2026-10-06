# IS 507 Alibaba GPU Trace: Raw Data Guide

## Project decision

We keep the official Parquet files as the single source of truth. We do **not**
create a second full processed copy because the pod-hourly data are large.
Cleaning, filtering, aliases, and feature creation are applied at query time in
R, Python, or DuckDB. Small derived tables may be created later only when they
answer a specific research question.

This approach is reproducible, avoids doubling disk usage, and preserves the
original observations.

## Local file layout

```text
MID/
  data/
    asi_opensource_pod_hourly_day0_29.parquet
    asi_opensource_job_execution_summary.parquet
  r_start.R
  data_pre_process.ipynb
```

Both analysis tables are single Parquet files. The merged pod file has physical
`day` and `hour` columns. `day=0` is the first relative day of the released
trace; it is not a calendar date. The data owner may retain the 720 original
hourly files locally, but the team workflow does not depend on them.

Official references:

- [Schema](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2026/docs/schema.md)
- [Download and directory layout](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2026/docs/data_download.md)

## Analysis grain

- `asi_opensource_pod_hourly`: one row for one pod observed on a GPU server
  during one hour. It includes pods whose `gpu_request` is zero.
- `asi_opensource_job_execution_summary`: one row for one pod/workload
  execution span. It already contains only GPU-requesting spans.

The same identifier may repeat because a pod can appear in multiple hours and
multiple pods can belong to one workload. Repeated IDs are therefore not, by
themselves, duplicate rows.

Do not directly join all raw pod-hour rows to all summary rows. That can create
a many-to-many expansion. For a combined analysis, aggregate both sources to a
declared grain (usually `workload_id`) before joining and report match coverage.

## Naming policy

Keep the official `snake_case` column names. This makes the code consistent
across R, Python, DuckDB, and the official documentation. Do not rename columns
only for appearance. Add a clearly named derived column when meaning or units
change, for example `schedule_delay_sec_clean`; never silently replace the raw
column.

## Pod-hourly fields

| Field | Type | Meaning and analysis note |
|---|---|---|
| `pod_id` | string | Stable anonymized pod ID. Repeats across hours. |
| `workload_id` | string | Stable anonymized workload ID when metadata is available; may be null. Multiple pods may share it. |
| `server_id` | string | Stable anonymized hosting-server ID. |
| `cluster_id` | string | Stable anonymized cluster ID. |
| `state_public` | string | `Standby`, `Running`, `Pending`, `Succeeded`, `Failed`, or `Unknown`. `Unknown` is a category, not an R `NA`. |
| `gpu_spec_public` | string | Normalized public GPU-model bucket. |
| `server_gpu_count` | integer | Number of GPUs on the hosting server. |
| `server_cpu_capacity_cores` | integer | Hosting server CPU capacity in cores. |
| `priority_class` | string | `HP`, `LP`, or `Other`. |
| `job_type_public` | string | `training`, `online_inference`, `offline_inference`, `dev`, `other`, or `unknown`. |
| `model_type_public` | string | `genai`, `rec`, `cv`, `embedding`, `dev`, or `unknown`. |
| `is_genai_request` | boolean | Whether the request matches the release's public GenAI-detection rule. |
| `gpu_request` | double | Requested GPU-equivalent count; `1.0` means one full GPU and fractions are allowed. Filter `> 0` for GPU-workload analyses. |
| `gpu_mem_request` | integer | Source-reported accelerator-memory request. The official schema does not declare a unit, so preserve it without conversion unless the team verifies the unit. |
| `cpu_request_cores` | double | Requested CPU cores. |
| `used_gpu_hours` | double | GPU-hours attributed to this pod-hour; one full GPU for one full hour is about `1.0`. |
| `avg_gpu_sm_util` | double | Source-reported average GPU SM utilization. Keep the raw value; do not automatically cap it at 100. |
| `avg_gpu_mem_gib` | double | Average GPU-memory use in GiB. |
| `avg_cpu_request_util` | double | Average CPU utilization normalized by requested CPU. |
| `avg_memory_util` | double | Average memory utilization. |
| `ready_status` | boolean | Whether the pod became ready according to source metadata. |
| `schedule_delay_sec` | integer | Scheduling delay in seconds when available. |
| `ready_delay_sec` | integer | Delay from scheduling to ready state in seconds when available. |
| `day` | partition integer | Relative day, inferred from the folder name by Arrow/DuckDB. |
| `hour` | partition integer | Hour 0 through 23, inferred from the folder name. |

## Job-execution-summary fields

| Field | Type | Meaning and analysis note |
|---|---|---|
| `pod_id` | string | Stable anonymized pod ID. |
| `workload_id` | string | Stable anonymized workload ID when metadata is available; may be null. |
| `server_id` | string | Stable anonymized server ID when available. |
| `gpu_spec_public` | string | Normalized public GPU-model bucket. |
| `priority_class` | string | `HP`, `LP`, or `Other`. |
| `job_type_public` | string | Public workload-type bucket. |
| `model_type_public` | string | Public model-type bucket. |
| `is_genai_request` | boolean | Whether the request matches the public GenAI-detection rule. |
| `gpu_request` | double | Requested GPU-equivalent count for the execution span. |
| `duration_hours` | double | Observed execution duration in hours. |
| `schedule_delay_sec` | integer | Scheduling delay in seconds when available. |
| `ready_delay_sec` | integer | Delay from scheduling to ready state in seconds when available. |
| `ready_status` | boolean | Whether the pod became ready according to source metadata. |
| `schedule_status` | boolean | Whether metadata indicates that the pod was scheduled. |

## Missing and exceptional-value policy

1. Preserve all raw files and raw columns unchanged.
2. Do not globally delete rows containing any `NA`; different columns are
   missing for different operational reasons.
3. Treat literal `Unknown`/`unknown` as documented categories, not missing
   values to be imputed.
4. Keep missing `workload_id` for single-table analyses. Exclude it only when a
   workload-level group or join specifically requires the ID.
5. Convert a negative delay to `NA` only in an explicitly named query-time
   column such as `schedule_delay_sec_clean`, while retaining the raw delay.
6. Do not mean-fill IDs, categories, outcomes, delays, duration, or utilization
   in the general preprocessing stage. If a model needs imputation, fit that
   rule on the training split only and record it with the model.
7. Do not automatically remove long durations, high utilization values, or
   fractional GPU requests. Flag and inspect them first because real cluster
   behavior can be extreme.
8. Before analysis, report missing counts/rates, numeric minima and maxima,
   category levels, row grain, and day/hour coverage.

## R usage

Open `MID` as the working directory and run [`r_start.R`](r_start.R). The key
idea is to keep Arrow queries lazy:

```r
# One hour
x <- read_pod(days = 5, hours = 12)

# One day, GPU-requesting rows only
x <- read_pod(days = 5, gpu_only = TRUE)

# Seven days, still lazy; filter/aggregate before collect()
x <- read_pod(days = 0:6, gpu_only = TRUE, collect_result = FALSE)

# Summary table, also lazy
summary_ds |>
  filter(job_type_public == "training") |>
  select(pod_id, workload_id, duration_hours) |>
  head(1000) |>
  collect()
```

Avoid `collect()` on all 30 pod days or the complete 40-million-row summary
unless the machine has enough memory. Select, filter, or aggregate first.
