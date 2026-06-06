# Decisions

## 2026-06-06 - Delivery Channel

Decision: use Gmail SMTP first.

Reason: the user uses email frequently, and the assignment allows email or Telegram. Gmail SMTP is fast to set up and nearly free for one daily recipient.

Alternatives considered:

- Telegram: simple bot delivery, but less aligned with the user's workflow.
- Resend: cleaner production email API, but requires verifying a custom domain to send beyond the account owner's email.

## 2026-06-06 - LLM Provider

Decision: use Gemini 2.5 Flash-Lite as the default LLM.

Reason: it is cheap, easy to explain in the memo, and has a straightforward API path for a take-home prototype.

Alternatives considered:

- DeepSeek V4 Flash: strong raw price story and should remain an optional provider.
- Provider-neutral first: useful later, but adds setup complexity before the dry run proves the framework.

## 2026-06-06 - GitHub Timing

Decision: initialize local git after the scaffold exists, then create/push the GitHub remote after the first local dry run.

Reason: the project should be locally coherent before external setup and secrets.

## 2026-06-06 - First Run Mode

Decision: start with sample data mode.

Reason: this proves output structure, word limits, chart rendering, logs, and delivery shape before real API integration.

## 2026-06-06 - Learning And Interaction Notes

Decision: keep durable assignment-facing state in tracked control docs, and keep temporary learning/session notes in ignored `.worklog/`.

Reason: the user wants explanations and continuity during the learning process, but wants interaction-derived material removed before the final assignment handoff.

Working rule:

- `PLAN.md` records the public resume point and next tasks.
- `DECISIONS.md` records durable choices and alternatives.
- `.worklog/session_notes.md` records private session breadcrumbs.
- `.worklog/learning_notes.md` records plain-language concepts explained during development.
- `.worklog/` is ignored by git and should be deleted before final submission.
