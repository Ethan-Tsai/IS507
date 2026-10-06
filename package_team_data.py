"""Package the two team Parquet datasets into one ZIP without recompression."""

from __future__ import annotations

import time
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
POD_FILE = DATA_DIR / "asi_opensource_pod_hourly_day0_29.parquet"
SUMMARY_FILE = DATA_DIR / "asi_opensource_job_execution_summary.parquet"
OUTPUT_ZIP = DATA_DIR / "IS507_alibaba_gpu_data_day0_29.zip"
TEMP_ZIP = OUTPUT_ZIP.with_suffix(".zip.part")


def log(message: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def zip_is_complete() -> bool:
    if not OUTPUT_ZIP.exists():
        return False
    expected = {
        f"data/{path.name}": path.stat().st_size
        for path in (POD_FILE, SUMMARY_FILE)
    }
    try:
        with zipfile.ZipFile(OUTPUT_ZIP) as archive:
            observed = {item.filename: item.file_size for item in archive.infolist()}
            return observed == expected and archive.testzip() is None
    except (OSError, zipfile.BadZipFile):
        return False


def main() -> None:
    for path in (POD_FILE, SUMMARY_FILE):
        if not path.exists():
            raise FileNotFoundError(path)

    if zip_is_complete():
        log(f"Archive already complete: {OUTPUT_ZIP}")
        return

    TEMP_ZIP.unlink(missing_ok=True)
    total_gib = sum(path.stat().st_size for path in (POD_FILE, SUMMARY_FILE)) / 1024**3
    log(f"Packaging two Parquet files ({total_gib:.2f} GiB) with ZIP store mode")

    with zipfile.ZipFile(
        TEMP_ZIP,
        mode="w",
        compression=zipfile.ZIP_STORED,
        allowZip64=True,
    ) as archive:
        for path in (POD_FILE, SUMMARY_FILE):
            log(f"Adding {path.name}")
            archive.write(path, arcname=f"data/{path.name}")

    TEMP_ZIP.replace(OUTPUT_ZIP)
    if not zip_is_complete():
        raise RuntimeError("ZIP validation failed")
    log(f"Complete: {OUTPUT_ZIP} ({OUTPUT_ZIP.stat().st_size / 1024**3:.2f} GiB)")


if __name__ == "__main__":
    main()
