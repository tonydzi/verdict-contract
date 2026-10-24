#!/usr/bin/env python3
"""Tests for examples/review_gate.py: the verdict must be judged on the reviewer's RAW bytes.

Run:  python3 _test_review_gate.py     (exit 0 = green)

Each case drives review_gate.py with a fake reviewer that emits exact bytes, and compares
the exit status with find_verdict() on the same bytes decoded strictly (no newline
translation), and checks the gate echoes those bytes unchanged. Reading the reply in text
mode turns CRLF and a lone CR into LF first, so what the gate showed and judged was no
longer what the reviewer wrote. (We found no input where that flips the verdict today;
the guarantee is byte identity, so it stays true if the parser changes.)
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verdict_contract as vc  # noqa: E402

GATE = os.path.join(HERE, "examples", "review_gate.py")
S = b"===VERDICT=== "
CASES = {
    "lf approve": b"ok\n" + S + b"APPROVE\n",
    "crlf approve": b"ok\r\n" + S + b"APPROVE\r\n",
    "lone cr before sentinel": b"ok\r" + S + b"APPROVE\n",
    "trailing blank line": b"ok\n" + S + b"APPROVE\n\n",
    "request changes": b"bug\n" + S + b"REQUEST_CHANGES\n",
    "no verdict": b"looks fine\n",
}


def gate(data):
    # the fake reviewer writes the exact bytes; repr() keeps them intact through the shell
    code = "import sys;sys.stdout.buffer.write(%r)" % (data,)
    reviewer = '"%s" -c "%s"' % (sys.executable, code)
    if os.name == "nt":
        reviewer = '"%s" -c "%s"' % (sys.executable, code.replace('"', '\\"'))
    p = subprocess.run([sys.executable, GATE, reviewer],
                       input=b"diff --git a/x b/x\n+y\n", capture_output=True)
    return p.returncode, p.stdout


def main():
    bad = 0
    for name, data in CASES.items():
        want = vc.exit_code(vc.find_verdict(data.decode("utf-8")))
        got, out = gate(data)
        # the gate must show the reviewer's bytes untouched (CRLF and lone CR kept), so a
        # caller that hashes what it printed hashes what the reviewer wrote
        ok = got == want and out.startswith(data)
        bad += not ok
        print("%s %-26s want %d got %d" % ("ok  " if ok else "FAIL", name, want, got))
    got, _ = gate(b"\xff\xfe" + S + b"APPROVE\n")
    ok = got == 1
    bad += not ok
    print("%s %-26s want 1 got %d" % ("ok  " if ok else "FAIL", "invalid utf-8", got))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
