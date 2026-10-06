"""Package exactly two canonical processed Parquet files into one ZIP."""

from __future__ import annotations

import time
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
POD_FILE = PROCESSED_DIR / "asi_opensource_pod_hourly_processed.parquet"
SUMMARY_FILE = PROCESSED_DIR / "asi_opensource_job_execution_summary_processed.parquet"
OUTPUT_ZIP = ROOT / "data" / "IS507_processed_data.zip"
TEMP_ZIP = OUTPUT_ZIP.with_suffix(".zip.part")
PACKAGE_FILES = (POD_FILE, SUMMARY_FILE)


def log(message: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def expected_members() -> dict[str, int]:
    return {
        path.relative_to(ROOT).as_posix(): path.stat().st_size
        for path in PACKAGE_FILES
    }


def zip_is_complete() -> bool:
    if not OUTPUT_ZIP.exists():
        return False
    try:
        with zipfile.ZipFile(OUTPUT_ZIP) as archive:
            observed = {item.filename: item.file_size for item in archive.infolist()}
            return observed == expected_members() and archive.testzip() is None
    except (OSError, zipfile.BadZipFile):
        return False


def main() -> None:
    missing = [path for path in PACKAGE_FILES if not path.exists()]
    if missing:
        names = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(
            "Canonical processed files are missing. Run data_pre_process.ipynb "
            f"with WRITE_PROCESSED_FILES=True first:\n{names}"
        )

    if zip_is_complete():
        log(f"Archive already complete: {OUTPUT_ZIP}")
        return

    TEMP_ZIP.unlink(missing_ok=True)
    total_gib = sum(path.stat().st_size for path in PACKAGE_FILES) / 1024**3
    log(f"Packaging exactly 2 Parquet files ({total_gib:.2f} GiB)")

    with zipfile.ZipFile(
        TEMP_ZIP,
        mode="w",
        compression=zipfile.ZIP_STORED,
        allowZip64=True,
    ) as archive:
        for path in PACKAGE_FILES:
            member = path.relative_to(ROOT).as_posix()
            log(f"Adding {member}")
            archive.write(path, arcname=member)

    TEMP_ZIP.replace(OUTPUT_ZIP)
    if not zip_is_complete():
        raise RuntimeError("ZIP validation failed")
    log(f"Complete: {OUTPUT_ZIP} ({OUTPUT_ZIP.stat().st_size / 1024**3:.2f} GiB)")


if __name__ == "__main__":
    main()
