"""Download and extract the Alibaba GPU execution-summary Parquet file."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DOWNLOAD_DIR = DATA_DIR / ".downloads"
ZIP_PATH = DOWNLOAD_DIR / "asi_opensource_job_execution_summary.zip"
TARGET_PATH = DATA_DIR / "asi_opensource_job_execution_summary.parquet"

URL = (
    "https://tre-clusterdata.oss-cn-hangzhou.aliyuncs.com/"
    "cluster-trace-gpu-v2026/data/asi_opensource_job_execution_summary.zip"
)
EXPECTED_ZIP_SIZE = 1_188_295_031
BUFFER_SIZE = 8 * 1024 * 1024


def log(message: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def parquet_looks_valid(path: Path) -> bool:
    try:
        if path.stat().st_size < 12:
            return False
        with path.open("rb") as stream:
            if stream.read(4) != b"PAR1":
                return False
            stream.seek(-4, 2)
            return stream.read(4) == b"PAR1"
    except OSError:
        return False


def download_with_resume() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    while (ZIP_PATH.stat().st_size if ZIP_PATH.exists() else 0) < EXPECTED_ZIP_SIZE:
        current_size = ZIP_PATH.stat().st_size if ZIP_PATH.exists() else 0
        headers = {
            "Range": f"bytes={current_size}-{EXPECTED_ZIP_SIZE - 1}",
            "User-Agent": "IS507-dataset-preparation/1.0",
        }
        request = urllib.request.Request(URL, headers=headers)

        try:
            log(
                f"summary: downloading from {current_size / 1024**3:.3f} "
                f"of {EXPECTED_ZIP_SIZE / 1024**3:.3f} GiB"
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                if current_size > 0 and response.status != 206:
                    log("server did not honor resume request; restarting summary ZIP")
                    ZIP_PATH.unlink(missing_ok=True)
                    continue
                mode = "ab" if current_size else "wb"
                with ZIP_PATH.open(mode) as output:
                    while True:
                        block = response.read(BUFFER_SIZE)
                        if not block:
                            break
                        output.write(block)

            if ZIP_PATH.stat().st_size > EXPECTED_ZIP_SIZE:
                raise RuntimeError("Downloaded summary ZIP is larger than expected")
        except (OSError, urllib.error.URLError, TimeoutError) as error:
            log(f"summary: transient download error: {error}; retrying in 15s")
            time.sleep(15)

    if ZIP_PATH.stat().st_size != EXPECTED_ZIP_SIZE:
        raise RuntimeError("Summary ZIP size does not match the official release")


def extract_summary() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = TARGET_PATH.with_suffix(".parquet.part")

    with zipfile.ZipFile(ZIP_PATH) as archive:
        members = [
            item
            for item in archive.infolist()
            if item.filename.endswith("/part-000.parquet")
        ]
        if len(members) != 1:
            raise RuntimeError(f"Expected one summary Parquet member, found {len(members)}")
        member = members[0]
        log("summary: extracting Parquet")
        with archive.open(member) as source, temporary.open("wb") as output:
            while True:
                block = source.read(BUFFER_SIZE)
                if not block:
                    break
                output.write(block)

    if not parquet_looks_valid(temporary):
        temporary.unlink(missing_ok=True)
        raise RuntimeError("Extracted summary Parquet failed the magic-byte check")
    temporary.replace(TARGET_PATH)


def main() -> None:
    if parquet_looks_valid(TARGET_PATH):
        log("summary: already present and valid; skipping")
        return

    download_with_resume()
    extract_summary()
    ZIP_PATH.unlink(missing_ok=True)
    log("summary: complete")


if __name__ == "__main__":
    main()
