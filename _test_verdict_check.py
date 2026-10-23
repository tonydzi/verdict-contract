#!/usr/bin/env python3
"""Tests for verdict_check.py: the CLI must hand find_verdict the RAW bytes.

Run:  python3 _test_verdict_check.py     (exit 0 = green)

The byte-fidelity cases are the point. find_verdict's strict layer sees the raw
reply; a CLI that rstrips, or turns CRLF into LF, can flip a verdict. Each such
case compares the CLI against the library on the SAME bytes.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verdict_contract as vc  # noqa: E402

CLI = os.path.join(HERE, "verdict_check.py")
S = "===VERDICT=== "


def run(data, via_stdin=False):
    if via_stdin:
        p = subprocess.run([sys.executable, CLI, "-"], input=data, capture_output=True)
    else:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
        try:
            p = subprocess.run([sys.executable, CLI, f.name], capture_output=True)
        finally:
            os.unlink(f.name)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def lib(data):
    return vc.exit_code(vc.find_verdict(data.decode("utf-8")))


CASES = [
    ("clean final-line APPROVE -> 0", b"ok\n" + (S + "APPROVE").encode() + b"\n", 0),
    ("REQUEST_CHANGES -> 3", b"bug\n" + (S + "REQUEST_CHANGES").encode() + b"\n", 3),
    ("REQUEST_CHANGES mid-report -> 3",
     (S + "REQUEST_CHANGES\nmore text\n").encode(), 3),
    ("repeated APPROVE -> 4", (S + "APPROVE\nx\n" + S + "APPROVE\n").encode(), 4),
    ("non-final APPROVE -> 4", (S + "APPROVE\ntrailing prose\n").encode(), 4),
    ("no verdict -> 4", b"looks fine to me\n", 4),
    ("empty file -> 4", b"", 4),
]


def main():
    fails = []
    for name, data, want in CASES:
        for stdin in (False, True):
            rc, _ = run(data, stdin)
            if rc != want:
                fails.append("%s [%s]: got %s want %s" % (
                    name, "stdin" if stdin else "file", rc, want))
    # Byte fidelity: same bytes in, same verdict as the library, whatever the
    # whitespace. Includes forms where normalising WOULD change the answer.
    base = ("ok\n" + S + "APPROVE").encode()
    fidelity = [
        ("LF end", base + b"\n"),
        ("no trailing newline", base),
        ("trailing blank line", base + b"\n\n"),
        ("CRLF endings", base.replace(b"\n", b"\r\n") + b"\r\n"),
        ("CRLF + blank", base.replace(b"\n", b"\r\n") + b"\r\n\r\n"),
        ("trailing spaces", base + b"   \n"),
        ("lone CR before sentinel", b"ok\r" + (S + "APPROVE").encode() + b"\n"),
        ("lone CR after APPROVE line", base + b"\rmore\n"),
    ]
    for name, data in fidelity:
        want = lib(data)
        for stdin in (False, True):
            rc, _ = run(data, stdin)
            if rc != want:
                fails.append("fidelity %s [%s]: cli %s != lib %s" % (
                    name, "stdin" if stdin else "file", rc, want))
    # Printed line is the library's verdict_line.
    rc, out = run(base + b"\n")
    if vc.verdict_line(base.decode() + "\n") not in out:
        fails.append("stdout lacks verdict_line: %r" % out)
    # Usage / script errors use 1 or 2, never a verdict code.
    for args in ([], ["a", "b"], ["/nonexistent/file"]):
        p = subprocess.run([sys.executable, CLI] + args, capture_output=True)
        if p.returncode not in (1, 2):
            fails.append("args %r -> %s, want 1 or 2" % (args, p.returncode))
    rc, _ = run(b"\xff\xfe bad utf8\n")
    if rc not in (1, 2):
        fails.append("invalid UTF-8 -> %s, want 1 or 2 (never a verdict)" % rc)
    if fails:
        print("FAIL (%d):" % len(fails))
        for f in fails:
            print("  - " + f)
        return 1
    print("OK - %d verdict cases x file/stdin, %d byte-fidelity cases, "
          "usage errors" % (len(CASES), len(fidelity)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
