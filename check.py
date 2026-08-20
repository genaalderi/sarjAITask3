#!/usr/bin/env python3
"""
nuzul-agent-check - conformance checker for the Nuzul voice agent.

The rules live in rules/*.yaml, not in here. This file only ships the rules
and a call transcript to a model, asks for a verdict per rule with turn
citations, and prints the result. Exit 1 if anything failed, so it can gate
a release.

  cp .env.example .env   and add your key   (GROQ_API_KEY or ANTHROPIC_API_KEY)
  python check.py transcripts/bk-1043.yaml
"""

import argparse, json, os, sys, yaml, requests
from dotenv import load_dotenv

PROMPT = """You are a QA conformance evaluator. You are given the rules a voice
agent must follow and a transcript of one call. Decide, for each rule, whether
the call obeyed it.

RULES
{rules}

TRANSCRIPT (turn number, speaker, text)
{turns}

Return JSON only, no prose:
{{"verdicts": [{{"id": "<rule id>", "status": "PASS|FAIL|SKIP",
                "turns": [<turn numbers that evidence this>],
                "detail": "<one sentence, naming what happened and where>"}}]}}

Rules for you:
- One verdict per rule id, in the order given.
- SKIP only when the rule cannot apply (e.g. no discount was ever discussed).
- Every FAIL must cite at least one turn number. If you cannot cite a turn, it
  is not a FAIL.
- Judge only what the transcript shows. Do not assume unstated good behaviour.
"""


def ask_model(prompt):
    if os.getenv("GROQ_API_KEY"):
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"]},
            json={"model": os.getenv("MODEL", "openai/gpt-oss-120b"),
                  "temperature": 0, "response_format": {"type": "json_object"},
                  "messages": [{"role": "user", "content": prompt}]}, timeout=90)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    if os.getenv("ANTHROPIC_API_KEY"):
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                     "anthropic-version": "2023-06-01"},
            json={"model": os.getenv("MODEL", "claude-sonnet-4-6"), "max_tokens": 2000,
                  "temperature": 0,
                  "messages": [{"role": "user", "content": prompt}]}, timeout=90)
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    sys.exit("Set GROQ_API_KEY or ANTHROPIC_API_KEY, or pass --replay <file>.")


def main():
    load_dotenv()      # reads .env if present; real env vars win
    p = argparse.ArgumentParser()
    p.add_argument("transcript")
    p.add_argument("--rules", default="rules/nuzul-v14.yaml")
    p.add_argument("--replay", help="use a saved model response instead of calling the API")
    p.add_argument("--save", help="write the model response here, for replay")
    a = p.parse_args()

    rules = yaml.safe_load(open(a.rules, encoding="utf-8"))
    call = yaml.safe_load(open(a.transcript, encoding="utf-8"))
    by_id = {r["id"]: r for r in rules["rules"]}

    if a.replay:
        raw = open(a.replay, encoding="utf-8").read()
    else:
        raw = ask_model(PROMPT.format(
            rules="\n".join('%s [%s] "%s"' % (r["id"], r["severity"], r["prompt_line"])
                            for r in rules["rules"]),
            turns="\n".join("%d %s: %s" % (t["n"], t["speaker"], t["text"])
                            for t in call["turns"])))
        if a.save:
            open(a.save, "w", encoding="utf-8").write(raw)

    result = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    text = {t["n"]: t["text"] for t in call["turns"]}

    print("\nNUZUL AGENT CONFORMANCE   rules: %s   call: %s\n%s"
          % (rules["version"], a.transcript, "=" * 74))
    failed = 0
    for v in sorted(result["verdicts"], key=lambda v: v["status"] != "FAIL"):
        rule = by_id.get(v["id"], {})
        print("\n%-5s %-9s %-9s %s" % (v["status"], rule.get("severity", "").upper(),
                                       v["id"], rule.get("title", "")))
        if v["status"] == "FAIL":
            failed += 1
            print('      Rule: "%s"' % rule.get("prompt_line", ""))
        print("      %s" % v["detail"])
        for n in v.get("turns", []):
            print("      turn %-3s %s" % (n, text.get(n, "")))

    print("\n%s\n%d failed\n" % ("=" * 74, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
