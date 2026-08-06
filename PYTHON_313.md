# snips-nlu on Python 3.13

This fork brings snips-nlu 0.20.2 (released 15.01.2020, last supported
interpreter cp38) up to Python 3.13. Upstream is unmaintained, so everything
below was changed in the fork itself.

Verified on Python 3.13.14 with numpy 2.5.1, scipy 1.18.0, scikit-learn 1.9.0:
**346 tests pass, including the cross-validation integration test.**

---

## Installing

The two Rust-backed dependencies have no wheels beyond cp38 and their source
builds fail for reasons unrelated to Python, so they need to be built first:

```bash
python -m venv .venv && source .venv/bin/activate
./tools/build_rust_deps.sh          # needs a Rust toolchain (rustup)
pip install -e ".[test]"
snips-nlu download en               # and/or: download-all-languages
```

### Why the Rust dependencies need a script

* `snips-nlu-utils` does not declare `setuptools-rust` as a build dependency,
  so pip's isolated build environment cannot find it. Building with
  `--no-build-isolation` after installing `setuptools-rust` works.
* `snips-nlu-parsers` depends on `gazetteer-entity-parser` 0.8.0 and
  `rustling-ontology` 0.19.3, both requiring `rmp-serde ^0.13`. **Every 0.13.x
  release has since been yanked from crates.io**, so cargo cannot resolve a
  version at all — the build fails before it reaches any Python code. The
  script bumps both crates to `rmp-serde 1` (the API these crates use is
  unchanged) and redirects them with `[patch]` sections.

The patched crates live in `build-deps/`. If you want a reproducible install
without the script, fork those three Snips repos with the `rmp-serde` bump
applied and depend on the forks directly.

---

## What changed in the Python code

### Python 2 compatibility layer removed

`future`, `builtins` and `past` are gone (`future` itself no longer imports on
3.12+, because it uses the removed `imp` module):

* `iteritems`/`itervalues`/`iterkeys`/`view*` → the plain dict methods
* `with_metaclass(ABCMeta, Base)` → `class X(Base, metaclass=ABCMeta)`
* `future.utils.text_type` → `str`; `newstr`/`newbytes` branches dropped
* `from __future__ import ...` removed throughout
* `mock` → `unittest.mock` in the test suite

### Removed and moved standard library APIs

* `pkg_resources` (removed with setuptools 81) → `importlib.metadata`
  in `snips_nlu/common/utils.py:is_package`
* `imp` (removed in 3.12) — reached only via `future`, gone with it
* the `importlib.invalidate_caches` ImportError fallback for Python 2 dropped

### scikit-learn 1.x

* `SGDClassifier(loss="log")` → `loss="log_loss"` (renamed in 1.1,
  removed in 1.3)
* `compute_class_weight("balanced", classes, y)` → keyword-only
  `compute_class_weight("balanced", classes=..., y=...)`, and `classes` must
  be an array rather than a `range`
* `TfidfVectorizer._tfidf._idf_diag` no longer exists: sklearn 1.6 replaced
  the sparse diagonal matrix with a plain `idf_` array. Both
  `TfidfVectorizer.limit_vocabulary` and its `from_path` now go through the
  public `idf_` setter (`_set_sklearn_idf` in
  `snips_nlu/intent_classifier/featurizer.py`), which works on either layout.
  Re-fitting `idf_` after limiting the vocabulary also requires updating
  `n_features_in_`, otherwise `transform` rejects the narrower matrix.
* `TfidfVectorizer(tokenizer=...)` now warns unless `token_pattern=None`

The persisted model format is unchanged — an engine trained with this fork and
one trained with 0.20.2 serialize to the same JSON.

### Dependency pins

| package | before | now |
|---|---|---|
| numpy | `>=1.15,<2.0` | `>=1.26` |
| scipy | `>=1.0,<2.0` | `>=1.11,<2.0` |
| scikit-learn | `>=0.21.1,<0.23` | `>=1.4` |
| sklearn-crfsuite | `>=0.3.6,<0.4` | `>=0.5` |
| pyaml | `>=17.0,<20.0` | `>=17.0` |
| num2words | `>=0.5.6,<0.6` | `>=0.5.6` |
| future, enum34, funcsigs, pathlib | pinned | removed |
| checksumdir (test) | `~=1.1.6` | `>=1.3` (1.1.x imports `pkg_resources`) |
| mock (test) | `>=2.0,<3.0` | removed, `unittest.mock` is used |
| pylint (test) | `<2` | removed |

---

## Two upstream services that are no longer intact

### Gazetteer entity downloads need an opt-in

`resources.snips.ai` still serves the gazetteer entity data (HTTP 200), but it
is a CloudFront distribution whose custom-domain certificate was never
renewed: it presents a `*.cloudfront.net` certificate, so TLS verification
fails on a hostname mismatch. Certificate verification stays **on** by
default. To fetch the data anyway:

```bash
SNIPS_NLU_INSECURE_DOWNLOAD=1 snips-nlu download-entity snips/musicArtist fr
```

This disables certificate verification for that download (and passes
`--trusted-host` to pip). The connection is unauthenticated — you are
downloading code from a host you cannot verify. Check what you got before
using it. Only the gazetteer entities are affected; the language resources
come from GitHub releases and verify normally.

The `#egg=name==version` fragments in the download URLs were also dropped —
modern pip rejects them.

### snips-nlu-metrics installs but must skip its own pins

Version 0.15.0 is already Python 3 only and runs on this stack, but its
published metadata pins `numpy<2`, `joblib<0.15` and `scikit-learn<0.23`,
which would downgrade the installation. Hence:

```bash
pip install --no-deps "snips-nlu-metrics>=0.15"
```

The `metrics` extra in `setup.py` is intentionally left empty for this reason.
