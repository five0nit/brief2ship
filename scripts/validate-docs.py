#!/usr/bin/env python3
"""Fast semantic documentation checks for Brief2Ship's public contract."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = {
    "README.md": [
        "One repo-search skill",
        "--local",
        "Report / Document",
        "The 4 default lanes",
        "docs/report-document-lane.md",
        "docs/free-scraping.md",
        "docs/code-discovery.md",
        "brief2ship scrape",
        "brief2ship crawl",
        "brief2ship discover",
        "--total-timeout",
        "robots.txt required",
        "zero-paid-API",
        "heygen-com/hyperframes",
    ],
    "CHANGELOG.md": [
        "0.6.1",
        "0.6.0",
        "0.5.1",
        "0.5.0",
        "brief2ship discover",
        "0.4.0",
        "zero-paid-API",
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
        "free scraping",
    ],
    "docs/free-scraping.md": [
        "robots.txt behavior",
        "Network safety",
        "Explicit non-features",
        "Receipt schema",
        "DNS-rebinding",
    ],
    "docs/code-discovery.md": [
        "Local workspaces",
        "--sources local",
        "contributor",
        "GitHub",
        "PyPI",
        "npm",
        "crates.io",
        "Hugging Face",
        "OSV",
        "Scoring contract",
        "Repository inspection",
        "Sandboxed tests",
        "brief2ship-discovery-v1",
        "Private results are filtered",
        "--total-timeout",
        "evidence coverage",
        "selective-reuse",
        "reject",
        "use-as-library",
        "build-clean",
    ],
    "docs/releases/v0.5.0-code-discovery-receipt.md": [
        "LOCAL RELEASE CANDIDATE",
        "101 tests passed",
        "brief2ship-discovery-v1",
        "Clean Linux install",
        "No push",
    ],
    "docs/releases/v0.5.1-code-discovery-receipt.md": [
        "LOCAL RELEASE CANDIDATE",
        "PUBLICATION NO-GO",
        "116 tests passed",
        "brief2ship-bwrap-v2",
        "No push",
    ],
    "docs/releases/v0.6.1-single-search-skill-receipt.md": [
        "Brief2Ship v0.6.1",
        "Python 3.13",
        "check_hostname",
        "Hyperframes",
        "141 tests passed",
    ],
    "docs/releases/v0.6.0-single-search-skill-receipt.md": [
        "PUBLIC RELEASE — VERIFIED",
        "sole repository/package/local-workspace search and base-selection skill",
        "138 tests passed",
        "local/brief2ship selective-reuse inspected",
        "Protected cutover completed",
        "v0.6.0",
    ],
    "docs/releases/v0.4.0-free-scraping-receipt.md": [
        "Local release candidate",
        "Ran 65 tests",
        "No known vulnerabilities found",
        "Publication gates remaining",
    ],
    "docs/examples.md": [
        "Example 4 — Report / Document lane",
        "source-first intake",
        "findings table",
        "Example 5 — Free source collection",
        "raw-response SHA-256",
        "Example 6 — Find reusable code",
        "brief2ship discover",
    ],
    "templates/report-request-template.md": [
        "Report / Document Request Template",
        "reader / audience",
        "decision / action",
        "Sources to use",
        "Optional public-web collection",
    ],
    "templates/report-receipt-template.md": [
        "Report Receipt",
        "Sources used",
        "Formatting and render checks",
        "Known gaps",
    ],
    "templates/scrape-receipt-template.md": [
        "Scrape Receipt",
        "robots.txt checked",
        "SHA-256",
        "crawl stayed same-origin",
    ],
    "skills/brief2ship/SKILL.md": [
        "sole repo-search skill",
        "--local",
        "agent-code entropy gate",
        "exact repository/base",
        "The 4 lanes",
        "Report / Document",
        "Free public-web scraping",
        "Mandatory safety rules",
        "Required scrape receipt",
        "Required code-discovery workflow",
        "github,pypi,npm,crates,huggingface",
        "formatting/render checks",
        "heygen-com/hyperframes",
    ],
}

# Local release receipts carry hashes of finished artifacts and stay outside the
# sdist to avoid self-referential archive hashes. A Git source checkout must
# contain every declared receipt; an extracted sdist validates without them.
if not (ROOT / ".git").exists():
    for _release_receipt in tuple(
        path for path in checks if path.startswith("docs/releases/")
    ):
        checks.pop(_release_receipt)

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
