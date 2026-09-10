<p align="center"><img src="../assets/skilldesk.png" width="80" alt="Skill-Desk logo"></p>
<h1 align="center">Build Skill-Desk yourself</h1>
<p align="center">Review the source. Run the project. Make your own installer.</p>

Prefer compiling the source to downloading a prebuilt installer? This guide follows the same build steps used by our GitHub Actions workflow. No signing certificate, private release key, or AI account is required to build.

**Jump to:** [Prerequisites](#1-install-the-build-tools) · [Source](#2-get-the-source) · [Windows](#windows-powershell) · [macOS / Linux](#macos--linux) · [Installers](#5-build-your-installer) · [Troubleshooting](#troubleshooting)

> [!NOTE]
> Build on the operating system you want to run: Windows for a Windows installer, macOS for a Mac app, and Linux for Linux packages. The bundled Python service is built for the current OS and architecture. These instructions do not cross-compile it.

## 1. Install the build tools

| Tool | Version used by our build workflow | Purpose |
| --- | --- | --- |
| Git | Current supported version | Download and inspect the source |
| Python | 3.12 | Build the bundled local service |
| Node.js and npm | Node.js 22 | Run the Tauri build CLI |
| Rust and Cargo | Stable, installed through rustup | Compile the desktop application |

Install the [Tauri prerequisites for your OS](https://v2.tauri.app/start/prerequisites/) as well:

- **Windows:** Microsoft C++ Build Tools with the **Desktop development with C++** workload, the Windows SDK, and WebView2. Use the Rust MSVC toolchain. Start with Windows x64, the architecture our release workflow builds.
- **macOS:** Xcode Command Line Tools for desktop builds. Use matching Python, Node and Rust architectures, such as all ARM64 on Apple Silicon.
- **Linux:** The compiler, WebKitGTK and other native packages listed in Tauri's instructions for your distribution. Our workflow uses Ubuntu 22.04 and additionally installs `patchelf` and `libfuse2` for packaging.

Open a new terminal after installing tools. Confirm `git --version`, `node --version`, `npm --version`, `rustc --version`, and `cargo --version` work.

Building downloads dependencies from their package registries. Your completed installer bundles Python; recipients do not need Python or these build tools. Codex or Claude Code is needed only when using AI authoring, not for compilation or browsing skills.

## 2. Get the source

```sh
git clone https://github.com/ldgraham92/skill-desk.git
cd skill-desk
```

This checks out the current default branch. To build a specific published version, select its tag before installing dependencies. For example:

```sh
git switch --detach v0.2.3
```

Use `main` for changes made after that release. Older tags preserve the source as it existed then. Inspect the code and record `git rev-parse HEAD` so you know which revision you built. These instructions describe the current build process; substantially older versions may have different requirements.

## 3. Prepare and verify the project

Run each command from the repository root. Stop and resolve errors before continuing.

### Windows PowerShell

These commands call the virtual environment's Python directly, so no activation or execution-policy change is needed. If PowerShell blocks `npm.ps1`, use `npm.cmd` as shown.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
npm.cmd ci
.\.venv\Scripts\python.exe scripts/check_version.py
.\.venv\Scripts\python.exe scripts/sync_ui_assets.py --check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/build_sidecar.py
.\.venv\Scripts\python.exe scripts/smoke_sidecar.py
```

### macOS / Linux

Use your Python 3.12 executable to create the environment. If it is named `python3` on your system, substitute that in the first command.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
npm ci
.venv/bin/python scripts/check_version.py
.venv/bin/python scripts/sync_ui_assets.py --check
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/build_sidecar.py
.venv/bin/python scripts/smoke_sidecar.py
```

The sidecar is Skill-Desk's bundled local service. Its smoke check uses temporary skill folders and state, with AI authoring disabled. It checks the compiled service rather than your personal library.

## 4. Run the desktop project

After building the service in step 3:

```sh
npm run desktop:dev
```

On Windows PowerShell, use `npm.cmd run desktop:dev`. Close the app before building an installer.

The running desktop app discovers your real user-level skills and uses your installed CLIs for requested authoring. Rebuild the sidecar after changing Python code, the app HTML, or bundled web assets; restarting Tauri alone does not refresh the frozen service. For theme edits, run `scripts/sync_ui_assets.py` with your virtual environment's Python before rebuilding.

## 5. Build your installer

Choose the command for your platform. The unsigned configuration disables creation of signed updater artifacts, allowing a local build without the project's private release key.

| Platform | Command |
| --- | --- |
| Windows PowerShell | `npm.cmd run desktop:build -- --bundles nsis --config src-tauri/unsigned.conf.json` |
| macOS | `npm run desktop:build -- --bundles app,dmg --config src-tauri/unsigned.conf.json` |
| Linux | `npm run desktop:build -- --bundles deb,appimage --config src-tauri/unsigned.conf.json` |

The first build takes longer because Rust compiles its dependencies. Successful builds place their output here:

| Platform | Output under `src-tauri/target/release/bundle/` |
| --- | --- |
| Windows | `nsis/Skill-Desk_*_x64-setup.exe` |
| macOS | `macos/Skill-Desk.app` and `dmg/*.dmg` |
| Linux | `deb/*.deb` and `appimage/*.AppImage` |

Open the generated installer to install your build. The installer already contains the local service. A local build is not guaranteed to be byte-for-byte identical to a release asset; toolchain versions and build environments can differ.

> [!IMPORTANT]
> Building locally does not provide a verified Windows publisher signature or macOS notarization. OS warnings can still occur when distributing your installer. Updater signatures and OS publisher signing are separate mechanisms.

### Updates and forks

The unsigned build configuration does **not** disable the in-app updater or change its source. A self-built app still checks the official Skill-Desk feed; accepting an update installs the official binary and replaces your local changes. To stay with source builds, rebuild and reinstall manually instead of accepting in-app updates.

For a separately distributed fork, configure your own application identity, update feed and signing key before publishing updates. See [update configuration](UPDATES.md) and the [release process](RELEASING.md). Never put signing keys or credentials in source control.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `py`, `node`, or `cargo` is not found | Install the relevant tool and reopen the terminal. Rust's Cargo bin directory must be on PATH. |
| Windows reports a missing linker or SDK | Install the C++ workload and Windows SDK from Tauri's prerequisites. |
| The build cannot find `skilldesk-service` | Run `scripts/build_sidecar.py` successfully before starting or packaging the desktop app. |
| A private signing key is requested | Include `--config src-tauri/unsigned.conf.json` in the installer command. |
| Shared UI assets are stale | Run `scripts/sync_ui_assets.py`, then rerun verification and rebuild the service. |
| Linux reports missing native libraries | Follow Tauri's prerequisites for your exact distribution and check the current workflow's packaging dependencies. |

If a build fails, [open an issue](https://github.com/ldgraham92/skill-desk/issues/new/choose) with your OS, architecture, tool versions, source commit and the relevant error. Remove credentials and private paths from logs before sharing.

---

[Back to README](../README.md) · [Desktop architecture](../DESKTOP.md) · [Contributing](../CONTRIBUTING.md) · [Build workflow](../.github/workflows/desktop.yml)
