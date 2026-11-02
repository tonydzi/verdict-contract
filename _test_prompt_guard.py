#!/usr/bin/env python3
"""Tests for examples/prompt_guard.py: a prompt goes out only with PROMPT_RULE verbatim and
without a second verdict format anywhere in it.

Run:  python3 _test_prompt_guard.py     (exit 0 = green)

Each case drives the guard as a separate process on exact bytes, the way a sender would
call it before a review is requested. The control is the prompt the README builds, a task
with PROMPT_RULE as its last block: it must pass, or the guard blocks the very prompt the
contract asks for.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verdict_contract as vc  # noqa: E402

GUARD = os.path.join(HERE, "examples", "prompt_guard.py")
TASK = ("Review the diff below. Report only MED/HIGH issues.\n\n"
        "--- DIFF ---\n+x = compute(y)\n\n")
GOOD = TASK + vc.PROMPT_RULE            # the README's own prompt shape: the rule last


def run(data, extra=(), via_stdin=True):
    if via_stdin:
        p = subprocess.run([sys.executable, GUARD, "-"] + list(extra), input=data,
                           capture_output=True)
    else:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
        try:
            p = subprocess.run([sys.executable, GUARD, f.name] + list(extra),
                               capture_output=True)
        finally:
            os.unlink(f.name)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def planted(line):
    """GOOD with one extra line in the task part, so only that line can be the reason."""
    return (line + "\n" + GOOD).encode("utf-8")


# Labels a model has copied instead of the sentinel, or old formats that invite it.
LOOKALIKE_LINES = [
    "===URTEIL=== REQUEST_CHANGES",
    "URTEIL: REQUEST_CHANGES",
    "Urteil: APPROVE",
    "FREIGABE",
    "AENDERUNGEN",
    "ÄNDERUNGEN",
    "VERDICT: ACCEPT",
    "verdict: reject",
    "VERDICT: FOLLOWUP",
]

CASES = [
    ("the rule as the last block -> 0", GOOD.encode("utf-8"), (), 0),
    ("no rule -> 3", TASK.encode("utf-8"), (), 3),
    ("rule retyped with one word changed -> 3",
     (TASK + vc.PROMPT_RULE.replace("exactly once", "once")).encode("utf-8"), (), 3),
    ("rule with CRLF line ends -> 3",
     (TASK + vc.PROMPT_RULE.replace("\n", "\r\n")).encode("utf-8"), (), 3),
    ("a label inside the quoted diff -> 3",
     GOOD.replace("+x = compute(y)", "+# URTEIL: ok").encode("utf-8"), (), 3),
    ("the word verdict in plain prose -> 0",
     planted("Write the verdict at the very end."), (), 0),
    ("a custom list catches its own label -> 3", planted("LGTM"), ("--pattern", "LGTM"), 3),
    ("a custom list replaces the defaults -> 0", planted("FREIGABE"), ("--pattern", "LGTM"), 0),
    ("a pattern that is no regex -> 2", GOOD.encode("utf-8"), ("--pattern", "("), 2),
    ("a pattern with an oversized repeat -> 2",
     GOOD.encode("utf-8"), ("--pattern", "a{4294967296}"), 2),
    ("invalid UTF-8 -> 1", b"\xff\xfe" + GOOD.encode("utf-8"), (), 1),
] + [("look-alike %r -> 3" % line, planted(line), (), 3) for line in LOOKALIKE_LINES]


def main():
    if not os.path.exists(GUARD):
        print("FAIL: %s does not exist" % os.path.relpath(GUARD, HERE))
        return 1
    fails = []
    for name, data, extra, want in CASES:
        for stdin in (True, False):
            rc, out = run(data, extra, stdin)
            if rc != want:
                fails.append("%s [%s]: got %s want %s %r" % (
                    name, "stdin" if stdin else "file", rc, want, out[-200:]))
    # A finding names the line, so the sender can find what to remove.
    rc, out = run(planted("URTEIL: x"))
    if "line 1" not in out:
        fails.append("the finding does not name line 1: %r" % out)
    # Usage errors use 2, a missing file 1, never 0 or a blocking 3.
    for args in ([], ["a", "b"], ["--pattern"]):
        p = subprocess.run([sys.executable, GUARD] + args, input=b"", capture_output=True)
        if p.returncode != 2:
            fails.append("args %r -> %s, want 2" % (args, p.returncode))
    p = subprocess.run([sys.executable, GUARD, os.path.join(HERE, "no", "such", "prompt")],
                       capture_output=True)
    if p.returncode != 1:
        fails.append("missing file -> %s, want 1" % p.returncode)
    # The example imports the rule; a retyped copy is how the two sides drift apart.
    src = open(GUARD, encoding="utf-8").read()
    if "PROMPT_RULE" not in src or "CRITICAL OUTPUT CONTRACT" in src:
        fails.append("examples/prompt_guard.py must import PROMPT_RULE, not retype it")
    if fails:
        print("FAIL (%d):" % len(fails))
        for f in fails:
            print("  - " + f)
        return 1
    print("OK - %d prompt cases x stdin/file, line number, usage errors, imported rule"
          % len(CASES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
