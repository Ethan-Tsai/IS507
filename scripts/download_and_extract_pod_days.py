"""Download and extract only pod-hourly day=0..29 from the remote ZIP.

The archive stores Parquet members without compression.  A precomputed range
manifest lets this script request one contiguous byte range per day instead of
downloading the full 327 GiB ZIP.  Completed days are resumable checkpoints.
"""

from __future__ import annotations

import json
import os
import struct
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MANIFEST_PATH = DATA_DIR / "pod_day_ranges_0_29.json"
PARTIAL_ZIP = ROOT.parent / "dataset" / "asi_opensource_pod_hourly.zip"
CHUNK_DIR = DATA_DIR / ".pod_download_chunks"
OUTPUT_ROOT = DATA_DIR
URL = (
    "https://tre-clusterdata.oss-cn-hangzhou.aliyuncs.com/"
    "cluster-trace-gpu-v2026/data/asi_opensource_pod_hourly.zip"
)

LOCAL_HEADER = struct.Struct("<IHHHHHIIIHH")
LOCAL_SIGNATURE = 0x04034B50
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
            stream.seek(-4, os.SEEK_END)
            return stream.read(4) == b"PAR1"
    except OSError:
        return False


def day_is_complete(day: int) -> bool:
    day_dir = OUTPUT_ROOT / "asi_opensource_pod_hourly" / f"day={day}"
    files = sorted(day_dir.glob("hour=*/part-000.parquet"))
    return len(files) == 24 and all(parquet_looks_valid(path) for path in files)


def safe_destination(member_name: str) -> Path:
    destination = (OUTPUT_ROOT / member_name).resolve()
    output_root = OUTPUT_ROOT.resolve()
    if os.path.commonpath((str(output_root), str(destination))) != str(output_root):
        raise ValueError(f"Unsafe ZIP member path: {member_name}")
    return destination


def extract_range(source_path: Path, start: int, end_exclusive: int, day: int) -> None:
    extracted = 0
    with source_path.open("rb") as source:
        position = start
        while position < end_exclusive:
            source.seek(position)
            header = source.read(LOCAL_HEADER.size)
            if len(header) != LOCAL_HEADER.size:
                raise EOFError(f"Incomplete local header for day {day} at {position}")
            (
                signature,
                _version,
                flags,
                method,
                _mtime,
                _mdate,
                expected_crc,
                compressed_size,
                uncompressed_size,
                name_length,
                extra_length,
            ) = LOCAL_HEADER.unpack(header)
            if signature != LOCAL_SIGNATURE:
                raise RuntimeError(f"Bad ZIP local signature at {position}")
            if flags & 0x08:
                raise RuntimeError("ZIP data descriptors are not supported")
            if method != 0:
                raise RuntimeError(f"Unexpected compression method {method}")

            raw_name = source.read(name_length)
            encoding = "utf-8" if flags & 0x800 else "cp437"
            member_name = raw_name.decode(encoding)
            source.seek(extra_length, os.SEEK_CUR)
            data_offset = position + LOCAL_HEADER.size + name_length + extra_length
            data_end = data_offset + compressed_size
            if data_end > end_exclusive:
                raise EOFError(f"Member extends beyond day range: {member_name}")
            expected_prefix = f"asi_opensource_pod_hourly/day={day}/"
            if not member_name.startswith(expected_prefix):
                raise RuntimeError(
                    f"Unexpected member in day {day} range: {member_name}"
                )

            destination = safe_destination(member_name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.stat().st_size == uncompressed_size if destination.exists() else False:
                if parquet_looks_valid(destination):
                    extracted += 1
                    position = data_end
                    continue

            temp_destination = destination.with_suffix(destination.suffix + ".part")
            source.seek(data_offset)
            remaining = compressed_size
            crc = 0
            with temp_destination.open("wb") as output:
                while remaining:
                    chunk = source.read(min(BUFFER_SIZE, remaining))
                    if not chunk:
                        raise EOFError(f"Unexpected EOF in {member_name}")
                    output.write(chunk)
                    crc = zlib.crc32(chunk, crc)
                    remaining -= len(chunk)
            if crc != expected_crc:
                temp_destination.unlink(missing_ok=True)
                raise RuntimeError(f"CRC mismatch for {member_name}")
            temp_destination.replace(destination)
            extracted += 1
            position = data_end

    if extracted != 24 or not day_is_complete(day):
        raise RuntimeError(f"Day {day} extraction incomplete: {extracted} members")


def download_range(day_info: dict) -> Path:
    day = int(day_info["day"])
    start = int(day_info["start"])
    end_exclusive = int(day_info["end_exclusive"])
    expected_size = end_exclusive - start
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    chunk_path = CHUNK_DIR / f"day={day}.zipchunk"

    while (chunk_path.stat().st_size if chunk_path.exists() else 0) < expected_size:
        current_size = chunk_path.stat().st_size if chunk_path.exists() else 0
        request_start = start + current_size
        headers = {
            "Range": f"bytes={request_start}-{end_exclusive - 1}",
            "User-Agent": "IS507-dataset-preparation/1.0",
        }
        request = urllib.request.Request(URL, headers=headers)
        try:
            log(
                f"day={day}: downloading from {current_size / 1024**3:.3f} "
                f"of {expected_size / 1024**3:.3f} GiB"
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                if response.status != 206:
                    raise RuntimeError(f"Expected HTTP 206, got {response.status}")
                with chunk_path.open("ab") as output:
                    while True:
                        block = response.read(BUFFER_SIZE)
                        if not block:
                            break
                        output.write(block)
            current_size = chunk_path.stat().st_size
            if current_size > expected_size:
                raise RuntimeError(
                    f"Downloaded range is too large for day {day}: {current_size}"
                )
        except (OSError, urllib.error.URLError, TimeoutError) as error:
            log(f"day={day}: transient download error: {error}; retrying in 15s")
            time.sleep(15)

    if chunk_path.stat().st_size != expected_size:
        raise RuntimeError(f"Wrong chunk size for day {day}")
    return chunk_path


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    log("Starting selective download/extraction for day=0..29")
    for day_info in manifest:
        day = int(day_info["day"])
        if day_is_complete(day):
            log(f"day={day}: already complete; skipping")
            continue
        start = int(day_info["start"])
        end_exclusive = int(day_info["end_exclusive"])
        if bool(day_info["available_in_partial"]):
            log(f"day={day}: extracting from existing partial ZIP")
            extract_range(PARTIAL_ZIP, start, end_exclusive, day)
        else:
            chunk_path = download_range(day_info)
            log(f"day={day}: extracting downloaded range")
            extract_range(chunk_path, 0, end_exclusive - start, day)
            chunk_path.unlink(missing_ok=True)
        log(f"day={day}: complete")
    log("All 30 days downloaded, extracted, and validated")


if __name__ == "__main__":
    main()
