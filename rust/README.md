# Vendored Rust dependencies

snips-nlu talks to two Rust libraries through cFFI: `snips-nlu-utils`
(tokenization, string handling) and `snips-nlu-parsers` (builtin entities,
dates, numbers, gazetteers). Neither ships wheels past cp38, and neither
builds from its published source on a current toolchain. The four crates they
need are vendored here with the minimal changes that make them build.

They are kept as plain directories rather than submodules or separate forks:
upstream has not moved since 2019, so there is nothing to merge back, and one
clone that builds is worth more than four repositories that have to be checked
out in the right order.

| directory | upstream | pinned at | change |
|---|---|---|---|
| `snips-nlu-utils` | snipsco/snips-nlu-utils | 0.9.1 | `python/pyproject.toml` added |
| `snips-nlu-parsers` | snipsco/snips-nlu-parsers | 0.4.3 | `python/pyproject.toml` added, `[patch]` sections in `Cargo.toml` |
| `gazetteer-entity-parser` | snipsco/gazetteer-entity-parser | 0.8.0 | `rmp-serde` 0.13 → 1 |
| `rustling-ontology` | snipsco/rustling-ontology | 0.19.3 | `rmp-serde` 0.14 → 1 |

## The two things that were broken

**Yanked crate.** `gazetteer-entity-parser` and `rustling-ontology` both
require `rmp-serde ^0.13`, and every 0.13.x release has since been yanked from
crates.io. Cargo cannot select a version at all, so the build fails during
dependency resolution — before it reaches any Python or Rust code. `rmp-serde`
1.x is API-compatible for the way these two crates use it (`from_read`,
`Serializer`, `encode::write`), so both were bumped. The 0.14 line, which
would have been the smaller step, does not compile against current `rmp`:
it calls `rmp::decode::read_data_*` functions that no longer exist.

The `[patch]` sections at the bottom of `snips-nlu-parsers/Cargo.toml`
redirect every reference to the vendored copies, including the ones reached
indirectly through the upstream git dependencies. They also point
`snips-nlu-parsers` and its ffi-macros at this tree, so the code compiled into
the Python extension is the code in this directory — not a second copy fetched
from GitHub.

**Missing build dependency.** Both `setup.py` files import `setuptools_rust`,
but neither declares it, so pip's isolated build environment does not have it
and the build dies on `ModuleNotFoundError`. The added `pyproject.toml` files
declare the build backend and its requirements, which is all that was needed.

## Building

From the repository root, with the target virtualenv active:

```bash
./tools/build_rust_deps.sh
```

This is not an offline build: cargo still fetches `snips-nlu-ontology`,
`rustling`, `snips-utils-rs` and the crates.io dependencies. Only the four
crates that needed changes are vendored.
