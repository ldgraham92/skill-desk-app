# Live global skill catalog

For packaged desktop installation, see [DESKTOP.md](DESKTOP.md).

For the development server, double-click `Start Skill-Desk.command`, then open http://127.0.0.1:8765. Keep the Terminal window running. Press Control-C to stop. The original `index.html` remains the portable offline collection.

The server scans `~/.agents/skills`, including symlinked skill folders. It reads `SKILL.md` and supporting Markdown, YAML, JSON and text documents. It uses your selected, signed-in Codex or Claude Code CLI to author reference guidance. These calls send skill documentation to the selected provider and use that account’s allowance. No separate API key is needed. The installed skills are never edited.

Descriptions are cached by documentation content hash in `~/Library/Caches/Skill-Desk/descriptions-v1.json`. Only new or changed content needs generation. The server watches filesystem changes and pushes catalog updates to the page. A generation job can take several minutes. Failed description jobs retry after 15 minutes, with errors shown in the sidebar. New entries show their original descriptions while generation is pending. Removed skills disappear on the next scan. AI guidance can be imperfect; installed source instructions remain accessible.

Requirements: Python 3 and the packages in `requirements.txt`, and either Codex CLI signed in with `codex login` or Claude Code signed in with `claude auth login`. This Mac already has the Codex setup. The CLI uses your current configured model. The server binds only to this Mac's loopback interface.

```sh
# Scan without using Codex
python3 scripts/skill_desk.py --once --no-author
# Author one pending description
python3 scripts/skill_desk.py --once --limit 1
# Author all pending descriptions and exit
python3 scripts/skill_desk.py --once
# Browse cached descriptions without making generation calls
python3 scripts/skill_desk.py --no-author
```

Run one sync/server process at a time. Only the personal global skill directory is scanned, not plugin caches or project skills. Nothing is registered to start at login.

## Create, import, and manage

Open **Manage** in the sidebar.

- **Create skill** sends your brief to the selected, signed-in CLI. It supplies the installed `skill-creator` and `writing-for-agents` guidance when available, and falls back to basic skill-format instructions. Generation returns a self-contained `SKILL.md`. Automatic invocation is the default; select the explicit-request option when needed. Review the preview, then choose **Install globally**.
- **Import skill** accepts pasted Markdown, a local Markdown file, or an HTTPS GitHub repository URL. For ordinary Markdown, supply its name and discovery description. GitHub imports retain the complete selected folder, including scripts and policy files, and record the fetched commit. Repository scripts are not executed. A repository containing several skills offers a selector; install one skill per import. Branch or tag and folder fields are optional. Private repositories require existing noninteractive Git access.
- Imports with an existing folder or skill name are blocked without overwriting it. Missing relative references are reported; import the full repository folder when the entrypoint needs supporting files.
- Source filters show **User Created**, **Repo Installed**, **Markdown Imported**, and **Existing**. Existing means the skill was not installed through this manager, so its installation origin is not assumed.
- **Remove** shows a confirmation and moves the installed folder into the app's archive. The skill leaves global discovery. **Removed skills → Restore** puts it back, provided no conflicting installation exists. Removing a symlink moves the link and preserves its target.

Installation origins and archives live in `~/Library/Application Support/Skill-Desk/`. Draft previews are temporary and expire when the server stops. Existing `index.html` remains an offline, fixed collection; these management features require the local server. No install or delete operation modifies your global Codex configuration or AGENTS.md.

Import limits: a Markdown request may contain up to 200 KB; a selected skill folder may have up to 1,000 files and 30 MB total, with no file over 10 MB. Repository previews support up to 30 discovered skills; choose a narrower folder for larger collections. Symlinks in incoming folders are rejected. Create and Import jobs run one at a time. Generating previews and description guidance uses the selected provider’s allowance.

Run the lifecycle checks with `python3 -m unittest discover -s tests -v`.

Create and Import jobs show an animated status indicator, elapsed time, and the current preparation step. **Continue browsing** closes the dialog while a status banner remains above the page. **View progress** reopens it. A completed background job changes the banner to **Ready to review** without interrupting browsing. Connection failures display a reconnecting notice and retry; generation failures remain visible until dismissed. Elapsed time is not an estimate of remaining work, and the app does not invent a completion percentage.

## Authoring with Codex or Claude Code

In **Manage → Author with**, select the installed CLI to use for both skill creation and generated reference descriptions. Skill-Desk reuses that CLI's authentication. Sign in in Terminal first (`codex login` or `claude auth login`). A detected executable is not proof of an active login. Generation consumes the selected provider's allowance and needs network access; browsing already cached descriptions does not make a model call.

The authoring provider does not change the installation directory. The default remains your Codex library. Claude-only users can launch:

```sh
python3 scripts/skill_desk.py --provider claude --library claude
```

This manages `~/.claude/skills` instead. Existing libraries are never automatically moved or duplicated. `--root` can override the library path. New explicit-only skills in a Claude library also receive Claude's `disable-model-invocation` frontmatter. Existing imports retain their files unchanged; review agent-specific instructions and dependencies before using them in another agent.

The Claude adapter uses `claude --print --output-format json --json-schema` and reads `structured_output`. It disables built-in and MCP tools for authoring, disables session persistence, and excludes inherited API credential/provider overrides so the CLI can use its saved login. Update Claude Code if those flags are unavailable. Provider preferences are saved in `~/Library/Application Support/Skill-Desk/provider.json`.

Verified against [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference), [programmatic usage](https://code.claude.com/docs/en/headless), and [personal skill locations](https://code.claude.com/docs/en/skills). The integration has adapter and policy tests; live Claude-account verification has not been performed on this Mac because its CLI is not installed.

## Shareable demo

Send `marketing/index.html` to friends. It contains its own HTML, CSS, JavaScript and sample data. Double-click to open it locally. It does not contact either provider, read local skills, install anything, or include your personal skill data. Interactive operations affect only the page's sample library. `marketing/skilldesk-demo.png` is a static overview. Print / save PDF uses the browser print dialog. The live application is separate from this demo file.
