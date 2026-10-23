#!/usr/bin/env python3
"""Fail a CI job unless a reviewer report ends in an explicit APPROVE.

Usage:
    python verdict_check.py <report-file>
    some-reviewer ... | python verdict_check.py -

Prints verdict_line(report) and exits with exit_code(find_verdict(report)):
    0  APPROVE            (the only exit that lets a job pass)
    3  REQUEST_CHANGES
    4  AMBIGUOUS, or no verdict stated
    1  could not read the report (missing file, not valid UTF-8)
    2  usage error

Byte fidelity is the whole point. find_verdict() judges APPROVE on the RAW
reply: the sentinel must be the only one AND sit on the final non-blank raw
line. So this CLI reads BYTES and decodes them strictly as UTF-8, with no
strip, no CRLF->LF translation (no text mode, no universal newlines) and no
re-encoding. A lone CR before the sentinel is APPROVE on the raw bytes and
AMBIGUOUS once normalised, so normalising here would change the verdict.
Invalid UTF-8 is an error (exit 1), never a guess.

Used by action.yml in this repo; stdlib only. Callers that hash the report
(for a signed receipt, say) should hash the same bytes this reads.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verdict_contract import exit_code, find_verdict, verdict_line  # noqa: E402


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        if argv[1] == "-":
            raw = sys.stdin.buffer.read()
        else:
            with open(argv[1], "rb") as f:
                raw = f.read()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print("verdict_check: cannot read report: %s" % e, file=sys.stderr)
        return 1
    print(verdict_line(text))
    return exit_code(find_verdict(text))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
