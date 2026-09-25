# glib 0.18.5 security backport

GTK 0.18 and WebKitGTK 2.0 require glib's 0.18 Rust API. The published 0.18.5 crate contains RUSTSEC-2024-0429 / GHSA-wrw7-89jp-8q8g. This copy applies only the upstream fix to `src/variant_iter.rs`: make the out-parameter pointer mutable and pass `&mut p` to `g_variant_get_child`.

- Original archive: https://static.crates.io/crates/glib/glib-0.18.5.crate
- Original archive SHA-256: `233daaf6e83ae6a12a52055f568f9d7cf4671dabb78ff9560ab6da230ce00ee5`
- Upstream fix: https://github.com/gtk-rs/gtk-rs-core/pull/1343
- Upstream fix commit: `b5a4071e439bef2b5eea76c3aa25e5ae84839e34`
- Advisory: https://rustsec.org/advisories/RUSTSEC-2024-0429.html
- License: MIT, preserved in `glib-0.18.5/LICENSE`.

The version remains 0.18.5. This is a source backport, not the upstream 0.20 API and not a scanner exception. No audit ignore or alert dismissal is added. The application-level Cargo patch replaces all registry references to glib 0.18.5.

`python scripts/check_glib_backport.py` verifies the complete vendored tree against the checksum-pinned original archive plus exactly the upstream two-line patch, then checks Linux Cargo metadata for one patched glib package and no remaining registry copy. CI also runs `cargo test --locked --release --manifest-path src-tauri/Cargo.toml --test glib_variant_iter` on Linux. The release profile matters because the invalid immutable out-parameter can fail under optimization.

Remove this override and directory when the Linux dependency chain accepts an upstream fixed release. Refresh the lock, verify no affected glib remains, and rerun the optimized regression and Linux application checks. Keep this backport narrowly scoped; any further source changes require a new provenance review.
