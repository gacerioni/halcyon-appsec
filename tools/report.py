#!/usr/bin/env python3
"""Before/after report: queue/findings.csv (baseline) vs report/findings_after.csv (PR heads).

Writes report/report.md and report/index.html. Numbers are for the Palm Tree demo estate only.
"""
from __future__ import annotations

import collections
import html
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT = ROOT / "report"
sys.path.insert(0, str(ROOT / "tools"))
from triage import build_campaigns, load_findings  # noqa: E402


def read_tests() -> dict[str, tuple[str, str, str]]:
    out: dict[str, tuple[str, str, str]] = {}
    p = REPORT / "tests_after.txt"
    if p.exists():
        for line in p.read_text().splitlines():
            name, result, branch, url = (line.split(",") + ["", "", ""])[:4]
            out[name] = (result, branch, url)
    return out


def counts(rows: list[dict]) -> collections.Counter:
    return collections.Counter(r["repo"] for r in rows)


def main() -> int:
    repos = {r["name"]: r for r in yaml.safe_load((ROOT / "repos.yaml").read_text())["repos"]}
    before = load_findings(ROOT / "queue" / "findings.csv")
    after = load_findings(REPORT / "findings_after.csv")
    tests = read_tests()
    b_all, a_all = counts(before), counts(after)
    b_crit = counts([r for r in before if r["severity"] == "CRITICAL"])
    a_crit = counts([r for r in after if r["severity"] == "CRITICAL"])

    md = ["# Remediation campaign: before / after", "",
          f"Findings (CRITICAL+HIGH): **{len(before)} → {len(after)}**. "
          f"Critical: **{sum(b_crit.values())} → {sum(a_crit.values())}**. "
          f"Repos: {len(repos)}. Data from the Palm Tree demo estate, not a customer.", "",
          "| repo | lang | tests before | before (crit) | after (crit) | tests on PR | PR |", "|---|---|---|---|---|---|---|"]
    for name, meta in repos.items():
        result, branch, url = tests.get(name, ("n/a", "", ""))
        pr = f"[{branch}]({url})" if url else "no PR"
        md.append(f"| {name} | {meta['language']} | {meta['tests']} | {b_all[name]} ({b_crit[name]}) | "
                  f"{a_all[name]} ({a_crit[name]}) | {result} | {pr} |")

    md += ["", "## Campaigns", "", "| campaign | severity | before | after | repos |", "|---|---|---|---|---|"]
    cb = {c["campaign"]: c for c in build_campaigns(before, repos)}
    ca = {c["campaign"]: c for c in build_campaigns(after, repos)} if after else {}
    for fam, c in cb.items():
        a = ca.get(fam)
        md.append(f"| {fam} | {c['severity']} | {c['findings']} | {a['findings'] if a else 0} | {', '.join(c['repos'])} |")
    left = [f for f in ca if f not in cb]
    if left:
        md += ["", "New findings introduced by the PRs (must be zero): " + ", ".join(left)]

    md += ["", "## Still needs a human", "",
           "- Every PR above is open, not merged. Review, then merge.",
           "- Findings marked left open in a PR body need a product decision, not a scanner.",
           "- Repos without CODEOWNERS: " + ", ".join(n for n, m in repos.items() if not m["owners"]) + ". Assign an owner before merging."]
    text = "\n".join(md) + "\n"
    (REPORT / "report.md").write_text(text)
    (REPORT / "index.html").write_text(render_html(text))
    print(text)
    return 0


def render_html(md: str) -> str:
    body = []
    in_table = False
    for line in md.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set(line) <= set("|-: "):
                continue
            tag = "th" if not in_table else "td"
            body.append(("<table>" if not in_table else "") + "<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
            in_table = True
            continue
        if in_table:
            body.append("</table>")
            in_table = False
        if line.startswith("# "):
            body.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("- "):
            body.append(f"<li>{inline(line[2:])}</li>")
        elif line.strip():
            body.append(f"<p>{inline(line)}</p>")
    if in_table:
        body.append("</table>")
    style = ("body{font:20px/1.4 -apple-system,Segoe UI,Helvetica,sans-serif;max-width:1200px;margin:40px auto;padding:0 24px;color:#111}"
             "table{border-collapse:collapse;margin:16px 0;width:100%}td,th{border-bottom:1px solid #ddd;padding:8px 10px;text-align:left}"
             "th{background:#f3f3f3}strong{color:#0a7d2c}h1{font-size:40px}h2{margin-top:40px}")
    return f"<!doctype html><meta charset=utf-8><title>Palm Tree remediation report</title><style>{style}</style>" + "\n".join(body)


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
    return s


if __name__ == "__main__":
    sys.exit(main())
