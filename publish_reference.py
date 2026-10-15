#!/usr/bin/env python3
"""Freeze extension artifacts and build the matching Jev GitHub Pages report.

This prepares files only. Git commits and publication are explicit later steps.
"""
import argparse
import html
import json
from pathlib import Path
import re
import shutil

import markdown
from run_extension import OUT, sha_file, write_json


def build(jev_repo):
    checksums = {p.relative_to(OUT).as_posix(): sha_file(p) for p in sorted(OUT.rglob("*"))
                 if p.is_file() and p.name != "checksums.json"}
    write_json(OUT / "checksums.json", checksums)
    shutil.copytree(OUT, jev_repo / "extension_136", dirs_exist_ok=True)
    asset_dir = jev_repo / "docs/extension_136-assets"
    asset_dir.mkdir(exist_ok=True)
    for path in OUT.glob("abilities_baseline.*"):
        shutil.copy2(path, asset_dir / path.name)
    body = markdown.markdown((OUT / "README.md").read_text(), extensions=["tables", "fenced_code"])
    prefix = "https://github.com/etsabary/jev-deterministic-benchmark/blob/main/extension_136/"
    body = re.sub(r'href="(?!https?://|#)([^"]+)"', lambda m: 'href="' + prefix + m.group(1) + '"', body)
    body = re.sub(r'src="(abilities_baseline\.[^"]+)"', r'src="extension_136-assets/\1"', body)
    document = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jev 1.13 vs GPT-6 Luna Decisions: expanded 1,136-question reference</title>
<style>
body{max-width:1100px;margin:0 auto;padding:38px 24px 80px;background:#f7f9fc;color:#172c42;font:17px/1.65 system-ui,sans-serif}
h1{font-size:2.2rem;line-height:1.2}h2{margin-top:2.4rem;line-height:1.3}h3{margin-top:2rem}a{color:#087f8c}img{max-width:100%;height:auto;border-radius:12px}
table{display:block;overflow-x:auto;border-collapse:collapse;max-width:100%;font-size:.9rem}th,td{padding:10px 13px;border-bottom:1px solid #d5dfe9;text-align:left}th{background:#e7eef5}code{font-size:.86em;overflow-wrap:anywhere}nav{font-size:.9rem;border-bottom:1px solid #d5dfe9;padding-bottom:16px;margin-bottom:32px}p,li{max-width:95ch}
</style><nav><a href="index.html">Original 1,000-question dashboard</a> · <a href="https://github.com/etsabary/luna-decisions-benchmark">Comparison repository and reproduction</a></nav><main>
""" + body + "</main></html>\n"
    (jev_repo / "docs/extension_136.html").write_text(document)
    print(f"Froze {len(checksums)} artifacts; mirrored the reference and built the expanded Pages report")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--jev-repo", type=Path, required=True)
    build(p.parse_args().jev_repo)
