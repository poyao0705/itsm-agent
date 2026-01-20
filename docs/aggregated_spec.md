# ISO/IEC 20000 Change Compliance Agent — Aggregated MVP Spec

## 0. Purpose and guardrails

### 0.1 MVP objective
Evaluate GitHub Pull Requests for change-management compliance using only PR artifacts (title/body + changed files + diff), and publish a clear result back to GitHub.

This MVP prioritizes:
- Deterministic policy-as-code as the baseline risk signal.
- Minimal but correct snapshotting and idempotency to avoid race conditions and stale evaluations.
- A small number of user-visible outcomes and reason codes.

### 0.2 Explicit non-goals (deferred)
The MVP does **not** include:
- Jira content evaluation or Jira-versus-diff semantic alignment.
- Merge blocking / branch protection automation.
- Append-only audit ledger and evidence blob store (lightweight run history is sufficient for now).
- Greptile/Sourcegraph enrichment (planned as a future phase).

### 0.3 Terminology
- **PR identity**: `(repo_full_name, pr_number)`.
- **Snapshot**: immutable capture of the PR inputs being evaluated.
- **Evaluation key**: stable identifier for an evaluation attempt, derived from the snapshot.
- **System risk**: computed risk used for gating (LOW/HIGH).
- **User risk**: risk declared in the PR template (LOW/HIGH).


## 1. Functional scope

### 1.1 Inputs
From GitHub:
- PR title
- PR body (contains the PR template content)
- Head SHA (commit) and repository metadata
- Changed files list (paths; optionally patch snippets)

From repository config:
- `policy.yaml` checked into the repo (versioned)

### 1.2 Outputs
To GitHub:
- A GitHub **Check Run** named `Change Compliance` on the evaluated commit SHA
- A Markdown summary that includes:
  - user risk, system risk, effective risk
  - blocking reason codes (if any)
  - required next actions (if any)

Optionally (recommended):
- A short PR comment only when the status is `ACTION_REQUIRED` (to improve author visibility).

### 1.3 Status taxonomy (MVP)
The MVP uses a small number of states:
- `PROCESSING`: evaluation is running for a snapshot
- `ACTION_REQUIRED`: the PR is not compliant yet and requires author action
- `COMPLIANT`: all required checks pass
- `ERROR`: evaluation failed due to system/integration issues (non-actionable by author)

### 1.4 Reason codes (MVP)
Reason codes are stable machine-readable strings surfaced in Check Run output.

Deterministic reasons:
- `MISSING_TICKET_NUMBER`: PR title does not contain a Jira-style ticket key
- `MISMATCH_RISK_LEVEL`: user-declared risk differs from system risk
- `MISSING_BACKOUT_PLAN`: effective risk is HIGH and backout plan section is empty

LLM-based reason (Phase 2+):
- `MISMATCH_BACKOUT_PLAN`: backout plan exists but does not appear to fit the change

System reasons:
- `GITHUB_API_FAILED`: could not fetch required PR evidence
- `POLICY_LOAD_FAILED`: cannot load/parse `policy.yaml`
- `LLM_CALL_FAILED`: LLM call failed or response invalid

### 1.5 Risk taxonomy
- `LOW`
- `HIGH`

Ordering: `HIGH > LOW`.

### 1.6 Risk reconciliation rule
- `policy_risk`: computed deterministically from file paths using `policy.yaml`
- `llm_risk`: computed by LLM from diff content (Phase 1+)
- `system_risk = max(policy_risk, llm_risk)`

For Phase 0 (fully deterministic MVP), set `llm_risk = LOW`.

### 1.7 Compliance rule summary (MVP)
A snapshot is `COMPLIANT` if and only if:
1) Ticket key present in PR title, AND
2) user risk equals system risk, AND
3) if effective risk is HIGH, backout plan is present and valid (validity is deterministic presence-only in MVP; quality/fit check is Phase 2).

## 2. PR template specification

### 2.1 Required sections
The PR description must contain these two sections (order may vary):

1) **Risk declaration** (checkboxes)
- Exactly one of LOW or HIGH must be selected.
- If neither or both are selected, treat user risk as `UNKNOWN` and set `ACTION_REQUIRED` with `MISMATCH_RISK_LEVEL`.

2) **Backout plan**
- Required only when effective risk is HIGH.
- Backout plan should follow the headings below to support deterministic extraction and future LLM validation.

### 2.2 Recommended backout plan structure (machine-detectable headings)
Use stable Markdown headings (either `##` or `###`):

- **Trigger / decision criteria**: conditions that trigger rollback
- **Rollback steps**: sequence of actions at a high level
- **Data considerations**: migrations, backward compatibility, restoration approach
- **Verification**: how to confirm rollback success and service health
- **Communication**: who is notified and how

