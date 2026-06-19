#!/usr/bin/env bash
# Polish #8.1 — chore(infra) git-hooks installer
# --------------------------------------------------------------------
# Copies tools/git-hooks/pre-push into .git/hooks/pre-push and chmod +x.
# Idempotent: safe to re-run; overwrites any existing pre-push sample
# or previously installed hook.
# --------------------------------------------------------------------
set -eo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_DIR="${REPO_ROOT}/.git/hooks"

if [ ! -d "${HOOKS_DIR}" ]; then
    echo "ERROR: ${HOOKS_DIR} not found. Are you inside a git repository?" >&2
    exit 1
fi

cp -f "${REPO_ROOT}/tools/git-hooks/pre-push" "${HOOKS_DIR}/pre-push"
chmod +x "${HOOKS_DIR}/pre-push"
echo "[INSTALL-HOOKS] Installed ${HOOKS_DIR}/pre-push (chmod +x)."
echo "[INSTALL-HOOKS] Bypass with: git push --no-verify origin main"
exit 0
