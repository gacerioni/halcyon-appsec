#!/usr/bin/env python3
"""Groups the findings queue into remediation campaigns.

A campaign is one remediation family (a vulnerable package, or a code rule) applied across every repo
where it appears. That is the unit the product security team hands to Devin: one playbook, N repos.

  python tools/triage.py                      # summary table + queue/campaigns.json
  python tools/triage.py --repo vin-registry-service   # what one repo owes
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SLA_DAYS = {"CRITICAL": 15, "HIGH": 30}

# Transitive dependencies are remediated through the framework that pulls them in.
PARENT = {
    "org.apache.tomcat.embed:tomcat-embed-core": "spring-boot",
    "org.springframework:spring-web": "spring-boot",
    "org.springframework:spring-webmvc": "spring-boot",
    "org.springframework:spring-core": "spring-boot",
    "org.springframework:spring-context": "spring-boot",
    "org.springframework:spring-expression": "spring-boot",
    "org.springframework.boot:spring-boot": "spring-boot",
    "org.springframework.boot:spring-boot-autoconfigure": "spring-boot",
    "com.fasterxml.jackson.core:jackson-databind": "jackson",
    "com.fasterxml.jackson.core:jackson-core": "jackson",
    "org.apache.logging.log4j:log4j-core": "log4j",
    "org.apache.logging.log4j:log4j-api": "log4j",
    "org.yaml:snakeyaml": "snakeyaml",
    "golang.org/x/crypto": "x/crypto",
    "golang.org/x/text": "x/text",
    "github.com/dgrijalva/jwt-go": "jwt-go",
    "find-my-way": "fastify",
    "@fastify/send": "fastify",
}


def family(row: dict) -> str:
    if row["tool"] == "semgrep":
        return f"code:{row['id']}"
    pkg = row["package"]
    return f"dep:{PARENT.get(pkg, pkg)}"


def load_findings(path: pathlib.Path) -> list[dict]:
    with path.open() as fh:
        return list(csv.DictReader(fh))


def build_campaigns(rows: list[dict], repos: dict[str, dict]) -> list[dict]:
    by_family: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        by_family[family(r)].append(r)

    campaigns = []
    for fam, items in by_family.items():
        per_repo: dict[str, list[dict]] = collections.defaultdict(list)
        for r in items:
            per_repo[r["repo"]].append(r)
        worst = "CRITICAL" if any(r["severity"] == "CRITICAL" for r in items) else "HIGH"
        campaigns.append({
            "campaign": fam,
            "kind": items[0]["kind"],
            "severity": worst,
            "sla_days": SLA_DAYS[worst],
            "findings": len(items),
            "repos": sorted(per_repo),
            "repos_without_tests": sorted(n for n in per_repo if repos[n]["tests"] is not True),
            "repos_without_owner": sorted(n for n in per_repo if not repos[n]["owners"]),
            "ids": sorted({r["id"] for r in items}),
            "fixed_versions": sorted({r["fixed"] for r in items if r["fixed"]}),
        })
    campaigns.sort(key=lambda c: (c["severity"] != "CRITICAL", -len(c["repos"]), -c["findings"]))
    return campaigns


def print_table(campaigns: list[dict], rows: list[dict], repos: dict[str, dict]) -> None:
    crit = sum(r["severity"] == "CRITICAL" for r in rows)
    print(f"{len(rows)} open findings ({crit} critical, {len(rows) - crit} high) across {len({r['repo'] for r in rows})} repos")
    print(f"{len(campaigns)} remediation campaigns\n")
    print(f"{'campaign':36s} {'sev':8s} {'find':>4s} {'repos':>5s}  {'no tests':>8s} {'no owner':>8s}  repos")
    for c in campaigns:
        print(f"{c['campaign'][:36]:36s} {c['severity']:8s} {c['findings']:4d} {len(c['repos']):5d}  "
              f"{len(c['repos_without_tests']):8d} {len(c['repos_without_owner']):8d}  {', '.join(c['repos'])}")
    print()
    print(f"{'repo':28s} {'lang':10s} {'find':>4s} {'crit':>4s}  tests   owner")
    per_repo = collections.Counter(r["repo"] for r in rows)
    per_repo_crit = collections.Counter(r["repo"] for r in rows if r["severity"] == "CRITICAL")
    for name, meta in repos.items():
        print(f"{name:28s} {meta['language']:10s} {per_repo[name]:4d} {per_repo_crit[name]:4d}  "
              f"{str(meta['tests']).lower():7s} {'yes' if meta['owners'] else 'NO'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--findings", type=pathlib.Path, default=ROOT / "queue" / "findings.csv")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "queue" / "campaigns.json")
    ap.add_argument("--repo", help="print the findings one repo owes and exit")
    args = ap.parse_args()

    repos = {r["name"]: r for r in yaml.safe_load((ROOT / "repos.yaml").read_text())["repos"]}
    rows = load_findings(args.findings)
    if args.repo:
        mine = [r for r in rows if r["repo"] == args.repo]
        for r in mine:
            loc = f"{r['path']}:{r['line']}" if r["line"] else r["path"]
            pkg = f"{r['package']} {r['installed']} -> {r['fixed'] or '?'}" if r["package"] else ""
            print(f"{r['severity']:8s} {r['id']:44s} {pkg:60s} {loc}")
        print(f"\n{len(mine)} findings")
        return 0

    campaigns = build_campaigns(rows, repos)
    print_table(campaigns, rows, repos)
    args.out.write_text(json.dumps(campaigns, indent=2))
    print(f"\nwrote {args.out.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
