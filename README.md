<p align="center"><img src="assets/skilldesk.png" width="96" alt="Skill-Desk logo"></p>
<h1 align="center">Skill-Desk</h1>
<p align="center">Discover, create and manage the skills behind your AI work.</p>
<p align="center"><a href="https://github.com/ldgraham92/skill-desk/actions/workflows/desktop.yml"><img src="https://github.com/ldgraham92/skill-desk/actions/workflows/desktop.yml/badge.svg" alt="Desktop builds"></a> <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT license"></a></p>

Skill-Desk is a free, open-source desktop manager for personal AI skills. It keeps your skill files on your machine and uses your installed, signed-in Codex or Claude Code CLI when you ask it to author a skill. Reference guidance is generated for new or changed skills and cached locally.

**[Download a desktop release](https://github.com/ldgraham92/skill-desk/releases)** · **[Report a bug](https://github.com/ldgraham92/skill-desk/issues/new/choose)** · **[Try the standalone demo](marketing/index.html)**

## What it does

- Browse and search globally installed skills, save favorites, and copy example prompts.
- Create a skill from a brief, track progress, review its instructions, and install it.
- Import pasted Markdown, an MD file, or a complete skill folder from GitHub.
- [Export and import skill packages](docs/SKILL-PACKAGES.md) to move full skill folders between devices without hosting a service.
- Track User Created, Repo Installed, Markdown Imported and Existing origins.
- Archive removed skills and restore them with installation-conflict checks.
- Refresh the library when skill files change.
- Choose Codex or Claude Code as the authoring provider, using its existing CLI login.

The desktop window and bundled local service start together. The tray menu opens or hides the window. Closing the window or choosing Quit stops the service. Installed skills remain available to their agents when Skill-Desk is closed.

## Install

Choose the appropriate asset from [Releases](https://github.com/ldgraham92/skill-desk/releases):

| Platform | Installer |
| --- | --- |
| Windows x64 | `*-setup.exe` |
| macOS | `.dmg`, with the CPU architecture in the filename |
| Debian/Ubuntu Linux x64 | `.deb` |

Python is bundled. Browsing and Markdown imports do not require an AI account. AI authoring requires an installed and signed-in Codex or Claude Code CLI. GitHub repository imports require Git. CLI usage consumes your provider account's allowance; Skill-Desk does not operate a paid generation service.

The releases are previews without Windows publisher signing or macOS notarization. The in-app updater verifies release signatures before installation; see [app updates](#app-updates).

The desktop app currently manages `~/.agents/skills`. Authoring-provider selection does not change the installation directory. The development server supports `--library claude` for `~/.claude/skills`; a desktop library selector is planned.

## Prefer to build it yourself?

You can review the source, run Skill-Desk locally, and compile your own installer. Our **[build-it-yourself guide](docs/BUILD-YOUR-OWN.md)** covers Windows, macOS and Linux, including prerequisites, verification, installer locations and builds without a private signing key.

> [!NOTE]
> Windows publisher signing is not configured for these previews. Release updates carry a separate signature that Skill-Desk verifies. Building from source is available if you prefer it; it does not add an OS publisher signature.

## Hosting the marketing site

Deploy only `marketing/` as a static website. In Coolify, choose the Static build pack and set Base Directory to `/marketing`. See [marketing deployment instructions](docs/MARKETING.md). The repository root `index.html` is also a generated copy of the marketing page; the desktop template lives in `web/app.html` and contains no bundled skill entries.

## Development

Skill-Desk uses Tauri, HTML/CSS/JavaScript, and a bundled Python service. See [DESKTOP.md](DESKTOP.md) for platform prerequisites and full build instructions.

```sh
python -m venv .venv
# Activate the virtual environment for your shell first.
python -m pip install -r requirements-build.txt
npm ci
python scripts/check_version.py
python -m unittest discover -s tests -v
python scripts/build_sidecar.py
python scripts/smoke_sidecar.py
npm run desktop:dev
```

Build a distributable installer with `npm run desktop:build`. The [Actions workflow](.github/workflows/desktop.yml) builds and tests on Windows, macOS and Linux. Version tags publish installers and SHA-256 checksums to GitHub Releases only after every platform succeeds.

## Project guides

- [Features and local server](LIVE-SYNC.md)
- [Desktop packaging and platform checks](DESKTOP.md)
- [Contributing](CONTRIBUTING.md) and [community conduct](CODE_OF_CONDUCT.md)
- [Security reporting](SECURITY.md)
- [Release process](docs/RELEASING.md) and [changelog](CHANGELOG.md)

## Roadmap

Curated and user-added skill libraries, a desktop library selector, signed installers, app updates, and reusable integration boundaries for other tools. These are planned features, not capabilities of the first release.

## License and attribution

Skill-Desk is MIT licensed. See [LICENSE](LICENSE). The original bundled skill/reference material retains its separate copyright notice in [PSTACK-LICENSE.txt](PSTACK-LICENSE.txt). Imported third-party skills retain their own licenses.

### Personal skill discovery

The desktop scans `~/.agents/skills`, `~/.codex/skills`, and `~/.claude/skills`. `CODEX_HOME` and `CLAUDE_CONFIG_DIR` override the corresponding CLI configuration directories. On Windows, `~` means your user profile. Manage shows the scanned paths. Linked copies of the same skill appear once; separate copies with the same name remain separate. Missing optional folders are watched for creation.

New skills install to the shared `.agents/skills` folder. Entries discovered in the other CLI folders are currently read-only in Manage. Project-local skills and plugin caches are not scanned. An explicit `--root` or `--library` keeps the standalone service limited to that selected library.

Use the All / Codex / Claude selector beside search to filter the catalog, Manage, and printed guide. All shows harness labels. A skill installed in only one harness offers an install action for the other. The preview preserves the complete folder and requires a separate install click; existing destination names are never overwritten. Copies are independent, and harness-specific instructions may need editing.

### App updates

Use Updates beside Print or Check for updates in the tray menu. Review release notes, then choose Update and restart. Updates wait for active skill jobs and outstanding previews. Windows, macOS, and Linux AppImage builds support in-app updates; Debian packages use package-manager upgrades. See [update and release setup](docs/UPDATES.md).
