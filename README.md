# palmtree-appsec

Product Security control repo for Palm Tree Motors, a fictional EV maker with the same shape of problem as a
real one: a backlog of dependency and code findings from several scanners, repeated across many small
repos in Java, TypeScript, Python and Go, a small security team triaging by hand, some repos without tests
or owners, and a CISO with SLAs on critical and high findings.

This repo turns that queue into remediation campaigns and hands each repo to a Devin session running one
playbook. Devin opens one pull request per repo with the fix, tests, and scanner evidence. Humans review
and merge. Nothing here touches `main` or production.

```
scanners (Trivy, Semgrep)            tools/scan.py      -> queue/findings.csv
group by package or rule             tools/triage.py    -> queue/campaigns.json
one playbook, N repos                playbooks/remediate_security_findings.md
one Devin session per repo           tools/kickoff.py   (Devin API v3)
Devin: fix, test, rescan, open PR    devin/appsec-<campaign> branches, CI security-gate red -> green
rerun tests + scanners on PR heads   tools/after.sh     -> report/report.md, report/index.html
```

## Estate

| repo | language | tests | CODEOWNERS | planted problems |
|---|---|---|---|---|
| palmtree-ota-campaign-service | Java 17 / Spring Boot 2.7 | yes | yes | snakeyaml 1.33 + `new Yaml()`, commons-text 1.9, old jackson |
| palmtree-warranty-claims-api | Java 17 / Spring Boot 2.7 | none | none | log4j-core 2.14.1 logging free text, snakeyaml 1.33, no tests |
| palmtree-owner-portal-bff | TypeScript / Fastify | yes | yes | jsonwebtoken 8.5.1 with no alg allowlist, axios 0.21.1, lodash 4.17.15 |
| palmtree-charging-network-gateway | TypeScript / Fastify | none | none | jsonwebtoken 8.5.1, node-fetch 2.6.0, minimist 1.2.5 |
| palmtree-telemetry-quality-checks | Python 3 / FastAPI | yes | yes | PyYAML 5.3 + `yaml.load` without Loader, `subprocess(shell=True)`, Jinja2 2.11 |
| palmtree-fleet-diagnostics-jobs | Python 3 | none | none | PyYAML 5.3, urllib3 1.26.4, cryptography 3.3.2, hardcoded service token |
| palmtree-vin-registry-service | Go 1.22 / SQLite | yes | yes | dgrijalva/jwt-go, x/crypto 0.14, SQL string concatenation |
| palmtree-service-appointments-api | Go 1.22 | partial | none | jwt-go without signing-method check, x/text 0.3.7 |

Baseline scan: 155 CRITICAL+HIGH findings (24 critical), 28 campaigns. The largest campaign
(`dep:spring-boot`, 72 findings) is two repos and one version bump. See `queue/`.

`rules/palmtree-appsec.yml` holds the custom Semgrep rules the security team wrote for the code-level
patterns. Every repo has a GitHub Actions `ci.yml` with a `test` job and a `security-gate` job (Trivy and
Semgrep, fail on CRITICAL/HIGH), so a Devin PR shows red → green without anyone running a tool by hand.

## Running the demo

```bash
set -a; source ~/.palmtree-demo.env; set +a     # DEVIN_API_KEY, DEVIN_ORG_ID (never committed)

make clone                                     # once
make scan && make triage                       # the queue, as the security team sees it
make prompt REPO=warranty-claims-api           # what one session receives
make kickoff ARGS="--campaign dep:PyYAML"      # 2 sessions, live
make kickoff ARGS="--all"                      # 8 sessions, one per repo (dry run the day before)
make status
make after                                     # PR heads: tests + rescan + report/index.html
make reset                                     # back to baseline
```

Requirements: Python 3.10+, `pyyaml`, `trivy`, `semgrep`, `gh` authenticated, plus Java 17 + Maven,
Node 20, Go 1.22 for `make after`.

## Why this shape

- Findings repeated across repos are the natural unit for fan-out: one playbook, N sessions, N PRs.
- A PR with tests and a before/after scan is evidence a fix is safe. A lower finding count is not.
- Repos without tests get a characterization test first, so the reviewer has something to trust.
- Suppressions and rule edits are forbidden in the playbook. Devin has to fix the code or say it could not.
- GitHub stands in for GitLab here. The flow is identical on GitLab: merge request instead of pull request,
  GitLab CI instead of Actions.
