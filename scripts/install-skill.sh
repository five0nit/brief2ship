#!/usr/bin/env bash
set -euo pipefail

PROFILE_DIR="${HOME}/.hermes/profiles/generalist1"
SKILL_DIR="${PROFILE_DIR}/skills/software-development/shipproof"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/skills/shipproof"

mkdir -p "${SKILL_DIR}"
cp "${SRC_DIR}/SKILL.md" "${SKILL_DIR}/SKILL.md"

echo "Installed shipproof to ${SKILL_DIR}"
echo "Start a fresh Hermes session or use /reload-skills if needed."
