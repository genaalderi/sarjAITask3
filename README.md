# nuzul-agent-check

Conformance checker for the Nuzul reservations voice agent. Give it a call
transcript; it reports which of the agent's own rules that call broke, and cites
the turn where each violation happened.

## Why this tool, why this problem

The booking API and the console are code, and code can be tested. The voice
agent is a prompt — edited every release by whoever is tuning the agent's
behaviour, with nothing in the pipeline checking that the deployed agent still
obeys its own instructions.


## The design

The rules are the artifact

`rules/nuzul-v14.yaml` holds one entry per obligation in the deployed prompt,
each carrying the prompt line it came from. `check.py` ships those
rules and the transcript to a model, asks for one verdict per rule with turn
citations, and prints the result.

When the prompt changes for Release 15, you edit the YAML, not the code.

## What it checks

Seven rules, from the production prompt excerpt:

| Rule | Obligation | Severity |
|---|---|---|
| NUZ-R01 | No name unless the caller gave it on this call | high |
| NUZ-R02 | Read dates back and get an explicit yes before saving | critical |
| NUZ-R03 | Re-confirm the whole booking after any change | high |
| NUZ-R04 | No total before room type and nights are confirmed | medium |
| NUZ-R05 | Never end the call without reading back the reference | high |
| NUZ-R06 | Najdi only, no Modern Standard Arabic | medium |
| NUZ-R07 | Discounts limited to the knowledge base | high |

## Running it

Set the GROQ_API_KEY variable in an .env

The key is read from `.env` (gitignored), a free key can be obtained at console.groq.com

```
pip install -r requirements.txt
python check.py transcripts/bk-1043.yaml
python check.py transcripts/clean-call.yaml
```

## Limitations

- **The verdicts come from a model, so they are not identical run to run.**
- **It reads transcripts, not production.** This is an after-the-fact judge you
  point at a batch of calls before shipping, not a runtime guardrail.
- **It does not transcribe.** Audio in, text out is somebody else's problem.

## Improvements that can be made

**Cross-layer checks.** Give the tool the booking record the system actually stored and compare
it to what the caller agreed to on the call. On BK-1043 that surfaces something
no single layer shows: the caller moved checkout to the 20th at turn 15, the
agent replied `تم التعديل`, and the stored record still holds the 12th — the
change was acknowledged and never applied.

**Batch mode.** Run it over every call in a release window rather than one at a
time and report violation rates per rule, which turns it from a debugging tool
into a release signal.

**Rules diff mode.** When the prompt is edited, re-run the call archive against
both rule versions, so a prompt edit that quietly drops an obligation is visible
before it ships.