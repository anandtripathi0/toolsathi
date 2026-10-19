#!/usr/bin/env bash
# Run in the existing anandtrip22 PythonAnywhere Bash console. Never source .env.
set -Eeuo pipefail
umask 077
trap 'printf "Deployment stopped at line %s. Read the preceding error; no web-app reload was requested.\n" "$LINENO" >&2' ERR

PROJECT=/home/anandtrip22/toolsathi
ENV_FILE=/home/anandtrip22/.toolsathi.env
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[[ "$(id -un)" == anandtrip22 ]] || fail 'Use the existing anandtrip22 account Bash console.'
[[ -d "$PROJECT" && ! -L "$PROJECT" ]] || fail "Expected a real project directory at $PROJECT."
cd -- "$PROJECT"
[[ "$(pwd -P)" == "$PROJECT" ]] || fail 'The project path must not traverse symlinks.'
[[ "$(git rev-parse --show-toplevel)" == "$PROJECT" ]] || fail 'The project must be its own Git checkout.'
[[ "$(git branch --show-current)" == main ]] || fail 'Deploy only the main branch; inspect local branches first.'
case "$(git remote get-url origin)" in
    https://github.com/anandtripathi0/toolsathi|https://github.com/anandtripathi0/toolsathi.git) ;;
    *) fail 'origin must be https://github.com/anandtripathi0/toolsathi.git.' ;;
esac
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || fail 'Tracked changes are present. Preserve/review them before deployment.'

PYTHON=''
for candidate in python3.13 python3.12 python3.14 python3.15 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 12))' >/dev/null 2>&1; then
        PYTHON="$(command -v "$candidate")"
        break
    fi
done
[[ -n "$PYTHON" ]] || fail 'No Python 3.12+ is available. Check the account system image; do not downgrade Django.'

EXISTING_VENV=0
if [[ -e .venv || -L .venv ]]; then
    [[ -d .venv && ! -L .venv && -x .venv/bin/python && -f .venv/pyvenv.cfg ]] || fail 'Existing .venv is not a usable private virtualenv; inspect it without deleting it.'
    .venv/bin/python -c 'import sys; raise SystemExit(sys.version_info < (3, 12) or sys.prefix == sys.base_prefix)' || fail 'Existing .venv needs Python 3.12+; preserve it and plan an explicit upgrade.'
    EXISTING_VENV=1
    PYTHON="$PROJECT/.venv/bin/python"
fi

printf 'Selected Python: '
"$PYTHON" --version
"$PYTHON" scripts/pythonanywhere_support.py disk-check --existing-venv "$EXISTING_VENV"
"$PYTHON" scripts/pythonanywhere_support.py init-env
export TOOLSATHI_ENV_FILE="$ENV_FILE"
"$PYTHON" scripts/pythonanywhere_support.py validate-env
if [[ "$EXISTING_VENV" == 0 ]]; then
    "$PYTHON" -m venv "$PROJECT/.venv"
fi
PYTHON="$PROJECT/.venv/bin/python"
export PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
"$PYTHON" -m pip install --no-cache-dir --only-binary=:all: --requirement requirements.txt
"$PYTHON" -m pip check
"$PYTHON" scripts/pythonanywhere_support.py settings
"$PYTHON" manage.py check --deploy --fail-level WARNING
"$PYTHON" manage.py migrate --noinput
"$PYTHON" manage.py collectstatic --noinput
"$PYTHON" scripts/pythonanywhere_support.py static-permissions
"$PYTHON" manage.py migrate --check
"$PYTHON" scripts/pythonanywhere_support.py verify
"$PYTHON" scripts/pythonanywhere_support.py disk-check --existing-venv 1 --after-install
printf '\nLocal deployment checks passed. Configure/reload the existing Web app and verify the public HTTPS website.\n'
printf 'Virtualenv: %s/.venv\n' "$PROJECT"
"$PYTHON" -c 'import django, sys; print("Web tab Python: %s.%s; Django: %s" % (*sys.version_info[:2], django.get_version()))'
printf 'Updates: cd %s && bash scripts/update_pythonanywhere.sh\n' "$PROJECT"
