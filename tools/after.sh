#!/usr/bin/env bash
# Checks out every open devin/* pull request head into .after/<repo>, reruns tests and scanners there,
# and builds the before/after report. main is never touched.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PATH:/usr/local/go/bin:$HOME/go/bin"
ORG=$(python3 -c "import yaml;print(yaml.safe_load(open('repos.yaml'))['github_org'])")
mkdir -p .after report
: > report/tests_after.txt

for name in $(python3 -c "import yaml;print(' '.join(r['name'] for r in yaml.safe_load(open('repos.yaml'))['repos']))"); do
  repo="palmtree-$name"
  dst=".after/$repo"
  if [ ! -d "$dst/.git" ]; then
    git clone -q "https://github.com/$ORG/$repo" "$dst"
  fi
  git -C "$dst" fetch -q --prune origin
  pr_branch=$(gh pr list --repo "$ORG/$repo" --state open --json headRefName --jq '.[] | select(.headRefName|startswith("devin/")) | .headRefName' | head -1 || true)
  if [ -n "$pr_branch" ]; then
    git -C "$dst" checkout -q -B after "origin/$pr_branch"
    pr_url=$(gh pr list --repo "$ORG/$repo" --state open --json url,headRefName --jq ".[] | select(.headRefName==\"$pr_branch\") | .url")
  else
    git -C "$dst" checkout -q -B after origin/main
    pr_url=""
  fi
  test_cmd=$(python3 -c "import yaml;print(next(r['test_cmd'] for r in yaml.safe_load(open('repos.yaml'))['repos'] if r['name']=='$name'))")
  if (cd "$dst" && bash -c "$test_cmd") >"$dst.test.log" 2>&1; then result=pass; else result=FAIL; fi
  echo "$name,$result,${pr_branch:-main},${pr_url}" >> report/tests_after.txt
  echo "$name: tests=$result branch=${pr_branch:-main}"
done

python3 tools/scan.py --root .after --out report/findings_after.csv
python3 tools/report.py
python3 tools/dashboard.py
