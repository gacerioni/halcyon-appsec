#!/usr/bin/env python3
"""Runs Trivy (dependencies) and Semgrep (code) over every service repo and writes the findings queue.

This stands in for the scanners that, in a real estate, land in Jira. Output is a flat CSV that
triage.py groups into campaigns.

  python tools/scan.py                 # all repos in repos.yaml -> queue/findings.csv
  python tools/scan.py --only vin-registry-service
  python tools/scan.py --root /tmp/after --out report/findings_after.csv   # rescan another checkout
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
RULES = ROOT / "rules" / "halcyon-appsec.yml"
COLUMNS = ["repo", "language", "tool", "severity", "kind", "id", "package", "installed", "fixed", "path", "line", "title"]
SEMGREP_PACKS = {"java": "p/java", "typescript": "p/typescript", "python": "p/python", "go": "p/golang"}


def load_repos() -> list[dict]:
    return yaml.safe_load((ROOT / "repos.yaml").read_text())["repos"]


def trivy(path: pathlib.Path) -> list[dict]:
    out = subprocess.run(
        ["trivy", "fs", "--scanners", "vuln", "--severity", "CRITICAL,HIGH", "--ignore-unfixed", "-q", "--format", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    doc = json.loads(out)
    rows: list[dict] = []
    for result in doc.get("Results") or []:
        for v in result.get("Vulnerabilities") or []:
            rows.append({
                "tool": "trivy", "severity": v["Severity"], "kind": "dependency", "id": v["VulnerabilityID"],
                "package": v["PkgName"], "installed": v["InstalledVersion"], "fixed": v.get("FixedVersion", ""),
                "path": result["Target"], "line": "", "title": (v.get("Title") or v.get("Description") or "")[:120],
            })
    return rows


def semgrep(path: pathlib.Path, language: str) -> list[dict]:
    cmd = ["semgrep", "scan", "--config", str(RULES), "--config", SEMGREP_PACKS[language], "--config", "p/secrets",
           "--metrics=off", "--json", "-q", "--exclude", ".venv", "--exclude", "node_modules", "--exclude", "target", str(path)]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    doc = json.loads(out) if out.strip() else {"results": []}
    rows: list[dict] = []
    for r in doc["results"]:
        if r["extra"]["severity"] != "ERROR":
            continue
        rows.append({
            "tool": "semgrep", "severity": "HIGH", "kind": "code", "id": r["check_id"].split(".")[-1],
            "package": "", "installed": "", "fixed": "",
            "path": str(pathlib.Path(r["path"]).relative_to(path)), "line": r["start"]["line"],
            "title": r["extra"]["message"].split(".")[0][:120],
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=pathlib.Path, default=ROOT, help="directory containing the repo checkouts")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "queue" / "findings.csv")
    ap.add_argument("--only", nargs="*", default=[])
    args = ap.parse_args()

    rows: list[dict] = []
    for repo in load_repos():
        if args.only and repo["name"] not in args.only:
            continue
        path = args.root / f"halcyon-{repo['name']}"
        if not path.exists():
            print(f"skip {repo['name']}: {path} missing", file=sys.stderr)
            continue
        found = trivy(path) + semgrep(path, repo["language"])
        for f in found:
            f.update(repo=repo["name"], language=repo["language"])
        rows.extend(found)
        print(f"{repo['name']:32s} {len(found):3d} findings", file=sys.stderr)

    rows.sort(key=lambda r: (r["repo"], r["tool"], r["id"], r["package"], r["path"]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} findings to {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
