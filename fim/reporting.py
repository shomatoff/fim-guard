"""Export event metadata; never export file contents."""

import csv
import json
from pathlib import Path


FIELDS = ("timestamp", "kind", "root", "path", "old_hash", "new_hash")


def _csv_safe(value):
    """Prevent spreadsheet formula execution from attacker-controlled paths."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_events(events, destination):
    path = Path(destination)
    if path.suffix.lower() not in (".json", ".csv"):
        raise ValueError("Report must end in .json or .csv")
    rows = [{key: item.get(key) for key in FIELDS} for item in events]
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        with path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows({key: _csv_safe(value) for key, value in row.items()} for row in rows)
    return path


def export_scan(scan, events, destination):
    """Export one scan summary and its events without file contents."""
    path = Path(destination)
    if path.suffix.lower() not in (".json", ".csv"):
        raise ValueError("Report must end in .json or .csv")
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps({"scan": scan, "events": events}, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        columns = ("scan_id", "started_at", "finished_at", "status", "added_count",
                   "modified_count", "deleted_count", "error_count", *FIELDS)
        summary = {
            "scan_id": scan["id"], "started_at": scan["started_at"],
            "finished_at": scan["finished_at"], "status": scan["status"],
            "added_count": scan["added"], "modified_count": scan["modified"],
            "deleted_count": scan["deleted"], "error_count": scan["errors"],
        }
        with path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            for event in events or [{}]:
                writer.writerow({key: _csv_safe(value) for key, value in {**summary, **{key: event.get(key) for key in FIELDS}}.items()})
    return path
