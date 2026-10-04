# Application architecture

This repository contains the desktop application and its local service. It needs no website checkout or hosted marketing service to build or run.

| Path | Responsibility |
| --- | --- |
| `src/skilldesk/skill_desk.py` | CLI, local HTTP routes, catalog and per-request UI configuration |
| `src/skilldesk/` | Providers, library operations, drafts, transactions, durable state, discovery and sharing |
| `scripts/` | Build, smoke, version, repository boundary, release and maintenance commands |
| `scripts/skill_desk.py` | Compatibility launcher; also the PyInstaller entry point |
| `web/app.html` | Authored application template; empty skill-data bootstrap; ordered script loading |
| `web/library.js`, `web/sync.js` | Base library view and local catalog subscription |
| `web/*.js`, `web/*.css` | Readable authored feature and theme source; no JavaScript minification step |
| `web/collections/` | Reviewed pinned third-party skill packages and provenance catalog used offline |
| `web/walkthrough/`, `assets/` | App walkthrough and application icon assets |
| `desktop/` | Native launcher/updater templates, including generated shared theme blocks |
| `src-tauri/` | Rust application wrapper, updater, platform bundle configuration and vendored glib patch |
| `tests/` | Unit contracts, security/state regressions, synthetic browser/native fixtures |
| `docs/` | Contributor, architecture, release and user documentation |

## Source and build products

Compressed JavaScript in the previous checkout was authored source, not a recoverable bundle with a separate source map. It is now formatted and the main library script is extracted from HTML. There is no bundler dependency. Python modules form a package with relative imports; tests import the same package rather than loading duplicate top-level modules.

`python scripts/sync_ui_assets.py` generates marked theme blocks only in the app and native templates. Edit `web/theme.css` and `web/theme.js`, not those blocks. `npm run format` formats authored scripts/CSS. `npm run check` verifies versions, package imports, the app/website boundary, formatting and theme blocks.

`npm run build` checks the boundary, synchronizes themes, and freezes the service. `npm run desktop:build` then compiles/packages Tauri. `dist/`, `build/`, generated PyInstaller specs, `src-tauri/binaries/`, `src-tauri/target/` and `src-tauri/gen/` are ignored build products. The vendored glib source, packaged skill collections, icons and licences are deliberate tracked runtime/build inputs, not arbitrary output to discard.

For source-only execution, keep the checkout intact and run `python scripts/skill_desk.py`, or `PYTHONPATH=src python -m skilldesk`. This is a checkout-based application, not a standalone Python wheel: its UI resources live at the repository root and are explicitly included in the frozen bundle.

## Compatibility

The application identifier `ca.lgraham.skilldesk`, product/executable names, version, update endpoint/key, data/cache paths, preference formats, archive/recovery behavior and existing licence files are unchanged. The historical `/demo` local URL redirects to `/`; no marketing content is bundled. The static website has its own repository and theme source.

No installed user libraries, preferences, drafts, state or running production app need migration for this source reorganization. Test with disposable state as documented in [local testing](LOCAL-TESTING.md). Rebuild the sidecar after runtime or UI changes; a Rust rebuild alone does not refresh frozen Python/web resources.
