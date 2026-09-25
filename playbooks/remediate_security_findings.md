# Playbook: remediate security findings in one repository

You are remediating open security findings for Halcyon Motors Product Security in the repository
{{REPO_URL}} (language: {{LANGUAGE}}). Work only in this repository. Open exactly one pull request.

## Findings assigned to you

{{FINDINGS}}

Findings came from Trivy (dependency CVEs) and Semgrep (code rules, including the custom rules in
{{CONTROL_REPO_URL}}/blob/main/rules/halcyon-appsec.yml). The severity labels and SLAs are the
CISO's, not yours: CRITICAL must close within 15 days, HIGH within 30.

## Procedure

1. Clone the repository and get the baseline green before touching anything: `{{TEST_CMD}}`.
   If there is no test suite, say so in the PR and go to step 5 before step 3.
2. Rescan locally so you can prove the delta afterwards:
   `trivy fs --scanners vuln --severity CRITICAL,HIGH --ignore-unfixed .` and
   `semgrep scan --config <the rules file above> --config p/{{LANGUAGE}} --config p/secrets --metrics=off .`
   Save the output; you will paste the before/after counts in the PR.
3. Dependency findings: bump to the smallest version that clears every CVE listed for that package.
   Prefer the framework bump when the vulnerable package is transitive (Spring Boot pulls Tomcat,
   Fastify pulls find-my-way). Then build and run the tests. If the bump breaks the build or a test,
   fix the code to match the new API. Do not pin, exclude or suppress a finding to make the scanner
   quiet. If a bump is genuinely impossible (no fixed version, incompatible major), leave the finding
   open and explain why in the PR.
4. Code findings: fix the code, not the rule. Typical fixes: parameterized SQL, `yaml.safe_load` or
   `SafeConstructor`, JWT algorithm allowlist and signing-method check, secrets read from the
   environment, no untrusted free text through Log4j. Never edit or delete the rules file or add
   `nosemgrep` comments.
5. Repos without tests: add a minimal characterization test for the code path you changed
   (for example: the token verifier rejects a token signed with another key, the YAML loader still
   reads the shipped config, the SQL query still finds the owner's rows). Keep it small and runnable
   in CI. This is the safety evidence the reviewer needs; a lower finding count alone is not.
6. Rerun the test command and both scanners. Every finding you claim to have fixed must be absent
   from the rescan.
7. Create a branch `devin/appsec-{{CAMPAIGN_SLUG}}` and open a single pull request against `main`.
   Do not merge it. Do not push to `main`.

## Pull request body (use exactly these sections)

- **Findings addressed**: table with id, package or rule, before → after version or file:line.
- **Findings left open**: id and the reason (no fixed version, needs product decision, false positive with proof).
- **Evidence**: before/after counts from Trivy and Semgrep, test command and result, tests added.
- **Risk notes**: anything a human should look at before merging (behavior change, major version bump, API change).

## Rules

- No merges. No changes to `main`. No changes to CI workflows, CODEOWNERS or scanner configuration.
- No new dependencies unless required by a bump.
- Do not touch production configuration, secrets or infrastructure. This repository is the whole scope.
- If you are unsure whether a change is safe, keep the finding open and say so. An honest "not fixed"
  is worth more than a quiet suppression.
