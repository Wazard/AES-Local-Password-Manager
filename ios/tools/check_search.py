"""Runs the shared search cases against the desktop search (core/data_handler).

Each query is checked two ways: in one go, and typed a character at a time
through SearchCache, whose narrowing must give the same answer.
Usage, from the repository root:  python ios/tools/check_search.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from core import data_handler  # noqa: E402


def main():
    with open(os.path.join(ROOT, "ios", "SecureVaultTests", "Fixtures", "search_cases.json"),
              encoding="utf-8") as f:
        spec = json.load(f)
    vault = dict(spec["entries"])
    failures = 0
    for case in spec["cases"]:
        q, want = case["q"], case["expect"]
        direct = data_handler.visible_services(vault, q, "name_asc")
        cache = data_handler.SearchCache()
        for i in range(len(q) + 1):
            typed = cache.services(vault, 1, q[:i], "name_asc")
        if direct != want or typed != want:
            failures += 1
            print("FAIL %r: expected %s, got %s (typed: %s)" % (q, want, direct, typed))
    print("%d of %d search cases pass" % (len(spec["cases"]) - failures, len(spec["cases"])))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
