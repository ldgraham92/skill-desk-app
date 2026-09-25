# Agents and models

Skill-Desk uses installed CLI tools and their existing authentication. It does not collect API keys or create provider accounts. Choose **Library settings → Author with** to select a CLI. Choose the destination separately when creating or importing a skill, or in the project selector.

| Agent | Personal destination | Project destination | Authoring | History recommendations |
| --- | --- | --- | --- | --- |
| Codex | `~/.codex/skills` | `.agents/skills` | Existing CLI login | Supported |
| Claude Code | `~/.claude/skills` | `.claude/skills` | Existing CLI login | Supported |
| OpenCode | `~/.config/opencode/skills` | `.opencode/skills` | Existing CLI configuration | Not yet supported |
| Cursor | `~/.cursor/skills` | `.cursor/skills` | Existing CLI login | Not yet supported |

The default shared library remains `~/.agents/skills`. `CODEX_HOME`, `CLAUDE_CONFIG_DIR`, and `XDG_CONFIG_HOME` affect their respective personal destinations. Explicit server roots remain supported. Skill-Desk displays documented compatible libraries for Cursor and OpenCode, so a skill may have several agent labels without being copied. Projects must be registered before their root-level skill directories are scanned.

## Set up a CLI

- Codex: install the CLI and run `codex login`.
- Claude Code: install the CLI and run `claude auth login`.
- OpenCode: install the CLI and check its available models. Free models may not require a paid account. Configure any required access inside OpenCode, not Skill-Desk.
- Cursor: install Cursor CLI and run `agent login`, then `agent status`. Skill-Desk finds `cursor-agent` first and falls back to `agent`.

Readiness checks make no inference requests. OpenCode readiness also checks required run options; its model picker and explicit synthetic connection test check separate capabilities. Cursor readiness provides the command for checking authentication yourself. It does not infer that a CLI is signed in merely because it is installed.

## OpenAI, Anthropic, and DeepSeek

OpenAI is available through Codex and Anthropic through Claude Code. Other model providers, including DeepSeek, are available through an OpenCode installation already configured to use them. Their account access and billing remain with that CLI and its provider.

For OpenCode or Cursor, **Library settings** includes an optional model field. Copy a model ID from `opencode models` or `agent models`, then choose **Save model**. OpenCode IDs use `provider/model`. An empty value uses the CLI default. Skill-Desk saves the model ID locally, not credentials, and does not switch to a different provider if the requested model fails.

## Current boundaries

OpenCode and Cursor authoring runs receive the skill brief and authoring guidance in a temporary working directory. Skill-Desk requests JSON, configures tool-denial permissions, and validates the returned skill before showing an installation preview. These CLIs still use their normal global configuration and may retain authoring sessions. They do not provide the same configuration isolation and ephemeral-history guarantees as the Codex/Claude recommendation path. Skill-Desk therefore does not send usage-history samples through them.

Cursor's SDK requires an API key, so this integration uses the signed-in CLI instead. No SDK runtime or direct API provider is bundled. Automatic Cursor history scanning is not implemented. The existing OpenCode history reader is retained, but it is not exposed as a recommendation integration.

Cursor supports explicit-only skill metadata. OpenCode does not recognize that metadata; configure its skill permissions in OpenCode instead. Supporting files are preserved on import, but agent-specific tool instructions may still need editing.

Publisher signing and macOS notarization remain deferred. Existing updater signatures continue to work independently.

## Integration references

