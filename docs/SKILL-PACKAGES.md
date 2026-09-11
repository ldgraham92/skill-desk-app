# Move skills between devices

Skill-Desk packages let you transfer complete skills without a hosted service or a Skill-Desk account.

## Export from your first device

1. Open **Manage skills → Add skills → Export package**.
2. Select the skills to include. **Select all shown** follows the All / Codex / Claude selector.
3. Choose **Review package** and inspect the file list.
4. Choose **Save package to Downloads**. Skill-Desk displays the saved path and uses a new filename without overwriting existing files.

A package contains SKILL.md and the skill's supporting files, including references, scripts, licenses and invocation settings. Linked skill roots are copied as ordinary folders; links inside a skill are rejected. Git history is excluded.

Package metadata contains names, provider labels and file checksums. It excludes machine paths, CLI logins, application settings, saved favorites, generated descriptions and archives. The skill files themselves are copied as written: review them for private text before sharing. Common credential filenames are rejected, but this is not a comprehensive secret scanner. Packages are ordinary ZIP files, not encrypted backups.

## Import on your other device

1. Transfer the `.skilldesk.zip` file.
2. Open **Manage skills → Add skills → Import package** and select it.
3. Choose the default library, Codex or Claude as the destination.
4. Choose **Preview package**, review the instructions and files, then select the skills to install.
5. Choose **Install selected skills**. Installed entries appear with the **Package Imported** origin.

Existing names are never overwritten. Conflicting entries remain unchecked and disabled. If a package contains separate copies with the same name, the first copy is available and later copies are flagged; export those copies separately to install into different providers. All selected skills go to the destination you choose, regardless of their source provider labels.

Each skill installs independently. If an entry fails, successfully installed entries stay installed and the preview reports the remaining failures. You can remove imported skills through the existing archive-and-restore workflow in the default library. Skills in other provider directories retain the existing read-only management behavior.

Packages preserve instructions rather than converting them for another provider. Platform-specific scripts, tool names and absolute paths inside instructions may need editing on the destination.

## Transfer without hosting

**[Built-in nearby sharing](NEARBY-SHARING.md)** lets you send an export directly to another Skill-Desk device. Choose **Send to device** from the export review; open **Receive from device** on the destination. No other app is required.


