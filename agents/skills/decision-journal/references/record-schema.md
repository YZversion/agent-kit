# Decision journal event schema

The ledger is strict UTF-8 JSONL. Each line is one immutable event. All events
contain:

- `schema_version`: integer `1`;
- `event_type`: `decision`, `review`, or `correction`;
- `event_id`: unique event identifier;
- `decision_id`: stable identifier shared by a decision and its later events;
- `recorded_at`: timezone-aware ISO-8601 timestamp.

## Decision event

Require:

- `title`: short description of the choice;
- `context`: scope and constraints known at the time;
- `chosen_action`: the committed action;
- `evidence`: one or more `{fact, source}` objects;
- `assumptions`: zero or more `{assumption, confidence, test}` objects;
- `alternatives`: one or more `{option, reason_not_chosen}` objects;
- `expected_outcomes`: one or more `{signal, target, by}` objects;
- `confidence`: overall probability from `0.0` to `1.0` that the expected
  outcome will be achieved;
- `invalidate_if`: one or more observable disconfirming conditions;
- `review_on`: ISO date `YYYY-MM-DD`.

Sources may be repository paths, issue or document IDs, experiment IDs, hashes,
or concise user statements. Do not copy sensitive payloads into the ledger.

## Review event

Require:

- `observed_outcomes`: one or more `{signal, observed, source}` objects;
- `decision_quality`: `good`, `mixed`, `poor`, or `uncertain`;
- `outcome_quality`: `good`, `mixed`, `poor`, or `uncertain`;
- `causes`: one or more of `judgment`, `execution`, `external`, `luck`, or
  `insufficient_evidence`;
- `lesson`: the narrow lesson supported by this result;
- `rule_update`: `{action, rule, rationale}`, where action is `keep`, `modify`,
  `retire`, or `none`;
- `next_review_on`: another ISO date or `null`.

Use `rule_update.action=none` when evidence is insufficient. A successful
outcome does not by itself prove a good decision.

## Correction event

Use only for a recording error, not to improve a prediction after the fact.
Require:

- `corrects_event_id`: existing event identifier;
- `field`: mutable top-level field whose recorded value was wrong;
- `replacement`: corrected value;
- `reason`: why this is a recording correction rather than hindsight editing.

The journal utility applies corrections in ledger order for due-date and summary
views while preserving the original event for auditability. Immutable identity
and type fields cannot be corrected.
