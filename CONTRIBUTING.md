# Contributing

Bug reports, focused improvements and documentation fixes are welcome. Open an issue before starting a large feature so we can agree on scope.

1. Fork the repository and create a branch from `main`.
2. Follow the [build-it-yourself guide](docs/BUILD-YOUR-OWN.md) to install build dependencies.
3. Make a focused change. Preserve existing skill files and installation policies.
4. Run `python -m unittest discover -s tests -v` and `npm run check`.
5. For service or packaging changes, rebuild the helper and run `python scripts/smoke_sidecar.py`. For UI changes, check the actual desktop window.
6. Open a pull request describing the behavior, verification and any platform you could not test.

Tests use temporary libraries. Do not test destructive operations against personal skills. Do not commit login credentials, generated caches, local logs, or private skill content.

Runtime Python modules live in `src/skilldesk/`. Use relative imports inside this package and qualified imports from tests and developer commands. Keep build/release utilities in `scripts/` and native code in `src-tauri/`. The existing `python scripts/skill_desk.py` command remains a compatible launcher. See [architecture](docs/ARCHITECTURE.md).

The UI uses authored HTML, CSS and ordinary browser scripts in `web/`. Keep JavaScript readable with `npm run format`; `npm run format:check` checks it in CI. These scripts share the browser global scope and their order in `web/app.html` matters. `library.js` holds the base library UI; `sync.js` subscribes to the local catalog after the feature scripts load. Request configuration is injected as JSON by the service, with `<` escaped before HTML insertion.

Edit shared app appearance in `web/theme.css` and `web/theme.js`, then run `python scripts/sync_ui_assets.py`. The marked blocks embedded in app/native windows are generated and checked in CI. The separate website owns its own theme copy and never participates in the app build.

Do not add website source, deployment configuration, private exports, or local skill folders to this repository. `npm run check` verifies the app boundary as well as versions, theme synchronization, and formatting. Unit tests use disposable libraries; [browser checks](docs/LOCAL-TESTING.md) use synthetic agent responses.

Contributions are provided under the MIT license. Preserve third-party attribution and licenses. We do not require a contributor license agreement.
