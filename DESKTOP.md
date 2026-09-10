# Skill-Desk desktop

Skill-Desk packages its local service and web interface in a Tauri desktop window. The installer includes Python and the service dependencies. Users only need a signed-in Codex or Claude Code CLI for AI authoring, and Git for repository imports. Browsing and Markdown imports work without an authoring CLI.

## Installation

Windows: download the `Skill-Desk_*_x64-setup.exe` installer from [GitHub Releases](https://github.com/ldgraham92/skill-desk/releases). Install for the current user. The executable, taskbar, Start menu entry, desktop shortcut and tray use the same Skill-Desk logo. WebView2 is handled by the Tauri installer when needed. Windows ARM64 is not yet built; the initial Windows target is x64.

macOS: open the DMG and drag Skill-Desk into Applications. The initial local build is Apple Silicon. CI also builds using its macOS runner architecture.

Linux: CI produces a Debian package on Ubuntu 22.04. The package needs the system WebKitGTK runtime. Linux desktop/tray behavior needs a supported graphical session.

These initial packages are unsigned developer previews. Public signing and notarization have not been configured. The in-app updater verifies release signatures separately from OS publisher signing. Login startup registration is not configured.

## Everyday use

Opening the app starts its bundled service on an available loopback port. A second launch focuses the existing window. The tray menu offers **Open Skill-Desk**, **Hide to tray**, and **Quit Skill-Desk**. Closing the main window quits. Hide to tray keeps the service and active work running. Quitting or closing the window sends an explicit shutdown signal to the service, which terminates active authoring/import subprocesses. A parent-process check also stops the service after an unexpected desktop exit. Installed skills remain available to their agents after Skill-Desk exits.

Skill-Desk reads the personal Codex library at `~/.agents/skills` by default. The existing server CLI supports `--library claude`; a desktop library selector is a separate future improvement. Provider selection in Manage changes the authoring CLI, not the installation directory.

The server watches filesystem changes. Catalog and Manage updates use server events, with a 30-second connection heartbeat. An active job still polls for progress. AI descriptions are generated for new/changed skills; cached skills do not need another call. Failed description generation schedules a retry after its backoff; an unchanged healthy library does not trigger repeated scans.

The desktop webview is not granted Tauri filesystem or shell permissions. Native code starts only the bundled helper; writes to the local API retain origin and request-token validation.

## Local builds

Follow the **[build-it-yourself guide](docs/BUILD-YOUR-OWN.md)** for prerequisites, platform-specific commands, verification, development mode and unsigned installer builds. Build each platform on that platform; the Python service is not cross-compiled.

Our [Actions workflow](.github/workflows/desktop.yml) runs tests and the packaged-service smoke check before producing installers. Main and pull-request builds upload workflow artifacts. Version tags publish release assets after all platforms pass; see [release instructions](docs/RELEASING.md).

## Storage and icons

State and archives: `%LOCALAPPDATA%\Skill-Desk` on Windows, `~/Library/Application Support/Skill-Desk` on macOS, and `$XDG_DATA_HOME/Skill-Desk` (default `~/.local/share/Skill-Desk`) on Linux. Existing Mac state is preserved. Favorites persist in preferences.json independently of the local server port. Caches use the corresponding platform cache folder. `SKILL_DESK_HOME` overrides app state for isolated tests.

The icon source is `assets/skilldesk.svg`, based on the four-line mark in the marketing demo. To regenerate the platform assets, run `python scripts/make_icons.py` then `npm run icons`. Windows shortcuts reference the branded application executable; macOS uses the generated ICNS file, and the tray uses the bundled PNG.

## Verification still needed for distribution

Run the Windows workflow and test its installer on a clean Windows machine: installation without Python, WebView2 setup, logo on shortcuts/taskbar/tray, CLI discovery, Unicode paths, import/create, second launch, and Quit without orphaned processes. Run equivalent graphical checks on Linux. The Mac build cannot establish those Windows/Linux runtime results.