### 2.3 Example PR template snippet
```markdown
## Risk
- [ ] LOW
- [ ] HIGH

## Backout Plan
### Trigger / decision criteria

### Rollback steps

### Data considerations

### Verification

### Communication
```

### 2.4 Template parsing rules (deterministic)
- Risk: detect Markdown checkbox pattern `- [x]` (case-insensitive X) next to LOW/HIGH.
- Backout plan: capture all text under the `Backout Plan` heading until the next top-level heading.
- Normalize line endings and strip trailing whitespace prior to hashing.

## 3. `policy.yaml` specification (MVP)

### 3.1 Required fields
`policy.yaml` is stored in the repo (e.g., `.change-compliance/policy.yaml`). It must contain:
- `policy_version`: string (semantic version recommended)
- `jira_key_regex`: regex for ticket keys (e.g., `([A-Z][A-Z0-9]+-\d+)`)
- `high_risk_paths`: list of glob patterns; if any changed path matches, policy risk = HIGH
- `low_risk_paths` (optional): list of glob patterns; if matched and no high risk match, keep LOW (default is LOW)

### 3.2 Matching rules
- Use case-sensitive path matching (GitHub paths are case-sensitive).
- Evaluate `high_risk_paths` first. If any match, policy risk is HIGH.
- Otherwise, policy risk is LOW.

### 3.3 Example
```yaml
policy_version: "0.1.0"
jira_key_regex: "([A-Z][A-Z0-9]+-\\d+)"
high_risk_paths:
  - "db/migrations/**"
  - "infra/**"
  - "terraform/**"
  - "k8s/**"
  - "auth/**"
```

### 3.4 Future extension points
- `path_to_risk_map`: support multiple tiers (MEDIUM/CRITICAL) if you expand beyond LOW/HIGH.
- `llm_usage_thresholds`: only run LLM when diff size < N, or only for certain directories.
- `required_controls_by_risk`: evolve into full policy response mapping.

## 4. Execution model

### 4.1 Triggering events
Minimum set:
- `pull_request.opened`
- `pull_request.edited`
- `pull_request.synchronize`

Optional (future): `pull_request.reopened`, review events, etc.

### 4.2 Snapshot and evaluation key
A run must evaluate a stable snapshot to avoid reading inconsistent PR inputs.

**Snapshot inputs (MVP):**
- `head_sha`
- `pr_title`
- `pr_body`
- `changed_files[]` (paths + basic stats)
- `policy_version`

**Evaluation key (recommended):**
- `repo_full_name`
- `pr_number`
- `head_sha`
- `pr_body_sha256`
- `policy_version`

This ensures:
- New commits (new `head_sha`) create a new evaluation.
- Body-only edits (same `head_sha`, different `pr_body_sha256`) create a new evaluation.

### 4.3 Idempotency rule
If a run exists for the evaluation key, the system should treat the webhook as a no-op (or update the existing Check Run idempotently).

### 4.4 Result binding
All published results must include the evaluated `head_sha` and `pr_body_sha256` in the output, so staleness is auditable and visible.

## 5. LangGraph workflow (MVP)

### 5.1 High-level flow
```mermaid
flowchart TD
  A[Webhook Ingest] --> B[Fetch PR evidence]
  B --> C[Persist Snapshot]
  C --> D[Check ticket key in PR title]
  D -->|missing| X[Publish ACTION_REQUIRED: MISSING_TICKET_NUMBER]
  D -->|present| E[Load policy.yaml + compute policy risk]
  E --> F[Parse PR template: user risk + backout text]
  F --> G[LLM diff risk (optional Phase 1+)]
  G --> H[Compute system risk]
  H --> I{User risk matches system risk?}
  I -->|no| Y[Publish ACTION_REQUIRED: MISMATCH_RISK_LEVEL]
  I -->|yes| J{System risk is HIGH?}
  J -->|no| Z[Publish COMPLIANT]
  J -->|yes| K{Backout plan present?}
  K -->|no| R[Publish ACTION_REQUIRED: MISSING_BACKOUT_PLAN]
  K -->|yes| L[LLM validate backout plan (Phase 2+)]
  L -->|fail| S[Publish ACTION_REQUIRED: MISMATCH_BACKOUT_PLAN]
  L -->|pass| Z[Publish COMPLIANT]
```

### 5.2 State object (LangGraph)
Minimum fields required in graph state:
- `repo_full_name`, `pr_number`
- `head_sha`
- `pr_title`, `pr_body`
- `pr_body_sha256`
- `changed_files[]` (paths + stats)
- `policy_version`
- `user_risk`
- `policy_risk`
- `llm_risk` (default LOW in Phase 0)
- `system_risk`
- `backout_text` (may be empty)
- `status` and `reason_codes[]`

### 5.3 Node contracts (MVP)

#### Node: `fetch_pr_evidence`
**Input:** PR identity and event payload

