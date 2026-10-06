# Preprocessing workflow

## Design decision

The two shared Parquet files remain the immutable source of truth. The project
does not create a second full processed copy because the merged pod table is
about 33.48 GiB. Cleaning rules are applied through DuckDB views in Python or
lazy Arrow queries in R.

This means a policy can be changed tomorrow without downloading, merging, or
copying the large data again.

## Standard fields

The notebook creates analysis views with these additional fields:

| Field | Meaning |
|---|---|
| `workload_id_clean` | Original workload ID after converting blank strings to missing. |
| `workload_id_status` | `observed` or `missing`. |
| `workload_id_was_missing` | Boolean indicator retained even when a placeholder is used. |
| `workload_id_analysis` | Workload ID after applying the selected policy. |
| `schedule_delay_sec_clean` | Scheduling delay when non-negative; otherwise missing. |
| `ready_delay_sec_clean` | Ready delay when non-negative; otherwise missing. |
| `is_gpu_request` | Whether `gpu_request > 0`. |

## Workload-ID policies

Set `WORKLOAD_ID_POLICY` in `data_pre_process.ipynb`, or pass
`workload_policy` to the R reader.

| Policy | Result | Recommended use |
|---|---|---|
| `keep` | Missing IDs remain missing. | Default single-table analysis. |
| `zero` | Missing IDs become string `"0"` in the analysis field. | Models requiring a visible missing category. |
| `drop` | Rows missing a workload ID are excluded from the current query only. | Workload-level aggregation or joins. |
| `ordinal` | Observed IDs receive positive integer codes; missing IDs receive `0`. | Models requiring numeric identifiers. |

Neither `zero` nor `ordinal` means that missing records belong to one real
workload. Always retain `workload_id_was_missing` and avoid treating ordinal
codes as continuous quantities.

The ordinal option requires a shared lookup file. In the notebook run:

```python
build_workload_id_lookup()
create_preprocessed_views("ordinal")
```

This creates only a small mapping file at
`data/workload_id_lookup.parquet`; it does not create another full dataset.

## R examples

```r
# Keep missing workload IDs (default)
x <- read_pod(days = 5, hours = 12, workload_policy = "keep")

# Use an explicit missing category
x <- read_pod(days = 5, hours = 12, workload_policy = "zero")

# Exclude missing IDs from this query only
x <- read_pod(days = 5, hours = 12, workload_policy = "drop")

# Summary sample with the same policy interface
s <- read_summary(
  row_limit = 10000,
  workload_policy = "keep",
  collect_result = TRUE
)
```

For `ordinal`, first generate the lookup in the notebook. R intentionally
requires `collect_result = TRUE` for this option so teammates do not
accidentally trigger an unbounded full-table join.

## Joining the two datasets

Do not join raw pod-hour rows directly to raw execution-summary rows. First
choose a grain, aggregate each table independently, and then join the two small
results. Report:

- rows and unique workloads before filtering;
- rows and unique workloads after requiring an ID;
- matched workloads after the join;
- the selected workload-ID policy.
