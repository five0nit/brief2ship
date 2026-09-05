# Native Windows PowerShell quickstart

Use PowerShell with Python 3.11, 3.12 or 3.13 installed. Start in the existing
Brief2Ship source checkout containing `pyproject.toml`. The working tree's v0.7.0
is unreleased; the published v0.6.2 tag does not contain the new v2 decisions.
Do not install a future tag or assume that PyPI publication has happened.

## Isolated source install

The Python launcher selects a native interpreter. Substitute an installed
supported version for `-3.13` when needed. No virtual-environment activation or
PowerShell execution-policy change is needed.

```powershell
py -3.13 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }

& .\.venv\Scripts\python.exe -m pip install .
if ($LASTEXITCODE -ne 0) { throw "Brief2Ship installation failed" }

& .\.venv\Scripts\brief2ship.exe doctor
if ($LASTEXITCODE -ne 0) { throw "doctor failed" }

& .\.venv\Scripts\brief2ship.exe --version
if ($LASTEXITCODE -ne 0) { throw "version check failed" }

& .\.venv\Scripts\python.exe scripts\validate-release.py
if ($LASTEXITCODE -ne 0) { throw "source release validation failed" }
```

If the `py` launcher is absent, use the full path to an installed Python 3.11–3.13
executable for the first command. `python.exe` must be a real interpreter, not the
Microsoft Store alias. The remaining commands explicitly target `.venv`.

## Local-only discovery round trip

```powershell
$output = Join-Path $env:TEMP ("brief2ship-discovery-" + [guid]::NewGuid().ToString("N"))
& .\.venv\Scripts\brief2ship.exe discover "brief2ship" `
  --local (Get-Location).Path --sources local `
  --per-source 3 --limit 3 --inspect-top 1 --summary --output $output
$discoveryExit = $LASTEXITCODE
if ($discoveryExit -notin @(0, 5)) { throw "Discovery failed: $discoveryExit" }

$receipt = Get-Content -LiteralPath (Join-Path $output "discovery.json") -Raw | ConvertFrom-Json
$receipt | Select-Object schema_version, discovery_status, decision_status, overall_recommendation
$receipt.evaluated_candidates | Select-Object name, recommendation, recommendation_status
```

The canonical checkout's free-form copyright notice produces an expected
`inconclusive` result with exit `5` and an explicit license-review check. Its MIT
body is recognized, but surrounding prose is not automatically approved.

Exit 5 is a successful receipt write but an **inconclusive decision**. Read its
`incomplete_reasons`; never turn it into permission for a clean build.
Exit 0 can still be a provisional reuse lead with required checks outstanding.
Use a fresh output directory for every run.

## Installed-package smoke

```powershell
& .\.venv\Scripts\python.exe scripts\smoke-installed.py
if ($LASTEXITCODE -ne 0) { throw "Installed-package smoke failed" }
```

This verifies the import resolves to the installed distribution, exercises the
installed CLI and checks a real local discovery receipt. Source validation and
installed-package validation are separate checks.

## Boundaries

- This route uses native Windows Python and `.venv\Scripts\*.exe` entrypoints;
  it does not require or claim WSL.
- Local static discovery does not execute candidate code or require network.
- These commands do not enable or claim native Windows Bubblewrap candidate tests.
- The optional Trafilatura adapter is not installed or validated by this core-only
  quickstart. Optional adapter CI is a separate gate.
- See [decision/schema migration](code-discovery.md) before updating automation.
