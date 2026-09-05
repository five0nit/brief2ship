#!/usr/bin/env python3
"""Exercise the installed console entrypoint, not an editable source import."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _installed_entrypoint() -> Path:
    suffix = sysconfig.get_config_var("EXE") or ""
    return Path(sysconfig.get_path("scripts")) / ("brief2ship" + suffix)


def main() -> int:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="brief2ship-installed-smoke-") as temporary:
        identity = subprocess.run(
            [sys.executable, "-c", "import brief2ship,json; print(json.dumps({'version':brief2ship.__version__,'file':brief2ship.__file__}))"],
            cwd=temporary, env=environment, text=True, capture_output=True, check=True,
        )
        package = json.loads(identity.stdout)
        if Path(package["file"]).resolve().is_relative_to(ROOT / "src"):
            raise RuntimeError("installed smoke imported the source checkout instead of a distribution")
        entrypoint = _installed_entrypoint()
        version = subprocess.run([str(entrypoint), "--version"], cwd=temporary, env=environment,
                                 text=True, capture_output=True, check=True)
        if package["version"] not in version.stdout:
            raise RuntimeError("console entrypoint and imported package versions disagree")
        result = subprocess.run(
            [str(entrypoint), "discover", "brief2ship", "--local", str(ROOT),
             "--sources", "local", "--inspect-top", "1", "--summary", "--output", str(Path(temporary) / "receipt")],
            cwd=temporary, env=environment, text=True, capture_output=True,
        )
        summary = json.loads(result.stdout)
        if result.returncode != 5 or summary["decision"] != "inconclusive":
            raise RuntimeError(f"installed local round-trip skipped the copyright-review gate: {summary}")
        receipt = json.loads(Path(summary["receipts"]["json"]).read_text(encoding="utf-8"))
        if not receipt["evaluated_candidates"] or not receipt["inspection_decisions"]:
            raise RuntimeError("installed round-trip omitted evaluation or inspection evidence")
        own = next(c for c in receipt["evaluated_candidates"] if Path(c["local_path"]).resolve() == ROOT)
        if own["license_body_match"] != "MIT" or not own["license_review_required"] or own["normalized_license"] is not None:
            raise RuntimeError("installed package lost license recognition or failed to keep it separate from authority")
        print(json.dumps({"package": package, "entrypoint": str(entrypoint), "decision": summary["decision"],
                          "decision_status": summary["decision_status"], "license_body_match": own["license_body_match"],
                          "schema": receipt["schema_version"], "passed": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