- [OpenCode CLI](https://opencode.ai/docs/cli/), [configuration](https://opencode.ai/docs/config/), and [skill discovery and metadata](https://opencode.ai/docs/skills/).
- [Cursor CLI parameters](https://cursor.com/docs/cli/reference/parameters), [permissions](https://cursor.com/docs/cli/reference/permissions), and [skill discovery](https://cursor.com/docs/skills).
- [Cursor SDK authentication](https://cursor.com/docs/sdk/typescript#authentication).

## Reliability and history coverage

Library settings now shows a capability table with each CLI's provider relationship and personal/project destinations. A found executable is not a sign-in confirmation. Known user installation directories are checked when a desktop launch has a limited PATH. Invalid saved model settings are ignored; OpenCode model overrides must use `provider/model` form. Inherited API-key environment overrides are removed before authoring; the installed tool retains control of its saved authentication and configuration.

History previews report their check time, discovered/scanned/skipped session counts, contributing sessions, unreadable files, and duplicate records. They rotate excerpts across projects and dates. Large Codex sessions contribute bounded windows from their beginning, middle, and recent end; every gap resets project context until fresh metadata is found. File discovery, read size, and excerpt limits remain bounded, and the UI explains partial results. Project labels come from working-directory metadata and can identify a subdirectory rather than the repository root. These are local conversation samples, not token, billing, or account-limit measurements.

Create, import, and recommendation jobs can be cancelled. The local process group is stopped before another job starts; any unfinished preview is discarded. Briefs and import fields survive recoverable failures and closing/reopening their dialogs during the current page session. They are held in memory, not written to browser storage. Status reconnection can resume after a reload, but unsent form text does not survive a reload. Retries reuse the reviewed recommendation sample; an expired sample requires a fresh preview.

## Cursor and OpenCode history feasibility, checked 2026-09-23

OpenCode combines configuration from several sources, and a custom config file does not replace its global configuration. Managed settings can override runtime settings. A temporary directory plus a deny-tools setting therefore does not establish the same isolation contract used for history analysis. This is an integration finding, not a claim that the tool cannot support an isolated adapter. [OpenCode configuration](https://opencode.ai/docs/config/).

OpenCode's CLI documents JSON events, session management, and model selection. Those support the authoring adapter, but they do not by themselves prove that reviewed history will avoid inherited plugins or persisted sessions. Enabling recommendations needs a tested isolation and persistence design. [OpenCode CLI](https://opencode.ai/docs/cli/).

Cursor documents permission denials for shell, file, web, and MCP tools. Its print mode can use tools, and the current adapter supplies explicit deny rules. The published parameter reference did not establish an ephemeral, configuration-isolated mode for this integration. The adapter consequently continues to reject history analysis. [Cursor permissions](https://cursor.com/docs/cli/reference/permissions), [Cursor CLI parameters](https://cursor.com/docs/cli/reference/parameters).

At the time of the first pass, neither CLI was installed. OpenCode v2.0.15 is now installed; results from the second pass follow. Before enabling history recommendations, test a disposable authenticated installation with inherited rules/MCP/hooks, verify that only the reviewed context reaches the model, and verify where sessions are retained. Do not move the user's authentication files or modify their normal CLI configuration to obtain isolation.

## OpenCode V2 verification, checked 2026-09-24

V2 authoring uses `run --standalone` when advertised by CLI help. This owns a private server for the request and avoids using the interactive background service. A temporary project config denies tools and disables sharing/snapshots. The CLI retains its normal authentication and global configuration. Model IDs may include a `#variant` suffix. [OpenCode V2 migration](https://opencode.ai/v2/docs/migrate-v1/).

Local tests with the real v2.0.15 CLI confirmed structured text output, denied injected shell calls, cancellation, and process cleanup. They also confirmed that global AGENTS instructions reach the request, a global plugin loads, and a configured MCP process starts. Tool denial is therefore insufficient for history isolation. Plugin inheritance agrees with the documented configuration behavior. [OpenCode plugins](https://opencode.ai/v2/docs/plugins/).

Private-server sessions persist in the CLI database. A synthetic session could be exported and deleted using supported CLI commands, but Skill-Desk does not claim ephemeral authoring or delete the user's existing sessions. The read-only V2 history reader is tested with synthetic user/assistant/child-session records and stays behind the recommendation gate.

The model picker runs the installed CLI and supports search and manual selection. It does not infer prices from model names. If the CLI returns no model IDs, the picker explains that instead of claiming model access. The explicit connection test submits only a short synthetic JSON request and reports the result for that selection.

The current installation returned an empty model list. A real `opencode/big-pickle` authoring request failed with a free-tier access rejection. This is an unresolved service/access result, separate from the passing local adapter tests.
