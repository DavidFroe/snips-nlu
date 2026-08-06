#!/usr/bin/env bash
#
# Build and install the two Rust-backed dependencies of snips-nlu for
# Python 3.9+.
#
# Why this script exists
# ----------------------
# snips-nlu-utils and snips-nlu-parsers only ship wheels up to cp38, so on a
# modern interpreter pip falls back to building them from source. Two things
# break there:
#
#   1. snips-nlu-utils does not declare setuptools-rust as a build dependency,
#      so the isolated build environment lacks it.
#   2. snips-nlu-parsers pulls in gazetteer-entity-parser 0.8.0 and
#      rustling-ontology 0.19.3, both of which require rmp-serde 0.13 —
#      every 0.13.x release has since been yanked from crates.io, so cargo
#      cannot resolve a version at all. rmp-serde 1.x builds and behaves
#      identically for the way these crates use it.
#
# Requirements: a Rust toolchain (rustup) and the target virtualenv active.

set -euo pipefail

BUILD_DIR="${BUILD_DIR:-$(pwd)/build-deps}"
PYTHON="${PYTHON:-python}"

PARSERS_TAG="0.4.3"
GAZETTEER_TAG="0.8.0"
RUSTLING_TAG="0.19.3"

mkdir -p "$BUILD_DIR"

echo "==> Build prerequisites"
"$PYTHON" -m pip install --upgrade pip setuptools setuptools-rust wheel

echo "==> snips-nlu-utils"
"$PYTHON" -m pip install --no-build-isolation "snips-nlu-utils>=0.9,<0.10"

echo "==> gazetteer-entity-parser $GAZETTEER_TAG (rmp-serde 0.13 -> 1)"
if [ ! -d "$BUILD_DIR/gazetteer-entity-parser" ]; then
    git clone --depth 1 --branch "$GAZETTEER_TAG" \
        https://github.com/snipsco/gazetteer-entity-parser \
        "$BUILD_DIR/gazetteer-entity-parser"
fi
sed -i 's/^rmp-serde = "0.13"/rmp-serde = "1"/' \
    "$BUILD_DIR/gazetteer-entity-parser/Cargo.toml"

echo "==> rustling-ontology $RUSTLING_TAG (rmp-serde 0.14 -> 1)"
if [ ! -d "$BUILD_DIR/rustling-ontology" ]; then
    git clone --depth 1 --branch "$RUSTLING_TAG" \
        https://github.com/snipsco/rustling-ontology \
        "$BUILD_DIR/rustling-ontology"
fi
sed -i 's/^rmp-serde = "0.14"/rmp-serde = "1"/g' \
    "$BUILD_DIR/rustling-ontology/Cargo.toml"

echo "==> snips-nlu-parsers $PARSERS_TAG"
if [ ! -d "$BUILD_DIR/snips-nlu-parsers" ]; then
    git clone --depth 1 --branch "$PARSERS_TAG" \
        https://github.com/snipsco/snips-nlu-parsers \
        "$BUILD_DIR/snips-nlu-parsers"
fi

# The patched crates have to be redirected in both the workspace root and the
# python ffi crate, which cargo builds as a standalone workspace member.
for manifest in "$BUILD_DIR/snips-nlu-parsers/Cargo.toml" \
                "$BUILD_DIR/snips-nlu-parsers/python/ffi/Cargo.toml"; do
    if ! grep -q "^\[patch\." "$manifest"; then
        cat >> "$manifest" <<EOF

[patch."https://github.com/snipsco/gazetteer-entity-parser"]
gazetteer-entity-parser = { path = "$BUILD_DIR/gazetteer-entity-parser" }

[patch."https://github.com/snipsco/rustling-ontology"]
rustling-ontology = { path = "$BUILD_DIR/rustling-ontology" }
EOF
    fi
done

find "$BUILD_DIR" -name Cargo.lock -delete
"$PYTHON" -m pip install --no-build-isolation "$BUILD_DIR/snips-nlu-parsers/python"

echo
echo "==> Done. Checking the installation:"
"$PYTHON" -c "from snips_nlu_parsers import BuiltinEntityParser; \
print(BuiltinEntityParser.build('de').parse('morgen um drei'))"
