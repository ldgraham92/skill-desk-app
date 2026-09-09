# Releasing Skill-Desk

1. Merge the intended changes into `main` and wait for the Desktop installers workflow to pass on every platform.
2. Set the same version in `package.json`, `src-tauri/Cargo.toml` and `src-tauri/tauri.conf.json`. Refresh the npm and Cargo lockfiles.
3. Write `docs/releases/vVERSION.md`, update CHANGELOG.md, and run `python scripts/check_version.py`.
4. Commit and push the version changes. After CI passes, create and push an annotated tag: `git tag -a vVERSION -m "Skill-Desk vVERSION"` then `git push origin vVERSION`.
5. The tag workflow builds Windows, macOS and Linux installers, tests their bundled helpers, uploads workflow artifacts, and publishes a GitHub Release with all installers and SHA256SUMS.txt.
6. Download the release installer and test it on its target OS. Confirm the logo, launch, CLI discovery, a temporary library, favorites and shutdown.

All 0.x tags and tags containing a hyphen are published as prereleases. A failed platform prevents publication. Do not move a published tag or silently replace an installer; use a new version for fixes. The publication script refuses to overwrite an existing release. If publication was interrupted, inspect any draft and uploaded assets before recovering it through GitHub.

Installers are not code-signed yet. Release publication is not automatic updating inside the app. Signing credentials and an updater need a separate setup.
