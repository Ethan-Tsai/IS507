"""Create a cleaned pod-hourly Parquet without modifying the merged source.

Default policy:
- drop workload_id;
- retain all rows unless a core analysis field is null;
- preserve nulls in optional utilization and delay fields.

Use --strict-complete-case only when the analysis truly requires every
retained field to be non-null. It may remove a large share of observations.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import duckdb
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DEFAULT_INPUT = DATA_DIR / "asi_opensource_pod_hourly_day0_29.parquet"
DEFAULT_OUTPUT = DATA_DIR / "asi_opensource_pod_hourly_day0_29_clean.parquet"
TEMP_DIR = DATA_DIR / ".duckdb_tmp"

DEFAULT_DROP_COLUMNS = ["workload_id"]
CORE_REQUIRED_COLUMNS = [
    "pod_id",
    "server_id",
    "cluster_id",
    "day",
    "hour",
    "gpu_request",
    "used_gpu_hours",
]


def log(message: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--gpu-only",
        action="store_true",
        help="Keep only rows with a positive, non-null gpu_request.",
    )
    parser.add_argument(
        "--strict-complete-case",
        action="store_true",
        help="Drop any row containing NULL in any retained column.",
    )
    parser.add_argument(
        "--keep-workload-id",
        action="store_true",
        help="Retain workload_id instead of dropping it.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing cleaned output.",
    )
    return parser.parse_args()


def schema_names(path: Path) -> list[str]:
    return pq.ParquetFile(path).schema_arrow.names


def metadata_null_counts(path: Path) -> dict[str, int] | None:
    parquet = pq.ParquetFile(path)
    names = parquet.schema_arrow.names
    totals = {name: 0 for name in names}

    for row_group_index in range(parquet.metadata.num_row_groups):
        row_group = parquet.metadata.row_group(row_group_index)
        for column_index, name in enumerate(names):
            statistics = row_group.column(column_index).statistics
            if statistics is None or statistics.null_count is None:
                return None
            totals[name] += statistics.null_count
    return totals


def main() -> None:
    args = parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    temporary_path = output_path.with_name(output_path.stem + ".part.parquet")

    if not input_path.exists():
        raise FileNotFoundError(
            f"Merged input not found: {input_path}\n"
            "Run `python merge_pod_hourly.py` first."
        )
    if input_path == output_path:
        raise ValueError("Input and output must be different; raw data are not overwritten.")
    if output_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}\n"
            "Use --overwrite only if replacement is intentional."
        )

    input_columns = schema_names(input_path)
    drop_columns = [] if args.keep_workload_id else DEFAULT_DROP_COLUMNS
    missing_drop_columns = sorted(set(drop_columns) - set(input_columns))
    if missing_drop_columns:
        raise RuntimeError(f"Columns requested for removal are absent: {missing_drop_columns}")

    retained_columns = [name for name in input_columns if name not in drop_columns]
    missing_core = sorted(set(CORE_REQUIRED_COLUMNS) - set(retained_columns))
    if missing_core:
        raise RuntimeError(f"Required core columns are absent: {missing_core}")

    filters = [f"{quote_identifier(name)} IS NOT NULL" for name in CORE_REQUIRED_COLUMNS]
    if args.gpu_only:
        filters.append("gpu_request > 0")
    if args.strict_complete_case:
        filters = [f"{quote_identifier(name)} IS NOT NULL" for name in retained_columns]
        if args.gpu_only:
            filters.append("gpu_request > 0")

    select_sql = ",\n                ".join(
        quote_identifier(name) for name in retained_columns
    )
    where_sql = " AND\n                ".join(filters)

    input_rows = pq.ParquetFile(input_path).metadata.num_rows
    input_gib = input_path.stat().st_size / 1024**3
    log(f"Input: {input_rows:,} rows, {input_gib:.2f} GiB")
    log(f"Dropping columns: {drop_columns or 'none'}")
    log(
        "Policy: "
        + ("strict complete case" if args.strict_complete_case else "core fields required")
        + (", GPU requests only" if args.gpu_only else ", all GPU-request values")
    )

    temporary_path.unlink(missing_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("SET threads=8")
    con.execute("SET memory_limit='8GB'")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET temp_directory='{TEMP_DIR.as_posix()}'")
    con.execute("PRAGMA enable_progress_bar")
    con.execute("PRAGMA progress_bar_time=2000")

    log("Writing cleaned ZSTD-compressed Parquet")
    con.execute(
        f"""
        COPY (
            SELECT
                {select_sql}
            FROM read_parquet('{input_path.as_posix()}')
            WHERE
                {where_sql}
        ) TO '{temporary_path.as_posix()}' (
            FORMAT PARQUET,
            COMPRESSION ZSTD,
            ROW_GROUP_SIZE 1000000
        )
        """
    )
    con.close()

    output_metadata = pq.ParquetFile(temporary_path).metadata
    output_rows = output_metadata.num_rows
    if output_rows > input_rows:
        raise RuntimeError("Cleaned output has more rows than its input")
    if schema_names(temporary_path) != retained_columns:
        raise RuntimeError("Cleaned output schema does not match the selected columns")

    if args.strict_complete_case:
        null_counts = metadata_null_counts(temporary_path)
        if null_counts is None:
            check = duckdb.connect().execute(
                "SELECT count(*) FROM read_parquet(?) WHERE "
                + " OR ".join(
                    f"{quote_identifier(name)} IS NULL" for name in retained_columns
                ),
                [temporary_path.as_posix()],
            ).fetchone()[0]
            if check != 0:
                raise RuntimeError(f"Strict output still contains {check:,} rows with NULL")
        elif any(null_counts.values()):
            raise RuntimeError(
                "Strict output still contains NULL values: "
                + str({key: value for key, value in null_counts.items() if value})
            )

    if output_path.exists():
        output_path.unlink()
    temporary_path.replace(output_path)

    output_gib = output_path.stat().st_size / 1024**3
    removed_rows = input_rows - output_rows
    removed_rate = removed_rows / input_rows if input_rows else 0
    log(
        f"Complete: {output_rows:,} rows retained; {removed_rows:,} removed "
        f"({removed_rate:.2%}); {output_gib:.2f} GiB"
    )
    log(f"Output: {output_path}")


if __name__ == "__main__":
    main()

