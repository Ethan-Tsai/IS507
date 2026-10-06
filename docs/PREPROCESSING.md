# Canonical preprocessing workflow

## Objective

`data_pre_process.ipynb` is the single source of preprocessing logic. One run
creates two canonical Parquet files that already contain the selected policy,
clean fields, and indicators. Downstream R or DuckDB code reads those files
directly and does not repeat the preprocessing rules.

The raw files are never overwritten.

## Configuration decisions

The notebook exposes these settings near the top:

| Setting | Default | Meaning |
|---|---|---|
| `WORKLOAD_ID_POLICY` | `"keep"` | Preserve missing IDs in `workload_id_processed`. |
| `CATEGORICAL_NULL_POLICY` | `"unknown"` | Replace null/blank categorical values only in `*_clean` fields. |
| `WRITE_PROCESSED_FILES` | `False` | Dry run until all diagnostic results are reviewed. |
| `OVERWRITE_PROCESSED_FILES` | `False` | Protect an existing canonical output from accidental replacement. |

Allowed workload-ID policies are:

| Policy | Canonical result | Appropriate use |
|---|---|---|
| `keep` | Missing remains missing. | Recommended default; preserves information. |
| `zero` | Missing becomes string `"0"`. | Algorithms that require an explicit missing category. |
| `drop` | Rows without an ID are excluded from both processed outputs. | Only when every planned analysis requires a workload ID. |
| `ordinal` | Known IDs become positive integer codes and missing becomes `0`. | Algorithms requiring numeric identifiers; codes are nominal, not continuous. |

`drop` can remove a large share of execution-summary rows, so it should be
selected only after reviewing the notebook's coverage table. `zero` and
`ordinal` do not imply that all missing records belong to one real workload;
the `workload_id_missing` indicator must remain available.

## Canonical transformations

All original fields are retained unless the selected `drop` policy removes
rows. The notebook adds:

| Field | Rule |
|---|---|
| `workload_id_clean` | Trim whitespace; convert blank strings to null. |
| `workload_id_missing` | Boolean indicator based on the cleaned ID. |
| `workload_id_processed` | Final ID according to `WORKLOAD_ID_POLICY`. |
| `schedule_delay_sec_clean` | Retain non-negative values; negative values become null. |
| `ready_delay_sec_clean` | Retain non-negative values; negative values become null. |
| `duration_hours_clean` | Summary only; retain non-negative values. |
| categorical `*_clean` fields | Preserve source labels; replace only null/blank values with a documented label. |
| `is_gpu_request` | Pod only; whether `gpu_request > 0`. |
| `gpu_utilization_observed` | Pod only; whether SM utilization is present. |

General preprocessing does not mean-fill durations, delays, utilization,
outcomes, identifiers, or categories. Model-specific imputation should be fit
inside the training split to avoid leakage. Large real-world values are
profiled and retained rather than silently clipped.

## Materialization and validation

After reviewing the notebook output:

1. Set `WORKLOAD_ID_POLICY` to the final decision.
2. If using `ordinal`, run `build_workload_lookup()` once.
3. Set `WRITE_PROCESSED_FILES = True`.
4. Keep `OVERWRITE_PROCESSED_FILES = False` for the first run.
5. Run the materialization and post-write validation sections.

The notebook writes temporary `.part.parquet` files and renames them only after
DuckDB completes the write. It then reopens the outputs and verifies metadata,
row counts, and all 720 pod day/hour combinations.

To intentionally replace an earlier processed version, first confirm the new
policy and then set `OVERWRITE_PROCESSED_FILES = True`. The two outputs remain
the only canonical downstream datasets.

## Joining the datasets

Do not join raw pod-hour rows directly to execution-summary rows. Choose a
grain, aggregate both canonical datasets independently (usually by
`workload_id_processed`), and then join the aggregate tables. Report ID
coverage and join match coverage with every combined analysis.
