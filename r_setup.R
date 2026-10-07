# IS 507: single R entry point.
# Run from the repository root after extracting IS507_processed_data.zip.

# Locate the project using base R before loading any packages.
project_root <- normalizePath(".", winslash = "/", mustWork = TRUE)
if (!file.exists(file.path(project_root, "r_setup.R")) &&
    file.exists(file.path(project_root, "MID", "r_setup.R"))) {
  project_root <- file.path(project_root, "MID")
}

# Keep packages inside the project so installation never needs admin access.
local_library <- file.path(project_root, ".r-library")
dir.create(local_library, recursive = TRUE, showWarnings = FALSE)
.libPaths(c(local_library, .libPaths()))

# Install required packages automatically on the first run.
required_packages <- c(
  "R6", "rlang", "cli", "lifecycle", "tzdb",
  "arrow", "dplyr", "ggplot2"
)
missing_packages <- required_packages[
  !vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)
]
if (length(missing_packages) > 0) {
  message("Installing missing packages: ", paste(missing_packages, collapse = ", "))
  install.packages(missing_packages, repos = "https://cloud.r-project.org")
}

still_missing <- required_packages[
  !vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)
]
if (length(still_missing) > 0) {
  stop(
    "Package installation did not complete: ",
    paste(still_missing, collapse = ", "),
    ". Check the internet connection and rerun r_setup.R."
  )
}

library(arrow)
library(dplyr)
library(ggplot2)

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
    "Processed Parquet files are missing under data/processed/. ",
    "Extract IS507_processed_data.zip into the repository root and rerun."
  )
}

# Canonical lazy datasets: no full data is loaded here.
pod <- open_dataset(pod_file, format = "parquet")
summary <- open_dataset(summary_file, format = "parquet")

# Compact field reference; run print(field_guide) at any time.
field_guide <- data.frame(
  dataset = c(
    "pod", "pod", "pod", "pod", "pod",
    "summary", "summary", "summary"
  ),
  group = c(
    "IDs and time", "Workload", "Resource request", "Resource usage",
    "Outcomes", "IDs and workload", "Resources and duration", "Outcomes"
  ),
  fields = c(
    paste(c(
      "pod_id", "workload_id_processed", "server_id", "cluster_id",
      "day", "hour"
    ), collapse = ", "),
    paste(c(
      "state_public_clean", "gpu_spec_public_clean", "priority_class_clean",
      "job_type_public_clean", "model_type_public_clean", "is_genai_request"
    ), collapse = ", "),
    paste(c(
      "gpu_request", "gpu_mem_request", "cpu_request_cores",
      "server_gpu_count", "server_cpu_capacity_cores"
    ), collapse = ", "),
    paste(c(
      "used_gpu_hours", "avg_gpu_sm_util", "avg_gpu_mem_gib",
      "avg_cpu_request_util", "avg_memory_util"
    ), collapse = ", "),
    paste(c(
      "ready_status", "schedule_delay_sec_clean", "ready_delay_sec_clean",
      "is_gpu_request", "gpu_utilization_observed"
    ), collapse = ", "),
    paste(c(
      "pod_id", "workload_id_processed", "gpu_spec_public_clean",
      "priority_class_clean", "job_type_public_clean",
      "model_type_public_clean", "is_genai_request"
    ), collapse = ", "),
    "gpu_request, duration_hours_clean",
    paste(c(
      "ready_status", "schedule_status", "schedule_delay_sec_clean",
      "ready_delay_sec_clean"
    ), collapse = ", ")
  ),
  stringsAsFactors = FALSE
)

# Read a manageable pod slice into memory, or return a lazy query.
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

# Filter the execution summary by common analysis dimensions.
read_summary <- function(job_types = NULL,
                         model_types = NULL,
                         ready = NULL,
                         gpu_only = FALSE,
                         columns = NULL,
                         row_limit = NULL,
                         collect_result = FALSE) {
  query <- summary

  if (!is.null(job_types)) {
    query <- query |> filter(job_type_public_clean %in% job_types)
  }
  if (!is.null(model_types)) {
    query <- query |> filter(model_type_public_clean %in% model_types)
  }
  if (!is.null(ready)) {
    query <- query |> filter(ready_status == ready)
  }
  if (gpu_only) {
    query <- query |> filter(gpu_request > 0)
  }
  if (!is.null(columns)) {
    query <- query |> select(any_of(columns))
  }
  if (!is.null(row_limit)) {
    query <- query |> head(as.integer(row_limit))
  }

  if (collect_result) collect(query) else query
}

# Validate row counts directly from Parquet metadata without scanning rows.
pod_rows <- arrow::ParquetFileReader$create(pod_file)$num_rows
summary_rows <- arrow::ParquetFileReader$create(summary_file)$num_rows

dataset_check <- data.frame(
  dataset = c("pod_hourly", "execution_summary"),
  expected_rows = c(842390418, 40522321),
  observed_rows = c(pod_rows, summary_rows)
)
dataset_check$valid <- dataset_check$expected_rows == dataset_check$observed_rows
stopifnot(all(dataset_check$valid))

# Small samples for checking fields and starting analysis code.
pod_sample <- read_pod(
  days = 0,
  hours = 0,
  columns = c(
    "pod_id", "workload_id_processed", "workload_id_missing",
    "gpu_spec_public_clean", "priority_class_clean",
    "job_type_public_clean", "model_type_public_clean",
    "gpu_request", "used_gpu_hours", "avg_gpu_sm_util",
    "schedule_delay_sec_clean", "ready_delay_sec_clean",
    "ready_status", "is_gpu_request", "gpu_utilization_observed",
    "day", "hour"
  ),
  row_limit = 50000,
  collect_result = TRUE
)

summary_sample <- read_summary(
  columns = c(
    "pod_id", "workload_id_processed", "workload_id_missing",
    "gpu_spec_public_clean", "priority_class_clean",
    "job_type_public_clean", "model_type_public_clean",
    "is_genai_request", "gpu_request", "duration_hours_clean",
    "schedule_delay_sec_clean", "ready_delay_sec_clean",
    "ready_status", "schedule_status"
  ),
  row_limit = 100000,
  collect_result = TRUE
)

# Quick visual check only; this first-row sample is not a population estimate.
job_type_counts <- summary_sample |>
  count(job_type_public_clean, sort = TRUE)

job_type_plot <- ggplot(
  job_type_counts,
  aes(x = reorder(job_type_public_clean, n), y = n)
) +
  geom_col(fill = "#2C7FB8") +
  coord_flip() +
  labs(
    title = "Job types in the setup sample",
    subtitle = "First 100,000 execution-summary rows; setup check only",
    x = "Clean job type",
    y = "Rows"
  ) +
  theme_minimal(base_size = 12)

print(field_guide, row.names = FALSE)
print(dataset_check, row.names = FALSE)
if (interactive()) {
  print(job_type_plot)
}
message(
  "Setup complete: `pod`, `summary`, helper functions, samples, and plot are ready."
)