- **USB drive or shared network folder:** copy the package and import it on the receiving device.
- **[LocalSend](https://localsend.org/):** free, open-source transfers between nearby devices on the same local network, without an account or external server.
- **[Syncthing](https://syncthing.net/):** synchronize a dedicated package-transfer folder between your devices without central storage. Import received packages through Skill-Desk when ready.

These tools are optional and are not bundled or configured by Skill-Desk. Skill-Desk supports reviewed file and nearby package transfers, not automatic skill synchronization. Keeping a transfer folder separate from active skill directories preserves the import review and conflict checks.

## Format and limits

The version 1 format uses `manifest.json` and `skills/<entry-number>/<relative-file-path>`. Each listed file has a SHA-256 digest. Checksums detect changes relative to the manifest; they do not authenticate the sender.

A package supports up to 500 skills, 10,000 files and 100 MB of file content, with a 100 MB compressed limit. Individual skills retain the existing 1,000-file / 30 MB limit and 10 MB per-file limit. Export smaller groups if necessary. Unsupported format versions, unsafe paths, links, duplicate ZIP paths, case collisions and unlisted files are rejected before staging an import.

## Built-in collections

Open **Manage skills → Discover** to preview AI Hero or PStack. Choose a destination, review the instructions and supporting files, and select the skills to install. Existing names remain blocked. **Save package to Downloads** saves a portable `.skilldesk.zip` without installing it. Both flows work offline because the packages ship with the app.

The bundled snapshots contain all recursively discovered `SKILL.md` folders under the selected upstream directories:

| Collection | Skills | Pinned source |
| --- | --- | --- |
| AI Hero | 37 | [mattpocock/skills at 3cca18b](https://github.com/mattpocock/skills/tree/3cca18b368ae95cdbdebbff572ccafa662551015/skills) |
| PStack | 47 | [cursor/plugins at c9ce35f](https://github.com/cursor/plugins/tree/c9ce35f013e234eb4de5ce15e1ca322998bb05ea/pstack/skills) |

AI Hero includes the upstream `in-progress` folder. Every packaged skill includes its upstream MIT license and source location. Skill folders retain supporting files and executable permissions. PStack's `Make Bot UI` and `Poteto Mode` names are normalized to `make-bot-ui` and `poteto-mode`. Cross-skill Markdown links point to the pinned upstream files so each skill can be installed independently. The collection preview and `web/collections/catalog.json` list these adjustments.

These are upstream instructions, not provider-specific conversions. Their tool requirements and behavior remain as written by the authors. Downloading or importing does not execute included scripts. Installing a collection does not subscribe the skills to upstream updates; updated snapshots require a later Skill-Desk release or a separately reviewed import.

To rebuild the archives, check out the exact commits in `scripts/build_collections.py` into clean, separate source directories, then run:

```sh
.venv/bin/python scripts/build_collections.py /path/to/mattpocock-skills /path/to/cursor-plugins
.venv/bin/python -m unittest discover -s tests -p test_collections.py -v
```

Review upstream changes before changing the pinned commits. The builder recursively finds skill folders, validates every skill, records adaptations and hashes, and creates the packages in `web/collections`. The desktop sidecar already bundles the full `web` directory.

## Recommendations from your usage

Open **Manage skills → For you**. Choose the agent you want to install skills for, Codex or Claude Code, and choose the last 7, 30, or 90 days. That agent reviews only its own history and installs suggestions into the selected personal or project library. It must already be installed and signed in. Switching agents clears the preview so their use cases remain separate.

Choose **Preview usage** to read a bounded sample of local user prompts. Review, edit, or deselect excerpts before asking the agent for recommendations. Skill-Desk masks common credential patterns and home paths, but this cannot remove every private detail. The selected, edited excerpts, bundled skill descriptions, descriptions of skills already available to the agent, and the selected project name are passed to the chosen agent. Project source files are not read for this review. This uses its normal service and usage allowance; it is not necessarily offline inference.

Suggestions come only from the bundled AI Hero and PStack collections and exclude skills already available to the destination agent. A skill installed only for Claude can still be recommended for Codex, and vice versa. For a project, existing skills include its selected agent’s project skills and personal skills; unrelated projects are excluded. Each suggestion includes its reason and the reviewed prompts that support it. Choose **Review skill**, inspect the instructions and the destination agent, then install it. Recommendations never install skills automatically.

The recommendation flow reads Codex history and session JSONL files or Claude Code history and project JSONL files, according to the selected agent. Reads exclude assistant messages and tool output and do not modify history. The sample is limited to 120 excerpts of 1,000 characters each; file and scan limits can omit older or large records. Missing, unreadable, or truncated sources are reported in the preview.

Preview tokens expire after 15 minutes. Previews and recommendation results remain in the running app's memory; Skill-Desk does not save them as history files. Discarding or replacing a preview removes that cached sample. Analysis runs in a temporary directory with tools, integrations, hooks, and user configuration disabled, using ephemeral/no-session-persistence CLI modes. The provider's normal service retention rules still apply. Use current Codex or Claude Code versions that support these isolation options; analysis does not use custom CLI model settings.

## Project repositories

In Manage skills, choose **Add project**, enter a name and the path to an existing local Git repository root, and choose **Add project**. Onboarding registers the location without changing repository files. Git worktrees with a `.git` file are supported. Up to 50 repositories can be registered.

Choose the repository in **Working in**, then select **Codex** or **Claude Code**. The Installed list shows that project's skills for the selected agent. Discover, package imports, GitHub/Markdown imports, and skill creation use that destination. The preview shows the destination before any files are installed. Personal libraries remain available in the dropdown.

Project installs use `.agents/skills/<name>` for Codex and `.claude/skills/<name>` for Claude Code. These match the agents' documented repository locations: [Codex local skills](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills) and [Claude Code skill locations](https://code.claude.com/docs/en/skills#where-skills-live). Skill-Desk does not commit or push the files. Existing files are never overwritten. A personal copy does not block a separately reviewed project install, though the agent's own name-precedence rules still apply.

The destination is checked again at installation. Missing repositories and redirected skill-directory symlinks are rejected. **Manage projects → Remove from list** forgets a repository without deleting its skills or other files. Restore a moved repository to its recorded path, or remove the old entry and onboard the new path. Project skills are displayed as externally managed files; edit or remove them in the repository.

Project selection changes the destination and the skills compared for overlap. The usage sample still covers the selected agent's recent work across projects. Review and deselect unrelated excerpts; this release does not automatically filter history by repository.

## Already covered and first steps

The analyzing agent compares skill purposes with the descriptions in the selected library. **Already covered by your library** names an existing skill and explains why it may cover a bundled alternative. It also offers a prompt to try the existing skill. These are model judgments, not a guarantee of equivalent behavior. Unknown skill references and recommendations that conflict with their own overlap results are rejected.

After a successful installation, **Put your new skills to work** offers a copyable starter prompt. Recommendations have a first step grounded in the reviewed usage; other installs have a general starter for the named skill. Codex prompts use `$name`, Claude Code prompts use `/name`. Copying a prompt does not run it. Open the destination repository in the relevant agent and start a new session before trying it.

## First-launch walkthrough

The first launch of this guide opens a five-step screenshot walkthrough. Use **Back**, **Next**, **Skip tour**, or **Start exploring**. Completion and skipping are saved locally with app preferences and survive restarts. Escape skips the guide too. **Getting started** in the sidebar reopens it at any time. It does not interrupt an active skill job or preview.

The bundled screenshots in `web/walkthrough/` show an isolated example workspace with synthetic usage and simulated recommendations. They are captured at double resolution from the actual app, contain no personal history, and work offline. Recapture them when the corresponding screens change.

## Project notes and recommendation choices

Use **Project notes** beside the project selector to describe what you use Codex and Claude Code for. The notes are stored separately. The preview shows the selected agent's notes before they are sent for analysis. These notes supplement the history sample; they do not trigger a source-code scan.

On a recommendation, choose **Save for later** or **Not relevant**. A dismissal can include an optional note for future reviews. Choices belong to that agent and destination. Saved and dismissed suggestions are excluded from subsequent reviews there, and preference notes are shown in the next usage preview. Open **Saved & dismissed suggestions** to review a saved skill or reset a choice. Saved suggestions retain the reason and first-step prompt locally, but not the supporting history excerpts.

## Installation history, undo, and usefulness

Open **Installation history & usefulness** from Installed, or use **Add skills → Installation history**. New installations record their destination, source, agent, and time. Existing installs from earlier releases are not retroactively tracked.

**Review undo** checks the current installation's identity and file digest. Confirming undo repeats those checks and moves the unchanged copy into Skill-Desk's `install-undo` data directory. Changed, missing, replaced, or redirected copies are preserved. The history entry displays the archived copy's path. Undo never rewrites a project's Git history or removes unrelated repository files.

After trying a skill, choose **Was this useful?** and record Useful, Confusing, or Haven't used it yet, with an optional note. Assessments are local. **Share this assessment** starts a feedback report for you to review; it sends nothing automatically.

## Agent readiness and feedback

**Check agent readiness** is available in Library settings and For you. It checks CLI startup, version, and saved authentication without an inference call. A saved sign-in does not guarantee service availability, current allowance, or compatibility with every CLI setting. Missing and unauthenticated clients have installation links or sign-in commands. Skill-Desk does not start a login flow or change CLI credentials on your behalf.

**Send feedback** prepares a Bug, Idea, or Confusing experience report. The preview contains your text, app version, OS version, and current screen. It does not attach history, project paths, credentials, or logs. Edit the preview, copy it, or open a GitHub issue draft. You submit the issue yourself on GitHub; reports are public when submitted. Longer reports can be copied and pasted into a blank issue. Nothing is sent as background telemetry.

**What's new** introduces each release and links directly to the relevant screens. Returning users see it automatically once; new users get the walkthrough first and can open What's new from the sidebar. Closing the panel marks that release as seen. It can be reopened any time.
