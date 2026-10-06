# Data Profile

## Scope

The notebook performs two different levels of validation:

- **Full-file integrity:** both complete Parquet files are checked using file
  metadata and the full pod `day`/`hour` coverage.
- **Quick diagnostic profile:** pod Day 0 / Hour 0 and the first 1,000,000
  execution-summary rows are profiled for missingness, distributions, and
  preprocessing decisions.

The quick profile is designed for a fast, reproducible classroom workflow. Its
percentages describe the selected scope and must not be presented as complete
30-day population estimates.

## Full-file integrity

| Dataset | Size (GiB) | Rows | Row groups | Columns |
|---|---:|---:|---:|---:|
| Pod hourly, Day 0–29 | 33.476 | 842,390,418 | 844 | 25 |
| Execution summary | 1.107 | 40,522,321 | 346 | 14 |

The merged pod file covers all 30 relative days, all 24 hours, and all 720
day/hour combinations. The integrity assertions passed.

## Quick-profile quality findings

### Pod hourly: Day 0 / Hour 0

- 1,179,029 rows and 1,179,028 distinct pods.
- `workload_id` is missing in 23.21% of rows; no blank strings were found.
- `avg_gpu_sm_util` is missing in 94.21% of all rows. This is expected to be
  strongly affected by the many rows with zero GPU request.
- Scheduling delay is missing in 2.07% and negative in only 0.0013%.
- Ready delay is missing in 2.07% and negative in 28.41%.
- `state_public` is `Unknown` for all rows in this hour, so this field is not
  informative in the quick pod scope.

### Execution summary: first 1,000,000 rows

- Approximately 99% of rows have distinct pod IDs.
- `workload_id` is missing in about 88%; no blank strings were found.
- `duration_hours` is complete and has no negative values.
- Scheduling delay is missing in about 0.96% and negative in about 0.59%.
- Ready delay is missing in about 0.96% and negative in about 55.5%.

## Numeric-distribution highlights

The summary duration distribution is strongly right-skewed:

- Median: about 0.43 hours (26 minutes)
- 75th percentile: about 1.50 hours
- 99th percentile: about 72.8 hours
- Maximum: about 1,824 hours (76 days)

Use medians, quantiles, or `log1p(duration_hours)` rather than relying only on
the mean.

For the pod quick profile, raw `avg_gpu_sm_util` reaches values above 100 and
raw GPU-memory values can also be very large. These values are retained because
they may represent multi-GPU aggregation or source-specific measurement rules.
They must not be silently capped without confirming the field definition.

## Categorical-distribution highlights

In the pod quick profile, `priority_class = Other` accounts for about 77%, while
about 92.6% of `job_type_public` and 92.8% of `model_type_public` values are
`unknown`. Only about 3.1% are marked as GenAI requests.

In the summary quick profile, about 82.5% are low priority, 79.3% are offline
inference jobs, and 77.5% are marked as GenAI requests. These large differences
reflect different table grains and possibly file-order effects in the bounded
summary profile; they are diagnostic findings, not evidence of a population
difference between the two tables.

## Current preprocessing policy

| Field or issue | Rule |
|---|---|
| `workload_id` | Trim blank strings to `NULL`; preserve missing values; do not impute. |
| Negative scheduling delay | Preserve raw value and create `schedule_delay_sec_clean`. |
| Negative ready delay | Preserve raw value and create `ready_delay_sec_clean`. |
| `Unknown` categories | Preserve as documented source categories. |
| Numeric extremes | Retain and profile before applying a research-specific rule. |
| Missing rows | Do not globally drop rows containing any missing value. |

`workload_id` coverage is approximately 76.8% in the pod quick profile but only
about 12% in the summary quick profile. Therefore, workload-level joins select
a limited subset of the summary data. Any combined analysis must report match
coverage and should aggregate both sources to a declared grain before joining.

## Generated tables

Running `data_pre_process.ipynb` creates the following small files under
`reports/data_profile/`:

- `file_inventory.csv`
- `quality_report.csv`
- `workload_id_coverage.csv`
- `column_profile.csv`
- `numeric_distribution.csv`
- `categorical_distribution.csv`

These files document the profile only. They do not contain the full raw data.
