"""Fit release notes on stdin into a character limit, cutting at whole lines.

Invoked by publish-stores/write-release-notes.sh, for Google Play's 500
character limit. Usage: fit_release_notes.py LIMIT < notes > fitted

Notes that already fit pass through unchanged. Otherwise whole lines are kept
while they fit, then a final "…and more" line says the list goes on, so a
store never shows a bullet cut off mid-word. Trailing blank lines and a
dangling heading with nothing under it are dropped before the marker.
"""

import sys

MORE = "…and more"


def fit(notes: str, limit: int) -> str:
    notes = notes.replace("\r\n", "\n").strip()
    if len(notes) <= limit:
        return notes

    budget = limit - len("\n" + MORE)
    kept: list[str] = []
    for line in notes.split("\n"):
        candidate = "\n".join([*kept, line])
        if len(candidate) > budget:
            break
        kept.append(line)

    while kept and (not kept[-1].strip() or kept[-1].lstrip().startswith("#")):
        kept.pop()
    return "\n".join([*kept, MORE]) if kept else MORE


if __name__ == "__main__":
    sys.stdout.write(fit(sys.stdin.read(), int(sys.argv[1])) + "\n")
