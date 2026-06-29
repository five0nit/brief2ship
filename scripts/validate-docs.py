#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = {
    "README.md": [
        "Report / Document",
        "The 4 default lanes",
        "docs/report-document-lane.md",
        "the 4 default lanes",
    ],
    "CHANGELOG.md": [
        "0.3.0",
        "Report / Document as a fourth default lane",
    ],
    "docs/lanes.md": [
        "## 4. Report / Document",
        "executive summaries",
        "reader outcome over writer cleverness",
    ],
    "docs/report-document-lane.md": [
        "Best-practice flow",
        "Source-first intake",
        "Evidence gate",
        "Formatting pass",
        "Report receipt",
        "Ship gate for reports",
    ],
    "docs/examples.md": [
        "Example 4 — Report / Document lane",
        "source-first intake",
        "findings table",
    ],
    "templates/report-request-template.md": [
        "Report / Document Request Template",
        "reader / audience",
        "decision / action",
        "Sources to use",
    ],
    "templates/report-receipt-template.md": [
        "Report Receipt",
        "Sources used",
        "Formatting and render checks",
        "Known gaps",
    ],
    "skills/brief2ship/SKILL.md": [
        "The 4 lanes",
        "Report / Document",
        "formatting/render checks",
    ],
}

missing = []
for rel, needles in checks.items():
    path = ROOT / rel
    if not path.exists():
        missing.append(f"missing file: {rel}")
        continue
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            missing.append(f"{rel}: missing {needle!r}")

if missing:
    print("Brief2Ship docs validation failed:")
    for item in missing:
        print(f"- {item}")
    raise SystemExit(1)

print("Brief2Ship docs validation passed")
