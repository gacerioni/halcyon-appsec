SHELL := /bin/bash
PY := python3

.PHONY: help clone scan triage prompt kickoff status after dashboard ops-deploy reset baseline

help:
	@echo "make clone      clone the 8 palmtree-* service repos next to this Makefile"
	@echo "make scan       run Trivy + Semgrep over every repo -> queue/findings.csv"
	@echo "make triage     group findings into campaigns -> table + queue/campaigns.json"
	@echo "make prompt     render the playbook for one repo, to paste into Devin (REPO=vin-registry-service [CAMPAIGN=dep:PyYAML])"
	@echo "make kickoff    start Devin sessions via API (ARGS='--all' | ARGS='--campaign dep:PyYAML' | ARGS='repo1 repo2')"
	@echo "make status     open devin/* PRs across the repos"
	@echo "make after      check out PR heads, rerun tests + scanners, build report/report.md and index.html"
	@echo "make dashboard  build dashboard/data.json (findings, campaigns, sessions, PRs) for the Remediation Command Center"
	@echo "make ops-deploy scp dashboard/ to the demo VM and rebuild the ops container (DEPLOY=user@host)"
	@echo "make reset      close devin PRs, delete devin branches, reset main to demo-baseline"
	@echo "make baseline   tag current main of every repo as demo-baseline (do once)"

ORG := $(shell $(PY) -c "import yaml;print(yaml.safe_load(open('repos.yaml'))['github_org'])")
REPOS := $(shell $(PY) -c "import yaml;print(' '.join('palmtree-'+r['name'] for r in yaml.safe_load(open('repos.yaml'))['repos']))")

clone:
	@for r in $(REPOS); do [ -d $$r/.git ] || git clone -q https://github.com/$(ORG)/$$r $$r; done

scan:
	@$(PY) tools/scan.py

triage:
	@$(PY) tools/triage.py

prompt:
	@$(PY) tools/kickoff.py --dry-run $(if $(CAMPAIGN),--campaign $(CAMPAIGN)) $(or $(REPO),vin-registry-service) | tail -n +2

kickoff:
	@$(PY) tools/kickoff.py $(ARGS)

status:
	@for r in $(REPOS); do gh pr list --repo $(ORG)/$$r --state open 2>/dev/null | sed "s#^#$$r  #"; done

after:
	@bash tools/after.sh

dashboard:
	@$(PY) tools/dashboard.py

ops-deploy: dashboard
	@scp -rq dashboard/ $(DEPLOY):palmtree-appsec/ && ssh $(DEPLOY) "cd palmtree-appsec/deploy && docker compose up -d --build ops" && echo "ops deployed"

reset:
	@bash tools/demo_reset.sh

baseline:
	@for r in $(REPOS); do git -C $$r tag -f demo-baseline main && git -C $$r push -q -f origin demo-baseline && echo "$$r: demo-baseline at $$(git -C $$r rev-parse --short main)"; done
