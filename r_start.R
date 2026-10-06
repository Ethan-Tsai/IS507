# IS 507 project: R starter for the canonical processed datasets
#
# Run data_pre_process.ipynb first and distribute its two final Parquet files.
# This script never reads the raw files and never repeats preprocessing rules.

# Install once if needed:
# install.packages(c("arrow", "dplyr"))

library(arrow)
library(dplyr)

# Locate MID whether R starts in MID or its parent IS507 directory.
project_root <- normalizePath(".", winslash = "/", mustWork = TRUE)
if (!dir.exists(file.path(project_root, "data", "processed")) &&
    dir.exists(file.path(project_root, "MID", "data", "processed"))) {
  project_root <- file.path(project_root, "MID")
}

processed_dir <- file.path(project_root, "data", "processed")
pod_file <- file.path(
  processed_dir,
  "asi_opensource_pod_hourly_processed.parquet"
)
summary_file <- file.path(
  processed_dir,
  "asi_opensource_job_execution_summary_processed.parquet"
)

if (!file.exists(pod_file) || !file.exists(summary_file)) {
  stop(
    "Canonical processed files are missing. Extract the shared ZIP into ",
    "the repository root, or run data_pre_process.ipynb first."
  )
}

# These are the two canonical analysis objects. Opening them is lazy and fast;
# Arrow reads rows only when a query is collected.
pod <- open_dataset(pod_file, format = "parquet")
summary <- open_dataset(summary_file, format = "parquet")

message("Pod dataset: ", pod_file)
message("Summary dataset: ", summary_file)
print(pod$schema)
print(summary$schema)

# Optional convenience readers. Preprocessing is already embedded in the
# Parquet files, so these functions only select a manageable analysis slice.
read_pod <- function(days = NULL,
                     hours = NULL,
                     gpu_only = FALSE,
                     columns = NULL,
                     row_limit = NULL,
                     collect_result = TRUE) {
  query <- pod

  if (!is.null(days)) {
    stopifnot(all(days >= 0), all(days <= 29))
    query <- query |> filter(day %in% as.integer(days))
  }
  if (!is.null(hours)) {
    stopifnot(all(hours >= 0), all(hours <= 23))
    query <- query |> filter(hour %in% as.integer(hours))
  }
  if (gpu_only) {
    query <- query |> filter(is_gpu_request)
  }
  if (!is.null(columns)) {
    query <- query |> select(any_of(columns))
  }
  if (!is.null(row_limit)) {
    query <- query |> head(as.integer(row_limit))
  }

  if (collect_result) collect(query) else query
}

read_summary <- function(columns = NULL,
                         row_limit = NULL,
                         collect_result = FALSE) {
  query <- summary
  if (!is.null(columns)) {
    query <- query |> select(any_of(columns))
  }
  if (!is.null(row_limit)) {
    query <- query |> head(as.integer(row_limit))
  }
  if (collect_result) collect(query) else query
}

# Examples -----------------------------------------------------------------

# Read one hour into memory, similar to read.csv() but already preprocessed.
pod_day5_hour12 <- read_pod(days = 5, hours = 12)

# Select only the fields needed for an analysis.
pod_day5_gpu <- read_pod(
  days = 5,
  gpu_only = TRUE,
  columns = c(
    "pod_id", "workload_id_processed", "gpu_spec_public_clean",
    "priority_class_clean", "job_type_public_clean", "gpu_request",
    "used_gpu_hours", "avg_gpu_sm_util", "schedule_delay_sec_clean",
    "ready_delay_sec_clean", "day", "hour"
  ),
  row_limit = 10000
)

# Keep a larger query lazy, aggregate first, and collect only the small result.
daily_gpu_summary <- read_pod(
  days = 0:29,
  gpu_only = TRUE,
  collect_result = FALSE
) |>
  group_by(day) |>
  summarise(
    rows = n(),
    unique_pods = n_distinct(pod_id),
    requested_gpu_hours = sum(gpu_request, na.rm = TRUE),
    used_gpu_hours = sum(used_gpu_hours, na.rm = TRUE),
    .groups = "drop"
  ) |>
  collect()

print(daily_gpu_summary)

# The summary object is also ready for direct dplyr use.
summary_overview <- summary |>
  summarise(
    rows = n(),
    unique_pods = n_distinct(pod_id),
    mean_duration_hours = mean(duration_hours_clean, na.rm = TRUE)
  ) |>
  collect()

print(summary_overview)

summary_training <- summary |>
  filter(job_type_public_clean == "training", gpu_request > 0) |>
  select(
    pod_id, workload_id_processed, gpu_spec_public_clean,
    priority_class_clean, model_type_public_clean, gpu_request,
    duration_hours_clean, schedule_delay_sec_clean,
    ready_delay_sec_clean, ready_status, schedule_status
  ) |>
  head(10000) |>
  collect()

# Optional DuckDB example --------------------------------------------------
# install.packages(c("DBI", "duckdb"))
# library(DBI)
# library(duckdb)
# con <- dbConnect(duckdb())
# pod_sql_path <- normalizePath(pod_file, winslash = "/", mustWork = TRUE)
# day5_by_hour <- dbGetQuery(
#   con,
#   sprintf(
#     paste(
#       "SELECT day, hour, COUNT(*) AS rows,",
#       "SUM(gpu_request) AS requested_gpu_hours",
#       "FROM read_parquet('%s')",
#       "WHERE day = 5 AND is_gpu_request",
#       "GROUP BY day, hour ORDER BY hour"
#     ),
#     pod_sql_path
#   )
# )
# dbDisconnect(con, shutdown = TRUE)