**Actions:**
- Fetch PR title/body/head SHA
- Fetch changed files list (paths; optionally patches)
- Compute `pr_body_sha256`

**Failure:** set `ERROR` with `GITHUB_API_FAILED`.

#### Node: `persist_snapshot`
**Actions:**
- Persist immutable snapshot keyed by evaluation key

**Notes:** Run idempotently (insert-or-ignore by unique key).

#### Node: `check_ticket_key`
**Actions:**
- Use `jira_key_regex` to match ticket key in PR title

**If missing:** set `ACTION_REQUIRED` with `MISSING_TICKET_NUMBER`.

#### Node: `policy_risk_from_paths`
**Actions:**
- Load `policy.yaml` (cache by repo + policy_version)
- Match changed files against `high_risk_paths`

**Output:** `policy_risk`.

#### Node: `parse_pr_template`
**Actions:**
- Extract `user_risk` from checkboxes
- Extract `backout_text`

#### Node: `llm_diff_risk` (Phase 1+)
**Actions:**
- Classify diff risk as LOW/HIGH with strict JSON output

#### Node: `reconcile_and_route`
**Actions:**
- Compute `system_risk = max(policy_risk, llm_risk)`
- If mismatch with user risk: `ACTION_REQUIRED` with `MISMATCH_RISK_LEVEL`
- If system risk LOW: `COMPLIANT`
- If system risk HIGH: require backout plan presence

#### Node: `llm_validate_backout_plan` (Phase 2+)
**Actions:**
- Validate the backout plan against the change context
- Output pass/fail + missing elements

#### Node: `publish_check_run`
**Actions:**
- Upsert GitHub Check Run on `head_sha`
- Include status, reason codes, and short remediation guidance


#### Node: `llm_diff_risk` (Phase 1+)
**Goal:** classify the diff content into `LOW|HIGH` only.

**Input:**
- selected diff content (bounded)
- changed files list and diff stats

**Output:** `llm_risk` and a short rationale.

**Failure:** set `ERROR` with `LLM_CALL_FAILED`.

#### Node: `compute_system_risk`
**Actions:**
- `system_risk = max(policy_risk, llm_risk)`

#### Node: `compare_user_vs_system_risk`
**If mismatch:** set `ACTION_REQUIRED` with `MISMATCH_RISK_LEVEL`.

#### Node: `backout_plan_presence_check`
**Condition:** only executed when `system_risk == HIGH`.

**Rule:** if `backout_text` is empty/whitespace, set `ACTION_REQUIRED` with `MISSING_BACKOUT_PLAN`.

#### Node: `llm_backout_plan_validate` (Phase 2+)
**Goal:** check plan completeness and fit with the change. Must not invent operational commands.

**If fail:** set `ACTION_REQUIRED` with `MISMATCH_BACKOUT_PLAN`.

#### Node: `publish_check_run`
**Actions:**
- Create or update a GitHub Check Run on `head_sha`
- Include: status, reason codes, and evaluated snapshot identifiers (`head_sha`, `pr_body_sha256`, `policy_version`)

**Notes:** keep output deterministic and succinct.


## 6. Persistence model (minimal MVP)

### 6.1 Design principles
- Separate immutable snapshots from mutable "current status" projection.
- Persist enough history to debug and to demonstrate correctness, without a full append-only audit ledger.

### 6.2 Tables (minimal)

#### `pull_request`
- Key: `(repo_full_name, pr_number)`
- Stores stable identity and basic metadata.

#### `pr_snapshot` (immutable)
- Key: `(pr_id, head_sha, pr_body_sha256, policy_version)`
- Stores:
  - `head_sha`, `pr_title`, `pr_body_sha256`
  - `changed_files` summary (paths + stats)
  - extracted `user_risk` and `backout_text_hash` (optional; `backout_text` may be stored if small)

#### `evaluation_run`
- Key: `evaluation_key` (unique)
- Stores:
  - start/end timestamps
  - computed `policy_risk`, `llm_risk`, `system_risk`
  - final status + reason codes
  - LLM model/prompt versions when used

#### `run_state` (mutable projection)
- Key: `(repo_full_name, pr_number)`
- Stores the latest known status for dashboard display:
  - `latest_evaluation_key`
  - `status` and `reason_codes`
  - `system_risk`
  - `updated_at`

### 6.3 Checkpointing (optional in MVP)
If you expect long LLM calls or rate limits, store a lightweight checkpoint in `evaluation_run.state_json` so replays can resume.


## 7. Concurrency and staleness handling (Check Runs)

### 7.1 The core problem
A PR can change while an evaluation is executing:
- New commit(s) (head SHA changes)
- PR body edit (risk/backout text changes)

If the system publishes results computed against old inputs, it can mislead reviewers.

