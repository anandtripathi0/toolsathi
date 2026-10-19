#!/usr/bin/env bash
# No reset, force-push, file deletion or automatic web-app reload.
set -Eeuo pipefail
umask 077
PROJECT=/home/anandtrip22/toolsathi
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ "$(id -un)" == anandtrip22 ]] || fail 'Use the existing anandtrip22 account Bash console.'
[[ -d "$PROJECT" && ! -L "$PROJECT" ]] || fail "Expected the existing checkout at $PROJECT."
cd -- "$PROJECT"
[[ "$(pwd -P)" == "$PROJECT" && "$(git rev-parse --show-toplevel)" == "$PROJECT" ]] || fail 'Expected the exact project checkout without symlinks.'
[[ "$(git branch --show-current)" == main ]] || fail 'Updates require main; preserve local work before switching.'
case "$(git remote get-url origin)" in
    https://github.com/anandtripathi0/toolsathi|https://github.com/anandtripathi0/toolsathi.git) ;;
    *) fail 'Unexpected origin. Inspect it before updating.' ;;
esac
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || fail 'Tracked local changes are present. Preserve/review them first.'
git fetch --no-tags origin main
git merge-base --is-ancestor HEAD FETCH_HEAD || fail 'Local commits are not an ancestor of GitHub main. Review divergence; nothing was reset.'
# Ignored runtime files (especially SQLite) must not be overwritten by an update.
git merge --ff-only --no-overwrite-ignore FETCH_HEAD
bash "$PROJECT/scripts/deploy_pythonanywhere.sh"
