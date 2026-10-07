# Data profile

## Where the profile is produced

The complete profile is displayed directly in `data_pre_process.ipynb`. It is
not exported to CSV. This keeps schema, quality metrics, distributions, and
preprocessing decisions beside the code and exact run configuration that
created them.

The notebook produces:

- full-file inventory and pod day/hour coverage;
- field catalog with type, analytical role, measurement level, and description;
- missing, blank, negative, and repeated-key diagnostics;
- per-field null rate, minimum, maximum, and observed count;
- top categorical levels with count and proportion;
- numeric count, mean, standard deviation, quantiles, and range;
- numeric correlation matrices;
- job/model relationship summaries;
- KuLC association tables with support, bidirectional confidence, lift, and
  imbalance ratio;
- PCA explained variance and loading tables on bounded analysis samples;
- a preprocessing plan and pre-write validation table;
- post-write schema, row-count, and coverage validation.

## Profile scope

Expensive structural checks use the full files and Parquet metadata. Detailed
diagnostics default to pod Day 0 / Hour 0 and the first 1,000,000 execution
summary rows so the notebook remains interactive. Correlation and PCA use
bounded samples.

These bounded results are exploratory diagnostics, not 30-day population
estimates. Change the profile settings only when a broader scan is necessary
and sufficient time and storage are available.

## Interpretation rules

- A repeated `pod_id` is not automatically a duplicate because pod-hourly data
  repeat pods across time and the summary may contain execution spans.
- Missing GPU utilization can be structural when no GPU was requested.
- Negative delays are invalid as elapsed-time measurements but remain preserved
  in raw fields for auditability.
- Literal `Unknown` and `unknown` values are documented source categories.
- Highly skewed duration and usage measures should be summarized with medians
  and quantiles; transformations such as `log1p` belong to a specific model.
- PCA is exploratory, uses standardized numeric variables, and median-fills
  only its temporary sample matrix. It does not alter canonical data.

## Validated raw inventory

| Dataset | Rows | Row groups | Columns | Approximate size |
|---|---:|---:|---:|---:|
| Pod hourly, Day 0–29 | 842,390,418 | 844 | 25 | 33.48 GiB |
| Execution summary | 40,522,321 | 346 | 14 | 1.11 GiB |

The merged pod input covers relative days 0–29, hours 0–23, and all 720
day/hour combinations. Final processed counts depend on the selected workload
policy and are displayed by the notebook before and after materialization.
