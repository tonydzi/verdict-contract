#!/usr/bin/env python3
"""Check a review prompt BEFORE it is sent: PROMPT_RULE is in it verbatim, and no second
verdict format is.

The parser stays strict on purpose (see Known limits in the README): a localized label
such as `URTEIL: REQUEST_CHANGES` is not a verdict and exits 4. This guard works on the
other side of the contract. It keeps the sender from handing the model a second format
to copy, whether in the instruction or in the quoted material.

Usage:
    python3 examples/prompt_guard.py prompt.txt
    build-my-prompt | python3 examples/prompt_guard.py -
    python3 examples/prompt_guard.py prompt.txt --pattern 'LGTM' --pattern 'SHIP IT'

Exit codes:
    0  the prompt may be sent
    3  blocked -- PROMPT_RULE is missing or altered, or a look-alike pattern is in it
    1  could not read the prompt (missing file, not valid UTF-8)
    2  usage error, or a --pattern that is not a regular expression

The whole prompt is searched, line by line, material included: a label inside a quoted
diff can lead the model just as well. A false block costs a rewrite of the prompt, a
mixed prompt costs the verdict. Each --pattern is a regular expression; given at least
once, the patterns replace the default list.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verdict_contract import PROMPT_RULE  # noqa: E402

# Verdict formats other than the sentinel: localized labels and an older review format.
# The label words without a colon stay case-sensitive, so ordinary prose passes.
LOOKALIKES = [
    ("===URTEIL===", r"(?i)=+\s*URTEIL\s*=+"),
    ("URTEIL:", r"(?i)\bURTEIL\s*:"),
    ("FREIGABE", r"\bFREIGABE\b"),
    ("AENDERUNGEN", r"\b(?:AENDERUNGEN|ÄNDERUNGEN)\b"),
    ("VERDICT: ACCEPT|REJECT|FOLLOWUP", r"(?i)VERDICT\s*:\s*(?:ACCEPT|REJECT|FOLLOWUP)\b"),
]


def findings(prompt, patterns=LOOKALIKES):
    """-> list of reasons this prompt must not be sent; empty means it may.

    `patterns` is a list of (name, regex) pairs. Matching is per line, so no pattern
    can reach across a newline."""
    out = []
    if PROMPT_RULE not in prompt:
        out.append("PROMPT_RULE is not in the prompt verbatim (import it, never retype it)")
    lines = prompt.splitlines()
    for name, regex in patterns:
        rx = re.compile(regex)
        hits = [str(i + 1) for i, line in enumerate(lines) if rx.search(line)]
        if hits:
            out.append("look-alike %s on line %s" % (name, ", ".join(hits[:5])))
    return out


def main(argv):
    args, patterns = argv[1:], []
    while "--pattern" in args:
        i = args.index("--pattern")
        if i + 1 >= len(args):
            print(__doc__, file=sys.stderr)
            return 2
        patterns.append((args[i + 1], args[i + 1]))
        del args[i:i + 2]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        if args[0] == "-":
            raw = sys.stdin.buffer.read()
        else:
            with open(args[0], "rb") as f:
                raw = f.read()
        prompt = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print("prompt_guard: cannot read prompt: %s" % e, file=sys.stderr)
        return 1
    try:
        found = findings(prompt, patterns or LOOKALIKES)
    except (re.error, OverflowError) as e:
        print("prompt_guard: --pattern is not a regular expression: %s" % e, file=sys.stderr)
        return 2
    for reason in found:
        print(reason)
    if found:
        print("PROMPT: blocked !!  <- fix the prompt before it is sent")
        return 3
    print("PROMPT: ok to send")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
