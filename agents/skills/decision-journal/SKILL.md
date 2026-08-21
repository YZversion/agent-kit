---
name: decision-journal
description: >-
  Captures consequential decisions before outcomes are known, appends outcome
  reviews without rewriting history, surfaces due reviews, and extracts
  reusable rule updates from a local decision journal. Use when the user
  invokes $decision-journal, asks to record or log a decision, create a
  decision card, review a previous decision, compare decision quality with
  outcome quality, or inspect recurring judgment patterns. Compose with
  decide-and-deliver and relevant domain Skills. Do not use for ordinary task
  logs, hidden chain-of-thought, automatic recording of every conversation, or
  retrieval, eval, and answer-quality audit ledgers.
---

# Decision Journal

Preserve a falsifiable snapshot of a consequential decision, then close the
loop with observed outcomes and a reusable rule update. Keep this workflow
independent from decision advice: other Skills may help make the decision;
this Skill records and reviews it.

## Non-negotiable boundaries

- Require explicit intent to record, review, list, or summarize journal data.
  Do not silently journal ordinary conversations.
- Record concise reasons, evidence, assumptions, alternatives, predictions,
  and invalidation criteria. Never request or expose hidden chain-of-thought.
- Capture the decision before its outcome is known. Do not rewrite a decision
  event after learning the result; append a review or correction event.
- Separate decision quality from outcome quality. Good decisions can have bad
  outcomes, and bad decisions can get lucky.
- Keep journal data local and private by default. Store pointers or hashes
  instead of proprietary source text, credentials, hosts, customer names, or
  private eval contents.
- Do not infer a durable personal rule from one result. Require at least five
  reviewed decisions or an explicit user instruction before claiming a
  recurring pattern.

## Select the operation

1. **Capture**: create and append a `decision` event when the user wants to
   record a current choice.
2. **Review**: append a `review` event when observable results are available.
3. **Due**: list decisions whose review date has arrived.
4. **Summarize**: report counts and candidate rule updates without treating
   correlation as causation.
5. **Correct**: append a `correction` event for a factual recording mistake;
   never edit an existing ledger line.

## Resolve the script path

`{SKILL_DIR}` in the commands below is the directory holding this `SKILL.md`.
The Skill loader reports it as "Base directory for this skill". Typical values:

| Install | `{SKILL_DIR}` |
| --- | --- |
| Global (Claude Code, all projects) | `%USERPROFILE%\.claude\skills\decision-journal` |
| Project (cross-tool canonical layer) | `<repo>\.agents\skills\decision-journal` |

Never hardcode one of these into an answer; resolve it from the loaded Skill
directory so the same workflow runs from either install.

Read [references/record-schema.md](references/record-schema.md) before creating,
reviewing, or correcting an event. Use
`scripts/decision_journal.py` for templates, validation, concurrency-safe
append, due-date checks, and summaries.

## Default storage

Let the script resolve the default ledger. In a Git repository it stores data
under the common Git directory so Agents in separate worktrees share one
repo-scoped journal while Git never tracks it. Outside Git it falls back to
`.agent-work/decision-journal/decision-ledger.jsonl`.

Pass `--ledger <path>` only when the user explicitly chooses another local
location. Never commit a populated journal.

## Capture a decision

1. Confirm that the choice is consequential, repeatable, uncertain, or has an
   observable delayed result. If none apply, give the user a concise card in
   chat and do not persist unless explicitly requested.
2. Create a draft:

   ```powershell
   python {SKILL_DIR}\scripts\decision_journal.py template --type decision --output .agent-work\decision-journal\draft.json
   ```

3. Fill every required field using facts available at decision time:
   - distinguish evidence from assumptions;
   - include at least one real alternative;
   - make the expected outcome observable and time-bound;
   - record a calibrated confidence from `0.0` to `1.0`;
   - state evidence that would invalidate the decision;
   - choose a concrete review date.
4. Validate and append:

   ```powershell
   python {SKILL_DIR}\scripts\decision_journal.py check-event --event .agent-work\decision-journal\draft.json
   python {SKILL_DIR}\scripts\decision_journal.py append --event .agent-work\decision-journal\draft.json
   ```

5. Return the `decision_id`, review date, ledger path, and any field based on an
   inference rather than user-confirmed information.

## Review an outcome

1. Load only the relevant decision event; do not reinterpret it using facts
   learned later.
2. Create a review draft with the exact `decision_id`:

   ```powershell
   python {SKILL_DIR}\scripts\decision_journal.py template --type review --decision-id <ID> --output .agent-work\decision-journal\review.json
   ```

3. Record observed signals and their sources. Score `decision_quality` and
   `outcome_quality` separately as `good`, `mixed`, `poor`, or `uncertain`.
4. Attribute causes conservatively among judgment, execution, external change,
   luck, or insufficient evidence.
5. Keep, modify, retire, or decline to update a rule. Use `none` when one case
   does not justify a rule.
6. Validate and append the review. Report what changed and what remains
   unknown.

## Check due reviews and summarize

```powershell
python {SKILL_DIR}\scripts\decision_journal.py due
python {SKILL_DIR}\scripts\decision_journal.py summary
python {SKILL_DIR}\scripts\decision_journal.py validate
```

Treat summary output as navigation, not a conclusion. Read the underlying
records before asserting a recurring bias or promoting a rule.

## Trigger examples

**Should trigger**

1. “使用 `$decision-journal` 记录我今天选择先完成五条 gold 的决定。”
2. “给这个架构选择建立决策卡，并在两周后复盘。”
3. “复盘 D-20260817-abc123；结果不错，但我想区分判断和运气。”
4. “列出已经到期的决策，并总结至少五次复盘中重复出现的偏差。”

**Should not trigger**

1. “帮我判断 A 和 B 哪个更好。” → use `decide-and-deliver`; do not
   persist unless the user also asks to record it.
2. “记录本轮检索调参的 keep/revert 指标。” → use
   `evidence-retrieval-loop`.
3. “根据 QA 反馈修复回答并写审计日志。” → use `audit-answer-loop`.
