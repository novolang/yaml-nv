#!/usr/bin/env bash
# tools/yaml_test_suite.sh — the yaml-test-suite corpus through this
# package.
#
# Usage: bash tools/yaml_test_suite.sh <yaml-test-suite data directory> [--emit]
#
# The data branch of https://github.com/yaml/yaml-test-suite holds one
# directory per case: `in.yaml`, `in.json` with the documents as JSON
# when they have a JSON form, and `error` when the input is not valid
# YAML.  This builds tests/yts_harness.nv inside a copy of the package,
# parses every case, and reports: a valid case whose documents differ
# from `in.json`, a valid case refused, and an invalid case accepted.
# With `--emit` it also writes tests/yts_tests.nv from the cases that
# agree.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$(cd "$HERE/.." && pwd)"
NOVO="${NOVO:-$HOME/.novo/bin/novo}"
DATA="$1"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/yaml-nv-yts.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
cp -r "$PKG" "$WORK/pkg"
rm -rf "$WORK/pkg/_novo"
cp "$PKG/tests/yts_harness.nv" "$WORK/pkg/src/yts_harness.nv"
printf '\n[[bin]]\nname = "yts-harness"\npath = "src/yts_harness.nv"\n' >>"$WORK/pkg/novo.toml"
( cd "$WORK/pkg" && NOVO_LEAK_CHECK=0 timeout 900 "$NOVO" pkg build --bin yts-harness ) \
    >"$WORK/build.log" 2>&1 || { echo "the harness did not build"; grep -E 'error' -A3 "$WORK/build.log" | head -20; exit 1; }
if [ "${2:-}" = "--emit" ]; then
  python3 "$HERE/yaml_test_suite.py" "$DATA" "$WORK" "$WORK/pkg/yts-harness" "$PKG"
else
  python3 "$HERE/yaml_test_suite.py" "$DATA" "$WORK" "$WORK/pkg/yts-harness"
fi
