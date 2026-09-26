#!/usr/bin/env python3
"""Starts one Devin session per repository, each with the playbook rendered for that repo's findings.

Credentials come from the environment only: DEVIN_API_KEY and DEVIN_ORG_ID. Uses the v3 API
(POST /v3/organizations/{org}/sessions), same as the Leet demo.

  python tools/kickoff.py --all                       # one session per repo with open findings
  python tools/kickoff.py vin-registry-service warranty-claims-api
  python tools/kickoff.py --campaign dep:PyYAML       # only repos in that campaign, only those findings
  python tools/kickoff.py --dry-run vin-registry-service   # print the prompt, start nothing
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import re
import sys
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLAYBOOK = ROOT / "playbooks" / "remediate_security_findings.md"
API = os.environ.get("DEVIN_API_BASE", "https://api.devin.ai/v3")


def load_repos() -> tuple[str, dict[str, dict]]:
    doc = yaml.safe_load((ROOT / "repos.yaml").read_text())
    return doc["github_org"], {r["name"]: r for r in doc["repos"]}


def load_findings() -> list[dict]:
    with (ROOT / "queue" / "findings.csv").open() as fh:
        return list(csv.DictReader(fh))


def findings_table(rows: list[dict]) -> str:
    lines = ["| severity | id | package / rule | installed → fixed | location |", "|---|---|---|---|---|"]
    for r in rows:
        loc = f"`{r['path']}:{r['line']}`" if r["line"] else f"`{r['path']}`"
        pkg = r["package"] or r["id"]
        ver = f"{r['installed']} → {r['fixed'] or 'no fixed version'}" if r["package"] else "code fix"
        lines.append(f"| {r['severity']} | {r['id']} | {pkg} | {ver} | {loc} |")
    return "\n".join(lines)


def render(repo: dict, org: str, rows: list[dict], campaign: str | None) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (campaign or "all-findings").lower()).strip("-")
    return (PLAYBOOK.read_text()
            .replace("{{REPO_URL}}", f"https://github.com/{org}/palmtree-{repo['name']}")
            .replace("{{CONTROL_REPO_URL}}", f"https://github.com/{org}/palmtree-appsec")
            .replace("{{LANGUAGE}}", repo["language"])
            .replace("{{TEST_CMD}}", repo["test_cmd"])
            .replace("{{CAMPAIGN_SLUG}}", slug)
            .replace("{{FINDINGS}}", findings_table(rows)))


def start_session(prompt: str, title: str, key: str, org_id: str) -> dict:
    body = json.dumps({"prompt": prompt, "title": title}).encode()
    req = urllib.request.Request(f"{API}/organizations/{org_id}/sessions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--campaign", help="restrict to one campaign from queue/campaigns.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    org, repos = load_repos()
    rows = load_findings()
    campaign_repos: set[str] | None = None
    if args.campaign:
        campaigns = {c["campaign"]: c for c in json.loads((ROOT / "queue" / "campaigns.json").read_text())}
        if args.campaign not in campaigns:
            ap.error(f"unknown campaign {args.campaign}; run tools/triage.py and pick one")
        c = campaigns[args.campaign]
        campaign_repos = set(c["repos"])
        rows = [r for r in rows if r["id"] in c["ids"] and r["repo"] in campaign_repos]

    targets = list(repos) if args.all else args.repos
    if campaign_repos is not None:
        targets = [t for t in targets] if args.repos else sorted(campaign_repos)
    if not targets:
        ap.error("pass repo names, --all, or --campaign")
    unknown = [t for t in targets if t not in repos]
    if unknown:
        ap.error(f"unknown repos {unknown}")

    key, org_id = os.environ.get("DEVIN_API_KEY"), os.environ.get("DEVIN_ORG_ID")
    if not args.dry_run and not (key and org_id):
        print("DEVIN_API_KEY and DEVIN_ORG_ID must be set", file=sys.stderr)
        return 2

    state = ROOT / ".demo-state"
    state.mkdir(exist_ok=True)
    for name in targets:
        mine = [r for r in rows if r["repo"] == name]
        if not mine:
            print(f"{name}: no open findings, skipping", file=sys.stderr)
            continue
        prompt = render(repos[name], org, mine, args.campaign)
        title = f"[Palm Tree appsec] {args.campaign or 'remediation'}: {name}"
        if args.dry_run:
            print(f"=== {title}\n{prompt}\n")
            continue
        res = start_session(prompt, title, key, org_id)
        (state / f"{name}.json").write_text(json.dumps(res, indent=2))
        print(f"{name}: {res.get('url') or res.get('session_id')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
