#!/usr/bin/env bash
# Puts every service repo back to its baseline: closes open devin/* PRs, deletes devin/* branches,
# resets origin/main to the demo-baseline tag. Clears local after/ checkouts and report outputs.
# Requires gh authenticated for the org in repos.yaml. Never touches anything outside halcyon-* repos.
set -euo pipefail
cd "$(dirname "$0")/.."
ORG=$(python3 -c "import yaml;print(yaml.safe_load(open('repos.yaml'))['github_org'])")

for name in $(python3 -c "import yaml;print(' '.join(r['name'] for r in yaml.safe_load(open('repos.yaml'))['repos']))"); do
  repo="halcyon-$name"
  dir="$repo"
  [ -d "$dir/.git" ] || { echo "$repo: no local checkout, skipping"; continue; }
  git -C "$dir" fetch -q --prune --tags origin
  for pr in $(gh pr list --repo "$ORG/$repo" --state open --json number,headRefName --jq '.[] | select(.headRefName|startswith("devin/")) | .number'); do
    gh pr close --repo "$ORG/$repo" "$pr" --comment "demo reset" --delete-branch >/dev/null && echo "$repo: closed PR #$pr"
  done
  for br in $(git -C "$dir" branch -r --list 'origin/devin/*' | sed 's#origin/##'); do
    git -C "$dir" push -q origin --delete "$br" && echo "$repo: deleted $br"
  done
  git -C "$dir" checkout -q main
  git -C "$dir" reset -q --hard demo-baseline
  git -C "$dir" push -q --force-with-lease origin main
  echo "$repo: main at $(git -C "$dir" rev-parse --short HEAD) (demo-baseline)"
done

rm -rf .after .demo-state report/findings_after.csv report/tests_after.txt report/report.md report/index.html
echo "reset done"
