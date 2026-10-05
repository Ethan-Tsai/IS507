"""Read a downloaded ZIP tail and locate the byte boundary after day 29."""

from __future__ import annotations

import struct
import json
from pathlib import Path


ARCHIVE_SIZE = 351_803_513_445
TAIL_PATH = Path(__file__).parent / "data" / "asi_opensource_pod_hourly.zip.tail"

tail = TAIL_PATH.read_bytes()
tail_start = ARCHIVE_SIZE - len(tail)

eocd_pos = tail.rfind(b"PK\x05\x06")
if eocd_pos < 0:
    raise RuntimeError("ZIP end-of-central-directory record not found")

locator_pos = tail.rfind(b"PK\x06\x07", 0, eocd_pos)
if locator_pos < 0:
    raise RuntimeError("ZIP64 locator not found")

_sig, _disk, zip64_eocd_offset, _disks = struct.unpack_from(
    "<IIQI", tail, locator_pos
)
zip64_pos = zip64_eocd_offset - tail_start
if zip64_pos < 0 or tail[zip64_pos : zip64_pos + 4] != b"PK\x06\x06":
    raise RuntimeError("ZIP64 end-of-central-directory record is outside the tail")

(
    _sig,
    _record_size,
    _made_by,
    _needed,
    _disk_no,
    _cd_disk,
    _entries_disk,
    total_entries,
    central_size,
    central_offset,
) = struct.unpack_from("<IQHHIIQQQQ", tail, zip64_pos)

central_pos = central_offset - tail_start
central_end = central_pos + central_size
if central_pos < 0 or central_end > len(tail):
    raise RuntimeError("Central directory is not fully present in the downloaded tail")


def zip64_values(extra: bytes, need_uncompressed: bool, need_compressed: bool,
                 need_offset: bool, need_disk: bool):
    pos = 0
    while pos + 4 <= len(extra):
        field_id, field_size = struct.unpack_from("<HH", extra, pos)
        data = extra[pos + 4 : pos + 4 + field_size]
        pos += 4 + field_size
        if field_id != 0x0001:
            continue
        cursor = 0
        values = {}
        if need_uncompressed:
            values["uncompressed"] = struct.unpack_from("<Q", data, cursor)[0]
            cursor += 8
        if need_compressed:
            values["compressed"] = struct.unpack_from("<Q", data, cursor)[0]
            cursor += 8
        if need_offset:
            values["offset"] = struct.unpack_from("<Q", data, cursor)[0]
            cursor += 8
        if need_disk:
            values["disk"] = struct.unpack_from("<I", data, cursor)[0]
        return values
    return {}


entries = []
pos = central_pos
central_header = struct.Struct("<I6H3I5H2I")
while pos < central_end:
    values = central_header.unpack_from(tail, pos)
    if values[0] != 0x02014B50:
        raise RuntimeError(f"Invalid central-directory signature at {pos}")
    compressed = values[8]
    uncompressed = values[9]
    name_len, extra_len, comment_len = values[10:13]
    disk_start = values[13]
    local_offset = values[16]
    name_start = pos + central_header.size
    name = tail[name_start : name_start + name_len].decode("utf-8")
    extra = tail[name_start + name_len : name_start + name_len + extra_len]
    extended = zip64_values(
        extra,
        uncompressed == 0xFFFFFFFF,
        compressed == 0xFFFFFFFF,
        local_offset == 0xFFFFFFFF,
        disk_start == 0xFFFF,
    )
    compressed = extended.get("compressed", compressed)
    uncompressed = extended.get("uncompressed", uncompressed)
    local_offset = extended.get("offset", local_offset)
    entries.append((name, local_offset, compressed, uncompressed))
    pos = name_start + name_len + extra_len + comment_len

if len(entries) != total_entries:
    raise RuntimeError(f"Expected {total_entries} entries, parsed {len(entries)}")

day30_name = "asi_opensource_pod_hourly/day=30/hour=00/part-000.parquet"
day30 = next((entry for entry in entries if entry[0] == day30_name), None)
if day30 is None:
    raise RuntimeError(f"Entry not found: {day30_name}")

included = [
    entry
    for entry in entries
    if entry[0].startswith("asi_opensource_pod_hourly/day=")
    and int(entry[0].split("day=")[1].split("/")[0]) < 30
]

partial_path = (
    Path(__file__).parents[1]
    / "dataset"
    / "asi_opensource_pod_hourly.zip"
)
partial_size = partial_path.stat().st_size if partial_path.exists() else 0
entry_index = {entry[0]: index for index, entry in enumerate(entries)}
day_ranges = []
for day in range(30):
    prefix = f"asi_opensource_pod_hourly/day={day}/"
    day_entries = [entry for entry in entries if entry[0].startswith(prefix)]
    if len(day_entries) != 24:
        raise RuntimeError(f"Expected 24 entries for day {day}, found {len(day_entries)}")
    day_entries.sort(key=lambda item: item[1])
    first_index = entry_index[day_entries[0][0]]
    last_index = entry_index[day_entries[-1][0]]
    if last_index + 1 >= len(entries):
        raise RuntimeError(f"Cannot determine range end for day {day}")
    start = day_entries[0][1]
    end_exclusive = entries[last_index + 1][1]
    day_ranges.append(
        {
            "day": day,
            "start": start,
            "end_exclusive": end_exclusive,
            "bytes": end_exclusive - start,
            "gib": round((end_exclusive - start) / 1024**3, 6),
            "available_in_partial": end_exclusive <= partial_size,
        }
    )

manifest_path = TAIL_PATH.parent / "pod_day_ranges_0_29.json"
manifest_path.write_text(json.dumps(day_ranges, indent=2), encoding="utf-8")

print(f"total_entries={total_entries}")
print(f"central_directory_mib={central_size / 1024**2:.3f}")
print(f"selected_entries={len(included)}")
print(f"day30_start_offset={day30[1]}")
print(f"required_prefix_bytes={day30[1]}")
print(f"required_prefix_gib={day30[1] / 1024**3:.3f}")
print(f"selected_uncompressed_gib={sum(item[3] for item in included) / 1024**3:.3f}")
print(f"partial_zip_gib={partial_size / 1024**3:.3f}")
print(
    "days_reusable_from_partial="
    + ",".join(str(item["day"]) for item in day_ranges if item["available_in_partial"])
)
print(
    "remaining_download_gib="
    + f"{sum(item['bytes'] for item in day_ranges if not item['available_in_partial']) / 1024**3:.3f}"
)
print(f"manifest={manifest_path}")
