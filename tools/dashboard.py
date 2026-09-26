#!/usr/bin/env python3
"""Remediation Command Center data: dashboard/data.json.

Combines the baseline queue, the after scan (if `make after` ran), test results, Devin session state from
.demo-state/ (refreshed from the Devin API when DEVIN_API_KEY is set) and open PRs. The static page in
dashboard/index.html renders it. Numbers describe the Palm Tree demo estate only.

  python tools/dashboard.py            # write dashboard/data.json
  python tools/dashboard.py --watch 20 # rewrite every 20s (during a live kickoff)
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT = ROOT / "report"
STATE = ROOT / ".demo-state"
OUT = ROOT / "dashboard" / "data.json"
API = os.environ.get("DEVIN_API_BASE", "https://api.devin.ai/v3")
sys.path.insert(0, str(ROOT / "tools"))
from triage import SLA_DAYS, build_campaigns, load_findings  # noqa: E402


def load_repos() -> tuple[str, dict[str, dict]]:
    doc = yaml.safe_load((ROOT / "repos.yaml").read_text())
    return doc["github_org"], {r["name"]: r for r in doc["repos"]}


def read_tests() -> dict[str, dict]:
    out: dict[str, dict] = {}
    p = REPORT / "tests_after.txt"
    if p.exists():
        for line in p.read_text().splitlines():
            name, result, branch, url = (line.split(",") + ["", "", ""])[:4]
            out[name] = {"result": result, "branch": branch, "pr_url": url}
    return out


def refresh_session(session: dict) -> dict:
    key = os.environ.get("DEVIN_API_KEY")
    org = os.environ.get("DEVIN_ORG_ID")
    sid = session.get("session_id")
    if not (key and org and sid):
        return session
    req = urllib.request.Request(f"{API}/organizations/{org}/sessions/{sid}", headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            fresh = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return session
    return {**session, **fresh}


def read_sessions(repos: dict[str, dict]) -> list[dict]:
    out = []
    for name in repos:
        p = STATE / f"{name}.json"
        if not p.exists():
            continue
        s = refresh_session(json.loads(p.read_text()))
        p.write_text(json.dumps(s, indent=2))
        out.append({
            "repo": name,
            "url": s.get("url"),
            "title": s.get("title"),
            "status": s.get("status"),
            "status_detail": s.get("status_detail"),
            "acus": s.get("acus_consumed", 0.0),
            "pull_requests": [pr.get("url") for pr in (s.get("pull_requests") or []) if isinstance(pr, dict) and pr.get("url")],
            "created_at": s.get("created_at"),
        })
    return out


def open_prs(org: str, repos: dict[str, dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = collections.defaultdict(list)
    for name in repos:
        cmd = ["gh", "pr", "list", "--repo", f"{org}/palmtree-{name}", "--state", "open",
               "--json", "number,title,url,headRefName,statusCheckRollup,reviewDecision"]
        try:
            raw = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True).stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            continue
        for pr in json.loads(raw or "[]"):
            if not pr["headRefName"].startswith("devin/"):
                continue
            checks = {c.get("name") or c.get("context"): (c.get("conclusion") or c.get("state") or "").lower()
                      for c in pr.get("statusCheckRollup") or []}
            out[name].append({"number": pr["number"], "title": pr["title"], "url": pr["url"],
                              "branch": pr["headRefName"], "checks": checks,
                              "review": pr.get("reviewDecision") or "REVIEW_REQUIRED"})
    return out


def build() -> dict:
    org, repos = load_repos()
    before = load_findings(ROOT / "queue" / "findings.csv")
    after_path = REPORT / "findings_after.csv"
    after = load_findings(after_path) if after_path.exists() else None
    tests = read_tests()
    sessions = read_sessions(repos)
    prs = open_prs(org, repos)

    def sev_counts(rows: list[dict] | None) -> dict:
        if rows is None:
            return {"total": None, "critical": None, "high": None}
        c = collections.Counter(r["severity"] for r in rows)
        return {"total": len(rows), "critical": c["CRITICAL"], "high": c["HIGH"]}

    def per_repo(rows: list[dict] | None, name: str) -> dict:
        if rows is None:
            return {"total": None, "critical": None}
        mine = [r for r in rows if r["repo"] == name]
        return {"total": len(mine), "critical": sum(r["severity"] == "CRITICAL" for r in mine)}

    cb = build_campaigns(before, repos)
    ca = {c["campaign"]: c for c in build_campaigns(after, repos)} if after else {}
    campaigns = []
    for c in cb:
        a = ca.get(c["campaign"])
        campaigns.append({
            "campaign": c["campaign"], "kind": c["kind"], "severity": c["severity"], "sla_days": c["sla_days"],
            "before": c["findings"], "after": (a["findings"] if a else 0) if after is not None else None,
            "repos": c["repos"], "repos_without_tests": c["repos_without_tests"],
            "repos_without_owner": c["repos_without_owner"], "fixed_versions": c["fixed_versions"],
        })
    introduced = [f for f in ca if f not in {c["campaign"] for c in cb}]

    repo_rows = []
    for name, meta in repos.items():
        repo_rows.append({
            "name": name, "language": meta["language"], "tests": meta["tests"], "owners": meta["owners"],
            "before": per_repo(before, name), "after": per_repo(after, name),
            "tests_after": tests.get(name), "prs": prs.get(name, []),
            "session": next((s for s in sessions if s["repo"] == name), None),
        })

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "estate": {"name": "Palm Tree Motors", "org": org, "repos": len(repos),
                   "repos_without_tests": [n for n, m in repos.items() if m["tests"] is not True],
                   "repos_without_owner": [n for n, m in repos.items() if not m["owners"]],
                   "scm": "GitHub (stands in for GitLab)", "scanners": ["Trivy", "Semgrep"]},
        "sla_days": SLA_DAYS,
        "before": sev_counts(before),
        "after": sev_counts(after),
        "after_available": after is not None,
        "campaigns": campaigns,
        "introduced_by_prs": introduced,
        "repos": repo_rows,
        "sessions": sessions,
        "acus_total": round(sum(s["acus"] or 0 for s in sessions), 2),
        "disclaimer": "Palm Tree Motors is a fictional company. All findings are synthetic and planted for demonstration.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", type=int, default=0, help="rewrite every N seconds")
    args = ap.parse_args()
    while True:
        data = build()
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(data, indent=2))
        print(f"{data['generated_at']}: {data['before']['total']} → {data['after']['total']} findings, "
              f"{len(data['sessions'])} sessions, {sum(len(r['prs']) for r in data['repos'])} PRs → {OUT.relative_to(ROOT)}")
        if not args.watch:
            return 0
        time.sleep(args.watch)


if __name__ == "__main__":
    sys.exit(main())
