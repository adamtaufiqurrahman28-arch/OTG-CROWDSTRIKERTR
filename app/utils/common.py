import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List
from datetime import datetime, timezone


def ensure_success(resp: Dict[str, Any], context: str) -> None:
    status_code = resp.get("status_code")
    if status_code and 200 <= int(status_code) < 300:
        return
    raise RuntimeError(f"{context} gagal | status_code={status_code} | body={resp.get('body')}")


def get_body(resp: Dict[str, Any]) -> Dict[str, Any]:
    return resp.get("body") or {}


def get_resources(resp: Dict[str, Any]):
    return get_body(resp).get("resources", [])


def chunked(items: List[Any], size: int) -> Iterator[List[Any]]:
    for index in range(0, len(items), size):
        yield items[index:index + size]


def parse_version(version: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", str(version or ""))
    return tuple(int(number) for number in numbers) if numbers else tuple()


def to_build_3(version: str) -> str:
    numbers = re.findall(r"\d+", str(version or ""))
    if len(numbers) < 3:
        return ""
    return ".".join(numbers[:3])


def quote_if_needed(text: str) -> str:
    if any(char in text for char in [" ", "'", '"']):
        return f'"{text}"'
    return text


def write_csv(path: Path, rows: List[Dict[str, Any]], headers: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_aids_csv(path: Path, aids: Iterable[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerow(["aid"])
        for aid in aids:
            writer.writerow([aid])


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

def quote_if_needed(text: str) -> str:
    if not text:
        return ""
    if " " in text or "'" in text or '"' in text:
        return f'"{text}"'
    return text

def is_online(last_seen_iso: str, minutes: int = 10) -> bool:
    if not last_seen_iso:
        return False
    try:
        dt = datetime.fromisoformat(last_seen_iso.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - dt
        return age.total_seconds() <= minutes * 60
    except Exception:
        return False