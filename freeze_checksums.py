#!/usr/bin/env python3
"""Record hashes after an intentionally reviewed regeneration of evidence."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
paths = sorted(p for folder in ["data", "analysis", "figures"] for p in (ROOT / folder).iterdir()
               if p.is_file() and p.name != "checksums.json")
checksums = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(ROOT / "data/checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
print(f"Recorded {len(checksums)} artifact checksums")