### 7.2 Strategy (recommended)
1) **Evaluate a snapshot**: run logic only over the captured `head_sha` and `pr_body_sha256`.
2) **Bind outputs to the snapshot**: always publish the evaluated `head_sha` and `pr_body_sha256` in the check output.
3) **Detect staleness at the end**: before publishing, re-fetch current PR title/body/head SHA and recompute hashes:
   - If `head_sha` changed: mark the run as `STALE` internally and skip publishing (or publish only as informational on the old commit). A new webhook should trigger a new run for the new SHA.
   - If `pr_body_sha256` changed but `head_sha` is the same: mark as `STALE` and re-run (the edited webhook should exist, but do not rely on timing).

### 7.3 Check Run publishing rules
- **Create/update Check Runs on the evaluated `head_sha` only.**
- If a run becomes stale, set the Check Run conclusion to `neutral` (or do not publish) with a message:
  - "Stale result: PR changed during evaluation. A new run will evaluate the latest PR content." 
- Use the `external_id` field (or your DB correlation key) to store the evaluation key so updates are idempotent.

### 7.4 Optional cancellation optimization
If you want to reduce wasted LLM calls:
- When a newer run starts for the same PR identity, set a `cancel_requested=true` flag on older runs.
- Each node checks the flag between external calls (GitHub/LLM) and short-circuits.


## 8. LLM usage (phased)

### 8.1 Phase 1: diff risk classifier (LOW/HIGH)
**Purpose:** detect business-logic-impact changes that are not captured by path-based policy rules.

**Constraints:**
- Must return only `LOW` or `HIGH`.
- Must emit strict JSON.
- Must operate on bounded diff evidence (avoid large PR costs).

**Suggested output schema:**
```json
{
  "llm_risk": "LOW|HIGH",
  "rationale": "string",
  "confidence": "LOW|MEDIUM|HIGH"
}
```

### 8.2 Phase 2: backout plan validation
**Purpose:** evaluate plan completeness and fit with change.

**Suggested output schema:**
```json
{
  "quality": "PASS|FAIL",
  "missing_elements": ["string"],
  "mismatch_reasons": ["string"],
  "confidence": "LOW|MEDIUM|HIGH"
}
```

**Safety posture:** the model should assess the plan, not generate operational commands or secrets.

### 8.3 Future: Greptile/Sourcegraph enrichment
Treat enrichment output as contextual evidence to improve LLM grounding, not as the sole basis for deterministic outcomes.


## 9. Delivery plan (phases)

### Phase 0 — Deterministic MVP (recommended first portfolio increment)
Deliver:
- Webhook ingress + signature verification
- Snapshot + evaluation key + idempotency
- Ticket key check in PR title
- Policy risk from file paths via `policy.yaml`
- PR template parser (risk + backout extraction)
- Risk mismatch + backout presence gating
- GitHub Check Run publishing (and optional PR comment)

### Phase 1 — LLM diff risk (business logic impact)
Deliver:
- `llm_diff_risk` node with strict JSON schema + caching
- `system_risk = max(policy_risk, llm_risk)`
- Cost controls: sample diff, file caps, and prompt/version identifiers

### Phase 2 — LLM backout plan validation
Deliver:
- `llm_backout_plan_validate` node
- Structured remediation feedback in Check Run output

### Phase 3 — Audit trail (deferred)
Deliver:
- Append-only audit_event ledger and evidence storage
- Stronger UI/dashboard projections

### Phase 4 — Greptile enrichment + Jira alignment (deferred)
Deliver:
- Context enrichment tool integration
- Jira semantic alignment checks (explicitly out of current scope)


## 10. Acceptance criteria (MVP)
1) PR without ticket key in title results in `ACTION_REQUIRED` with `MISSING_TICKET_NUMBER`.
2) PR where user risk differs from system risk results in `ACTION_REQUIRED` with `MISMATCH_RISK_LEVEL`.
3) HIGH risk PR without backout text results in `ACTION_REQUIRED` with `MISSING_BACKOUT_PLAN`.
4) If PR changes mid-run (body or head SHA), system marks run stale and does not publish a misleading Check Run on the latest state.
5) Duplicate webhook deliveries do not create duplicate evaluations for the same evaluation key.

## 11. Portfolio positioning (why this is a strong LangGraph demo)

This project demonstrates practical agentic application engineering, even in Phase 0:
- Orchestration as a graph with conditional routing and clear node contracts.
- Policy-as-code (versioned) + deterministic decisioning.
- Snapshotting and idempotency (real production integration concerns).
- Structured outputs and stable reason codes suitable for automation.

To strengthen the portfolio narrative:
- Show the PR lifecycle: open PR → check run fails → edit PR template → re-evaluation passes.
- Highlight evolution: deterministic first, then LLM risk, then LLM backout validation.
- Emphasize engineering rigor: staleness handling, cost controls, and reproducibility.

