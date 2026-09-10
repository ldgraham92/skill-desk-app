# Contributing

Bug reports, focused improvements and documentation fixes are welcome. Open an issue before starting a large feature so we can agree on scope.

1. Fork the repository and create a branch from `main`.
2. Follow the [build-it-yourself guide](docs/BUILD-YOUR-OWN.md) to install build dependencies.
3. Make a focused change. Preserve existing skill files and installation policies.
4. Run `python -m unittest discover -s tests -v` and `python scripts/check_version.py`.
5. For service or packaging changes, rebuild the helper and run `python scripts/smoke_sidecar.py`. For UI changes, check the actual desktop window.
6. Open a pull request describing the behavior, verification and any platform you could not test.

Tests use temporary libraries. Do not test destructive operations against personal skills. Do not commit login credentials, generated caches, local logs, or private skill content.

The core service lives in `scripts/`; the desktop wrapper in `src-tauri/`; management UI in `web/`; the standalone demonstration in `marketing/`. The server transforms `web/app.html` into the live reference UI. Root `index.html` is a generated copy of the marketing page. Keep the demo honest about which workflows are simulated.

Edit shared appearance in `web/theme.css` and `web/theme.js`, then run `python scripts/sync_ui_assets.py`. This embeds the assets in the library, demo and native windows so they work offline. CI checks that these copies stay in sync. Verify both themes, reduced motion, narrow layouts and print styles after appearance changes.

Contributions are provided under the MIT license. Preserve third-party attribution and licenses. We do not require a contributor license agreement.
