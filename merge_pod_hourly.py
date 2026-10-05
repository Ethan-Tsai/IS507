"""Merge pod-hourly day 0..29 into one Parquet file for file sharing."""

from __future__ import annotations

import time
from pathlib import Path

import duckdb
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
INPUT_ROOT = DATA_DIR / "asi_opensource_pod_hourly"
INPUT_GLOB = (INPUT_ROOT / "day=*" / "hour=*" / "part-000.parquet").as_posix()
OUTPUT_PATH = DATA_DIR / "asi_opensource_pod_hourly_day0_29.parquet"
TEMP_PATH = DATA_DIR / "asi_opensource_pod_hourly_day0_29.part.parquet"
TEMP_DIR = DATA_DIR / ".duckdb_tmp"


def log(message: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def input_inventory() -> tuple[list[Path], int]:
    files = sorted(INPUT_ROOT.glob("day=*/hour=*/part-000.parquet"))
    if len(files) != 720:
        raise RuntimeError(f"Expected 720 hourly Parquet files, found {len(files)}")

    expected = {
        (day, hour)
        for day in range(30)
        for hour in range(24)
    }
    observed = {
        (
            int(path.parents[1].name.split("=")[1]),
            int(path.parent.name.split("=")[1]),
        )
        for path in files
    }
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise RuntimeError(f"Partition mismatch. Missing={missing}; extra={extra}")

    total_rows = sum(pq.ParquetFile(path).metadata.num_rows for path in files)
    return files, total_rows


def output_looks_complete(expected_rows: int) -> bool:
    if not OUTPUT_PATH.exists():
        return False
    try:
        metadata = pq.ParquetFile(OUTPUT_PATH).metadata
        return metadata.num_rows == expected_rows
    except (OSError, ValueError):
        return False


def main() -> None:
    files, expected_rows = input_inventory()
    input_gib = sum(path.stat().st_size for path in files) / 1024**3
    log(
        f"Validated {len(files)} partitions with {expected_rows:,} rows "
        f"({input_gib:.2f} GiB input)"
    )

    if output_looks_complete(expected_rows):
        log(f"Merged output already exists and has {expected_rows:,} rows; skipping")
        return

    TEMP_PATH.unlink(missing_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("SET threads=8")
    con.execute("SET memory_limit='8GB'")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET temp_directory='{TEMP_DIR.as_posix()}'")
    con.execute("PRAGMA enable_progress_bar")
    con.execute("PRAGMA progress_bar_time=2000")

    log("Merging into one ZSTD-compressed Parquet file")
    con.execute(
        f"""
        COPY (
            SELECT
                * EXCLUDE (day, hour),
                CAST(day AS SMALLINT) AS day,
                CAST(hour AS TINYINT) AS hour
            FROM read_parquet(
                '{INPUT_GLOB}',
                hive_partitioning=true,
                union_by_name=true
            )
        ) TO '{TEMP_PATH.as_posix()}' (
            FORMAT PARQUET,
            COMPRESSION ZSTD,
            ROW_GROUP_SIZE 1000000
        )
        """
    )
    con.close()

    output_rows = pq.ParquetFile(TEMP_PATH).metadata.num_rows
    if output_rows != expected_rows:
        raise RuntimeError(
            f"Row-count mismatch: input={expected_rows:,}, output={output_rows:,}"
        )

    TEMP_PATH.replace(OUTPUT_PATH)
    output_gib = OUTPUT_PATH.stat().st_size / 1024**3

    check = duckdb.connect().execute(
        """
        SELECT
            min(day) AS min_day,
            max(day) AS max_day,
            min(hour) AS min_hour,
            max(hour) AS max_hour,
            count(DISTINCT day) AS days,
            count(DISTINCT hour) AS hours
        FROM read_parquet(?)
        """,
        [OUTPUT_PATH.as_posix()],
    ).fetchone()
    if check != (0, 29, 0, 23, 30, 24):
        raise RuntimeError(f"Unexpected day/hour coverage in merged output: {check}")

    log(
        f"Complete: {OUTPUT_PATH} | {output_rows:,} rows | "
        f"{output_gib:.2f} GiB | day 0-29 | hour 0-23"
    )


if __name__ == "__main__":
    main()

