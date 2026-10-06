# IS 507 project: R starter code for the raw Alibaba GPU trace
#
# Recommended workflow:
#   1. Open the MID folder as the RStudio/VS Code working directory.
#   2. Run this file section by section.
#   3. Keep queries lazy and call collect() only after filtering/selecting.

# Install once if needed:
# install.packages(c("arrow", "dplyr"))

library(arrow)
library(dplyr)

# Locate MID whether R was started from MID or its parent IS507 folder.
project_root <- normalizePath(".", winslash = "/", mustWork = TRUE)
if (!dir.exists(file.path(project_root, "data")) &&
    dir.exists(file.path(project_root, "MID", "data"))) {
  project_root <- file.path(project_root, "MID")
}

data_dir <- file.path(project_root, "data")
pod_merged_file <- file.path(
  data_dir,
  "asi_opensource_pod_hourly_day0_29.parquet"
)
summary_file <- file.path(data_dir, "asi_opensource_job_execution_summary.parquet")

stopifnot(file.exists(pod_merged_file))
stopifnot(file.exists(summary_file))

# open_dataset() is lazy: it reads metadata now, not all rows into RAM.
# The team workflow always uses the two shared single-file Parquet datasets.
# The 720 hourly source files may remain on the data owner's machine, but this
# script never depends on them.
pod_ds <- open_dataset(pod_merged_file, format = "parquet")
summary_ds <- open_dataset(summary_file, format = "parquet")

message("Pod source: ", pod_merged_file)
message("Summary source: ", summary_file)
print(pod_ds$schema)
print(summary_ds$schema)

# Read selected pod partitions. Keep collect_result = FALSE for a lazy query.
read_pod <- function(days,
                     hours = NULL,
                     gpu_only = FALSE,
                     columns = NULL,
                     collect_result = TRUE) {
  stopifnot(length(days) >= 1, all(days >= 0), all(days <= 29))

  query <- pod_ds |>
    filter(day %in% as.integer(days))

  if (!is.null(hours)) {
    stopifnot(all(hours >= 0), all(hours <= 23))
    query <- query |>
      filter(hour %in% as.integer(hours))
  }

  if (gpu_only) {
    query <- query |>
      filter(!is.na(gpu_request), gpu_request > 0)
  }

  if (!is.null(columns)) {
    # day and hour remain available even when a short column list is requested.
    query <- query |>
      select(any_of(unique(c(columns, "day", "hour"))))
  }

  if (collect_result) collect(query) else query
}

# Examples -----------------------------------------------------------------

# One hour only (smallest useful unit).
pod_day5_hour12 <- read_pod(days = 5, hours = 12)

# One whole day, GPU-requesting rows only, selected columns only.
pod_day5_gpu <- read_pod(
  days = 5,
  gpu_only = TRUE,
  columns = c(
    "pod_id", "workload_id", "gpu_spec_public", "priority_class",
    "job_type_public", "gpu_request", "used_gpu_hours",
    "avg_gpu_sm_util", "ready_status", "schedule_delay_sec",
    "ready_delay_sec"
  )
)

# Several days as a lazy query. This does not load all rows yet.
pod_week_lazy <- read_pod(
  days = 0:6,
  gpu_only = TRUE,
  collect_result = FALSE
)

# Aggregate first, then collect only the small result.
daily_gpu_summary <- pod_week_lazy |>
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

# Summary table: also keep it lazy, because it has about 40 million rows.
summary_overview <- summary_ds |>
  summarise(
    rows = n(),
    unique_pods = n_distinct(pod_id),
    mean_duration_hours = mean(duration_hours, na.rm = TRUE)
  ) |>
  collect()

print(summary_overview)

summary_ready_counts <- summary_ds |>
  count(ready_status) |>
  collect()

print(summary_ready_counts)

# Example filtered summary data. Collect only after filtering/selecting.
summary_training <- summary_ds |>
  filter(job_type_public == "training", gpu_request > 0) |>
  select(
    pod_id, workload_id, gpu_spec_public, priority_class,
    model_type_public, gpu_request, duration_hours,
    schedule_delay_sec, ready_delay_sec, ready_status, schedule_status
  ) |>
  head(10000) |>
  collect()

# Query-time cleaning -------------------------------------------------------
# Do not overwrite raw files. These rules are examples to apply only when the
# analysis needs them. Missing values stay missing unless a model later needs
# an explicitly documented imputation strategy.
pod_day5_analysis <- pod_day5_gpu |>
  mutate(
    schedule_delay_sec_clean = if_else(
      !is.na(schedule_delay_sec) & schedule_delay_sec >= 0,
      schedule_delay_sec,
      NA_integer_
    ),
    ready_delay_sec_clean = if_else(
      !is.na(ready_delay_sec) & ready_delay_sec >= 0,
      ready_delay_sec,
      NA_integer_
    )
  )

# Optional DuckDB example --------------------------------------------------
# DuckDB is useful for SQL users and still reads Parquet without importing all
# rows. Install once with: install.packages(c("DBI", "duckdb"))
#
# library(DBI)
# library(duckdb)
# con <- dbConnect(duckdb())
# pod_glob <- file.path(pod_dir, "day=*", "hour=*", "part-000.parquet")
# pod_glob <- normalizePath(pod_glob, winslash = "/", mustWork = FALSE)
# sql <- sprintf(
#   paste(
#     "SELECT day, hour, COUNT(*) AS rows,",
#     "SUM(gpu_request) AS requested_gpu_hours",
#     "FROM read_parquet('%s', hive_partitioning = true)",
#     "WHERE day = 5 AND gpu_request > 0",
#     "GROUP BY day, hour ORDER BY hour"
#   ),
#   pod_glob
# )
# day5_by_hour <- dbGetQuery(con, sql)
# dbDisconnect(con, shutdown = TRUE)
