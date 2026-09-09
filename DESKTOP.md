# Skill-Desk desktop

Skill-Desk packages its local service and web interface in a Tauri desktop window. The installer includes Python and the service dependencies. Users only need a signed-in Codex or Claude Code CLI for AI authoring, and Git for repository imports. Browsing and Markdown imports work without an authoring CLI.

## Installation

Windows: download the `Skill-Desk_*_x64-setup.exe` installer from [GitHub Releases](https://github.com/ldgraham92/skill-desk/releases). Install for the current user. The executable, taskbar, Start menu entry, desktop shortcut and tray use the same Skill-Desk logo. WebView2 is handled by the Tauri installer when needed. Windows ARM64 is not yet built; the initial Windows target is x64.

macOS: open the DMG and drag Skill-Desk into Applications. The initial local build is Apple Silicon. CI also builds using its macOS runner architecture.

Linux: CI produces a Debian package on Ubuntu 22.04. The package needs the system WebKitGTK runtime. Linux desktop/tray behavior needs a supported graphical session.

These initial packages are unsigned developer previews. Public signing and notarization have not been configured. There is no automatic updater or login startup registration in this preview.

## Everyday use

Opening the app starts its bundled service on an available loopback port. A second launch focuses the existing window. The tray menu offers **Open Skill-Desk**, **Hide to tray**, and **Quit Skill-Desk**. Closing the main window quits. Hide to tray keeps the service and active work running. Quitting or closing the window sends an explicit shutdown signal to the service, which terminates active authoring/import subprocesses. A parent-process check also stops the service after an unexpected desktop exit. Installed skills remain available to their agents after Skill-Desk exits.

Skill-Desk reads the personal Codex library at `~/.agents/skills` by default. The existing server CLI supports `--library claude`; a desktop library selector is a separate future improvement. Provider selection in Manage changes the authoring CLI, not the installation directory.

The server watches filesystem changes. Catalog and Manage updates use server events, with a 30-second connection heartbeat. An active job still polls for progress. AI descriptions are generated for new/changed skills; cached skills do not need another call. Failed description generation schedules a retry after its backoff; an unchanged healthy library does not trigger repeated scans.

The desktop webview is not granted Tauri filesystem or shell permissions. Native code starts only the bundled helper; writes to the local API retain origin and request-token validation.

## Local builds

Install Node.js, Rust, Python 3.9+ and the [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) for your build OS. Build each platform on that platform; the Python helper is not cross-compiled.

```sh
python -m venv .venv
# Activate .venv using the command for your shell, then:
python -m pip install -r requirements-build.txt
npm ci
python -m unittest discover -s tests -v
python scripts/build_sidecar.py
python scripts/smoke_sidecar.py
npm run desktop:build
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`. On macOS/Linux, use `source .venv/bin/activate`. If PowerShell activation is restricted, call `.venv\Scripts\python.exe` directly. Rust's cargo/bin directory must be on PATH. `npm run desktop:dev` also requires a built helper.

Output: `src-tauri/target/release/bundle/`. CI runs the same tests and packaged-helper smoke check before producing installer artifacts for Windows, macOS and Linux. Run the **Desktop installers** workflow manually, or push a version tag. Successful version-tag builds publish all installers and SHA-256 checksums to GitHub Releases. Main-branch and pull-request builds upload workflow artifacts only. See docs/RELEASING.md.

## Storage and icons

State and archives: `%LOCALAPPDATA%\Skill-Desk` on Windows, `~/Library/Application Support/Skill-Desk` on macOS, and `$XDG_DATA_HOME/Skill-Desk` (default `~/.local/share/Skill-Desk`) on Linux. Existing Mac state is preserved. Favorites persist in preferences.json independently of the local server port. Caches use the corresponding platform cache folder. `SKILL_DESK_HOME` overrides app state for isolated tests.

The icon source is `assets/skilldesk.svg`, based on the four-line mark in the marketing demo. To regenerate the platform assets, run `python scripts/make_icons.py` then `npm run icons`. Windows shortcuts reference the branded application executable; macOS uses the generated ICNS file, and the tray uses the bundled PNG.

## Verification still needed for distribution

Run the Windows workflow and test its installer on a clean Windows machine: installation without Python, WebView2 setup, logo on shortcuts/taskbar/tray, CLI discovery, Unicode paths, import/create, second launch, and Quit without orphaned processes. Run equivalent graphical checks on Linux. The Mac build cannot establish those Windows/Linux runtime results.
