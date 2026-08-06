#!/usr/bin/env bash
#
# Build and install the two Rust-backed Python packages that snips-nlu needs:
# snips-nlu-utils and snips-nlu-parsers. Both are built from the sources
# vendored under rust/ — see rust/README.md for what was changed and why.
#
# Requirements: a Rust toolchain (rustup) and the target virtualenv active.
# The cargo build still fetches a handful of upstream crates from GitHub, so
# this is not an offline build.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python}"

echo "==> Build prerequisites"
"$PYTHON" -m pip install --upgrade pip setuptools setuptools-rust wheel

echo "==> snips-nlu-utils"
"$PYTHON" -m pip install "$REPO_ROOT/rust/snips-nlu-utils/python"

echo "==> snips-nlu-parsers (this one takes several minutes)"
"$PYTHON" -m pip install "$REPO_ROOT/rust/snips-nlu-parsers/python"

echo
echo "==> Done. Checking the installation:"
"$PYTHON" -c "
from snips_nlu_utils import tokenize_light
from snips_nlu_parsers import BuiltinEntityParser
print(tokenize_light('Machst du mir drei Kaffee', 'de'))
print(BuiltinEntityParser.build('de').parse('morgen um drei'))
"
