# Move skills between devices

Skill-Desk packages let you transfer complete skills without a hosted service or a Skill-Desk account.

## Export from your first device

1. Open **Manage skills → Export package**.
2. Select the skills to include. **Select all shown** follows the All / Codex / Claude selector.
3. Choose **Review package** and inspect the file list.
4. Choose **Save package to Downloads**. Skill-Desk displays the saved path and uses a new filename without overwriting existing files.

A package contains SKILL.md and the skill's supporting files, including references, scripts, licenses and invocation settings. Linked skill roots are copied as ordinary folders; links inside a skill are rejected. Git history is excluded.

Package metadata contains names, provider labels and file checksums. It excludes machine paths, CLI logins, application settings, saved favorites, generated descriptions and archives. The skill files themselves are copied as written: review them for private text before sharing. Common credential filenames are rejected, but this is not a comprehensive secret scanner. Packages are ordinary ZIP files, not encrypted backups.

## Import on your other device

1. Transfer the `.skilldesk.zip` file.
2. Open **Manage skills → Import package** and select it.
3. Choose the default library, Codex or Claude as the destination.
4. Choose **Preview package**, review the instructions and files, then select the skills to install.
5. Choose **Install selected skills**. Installed entries appear with the **Package Imported** origin.

Existing names are never overwritten. Conflicting entries remain unchecked and disabled. If a package contains separate copies with the same name, the first copy is available and later copies are flagged; export those copies separately to install into different providers. All selected skills go to the destination you choose, regardless of their source provider labels.

Each skill installs independently. If an entry fails, successfully installed entries stay installed and the preview reports the remaining failures. You can remove imported skills through the existing archive-and-restore workflow in the default library. Skills in other provider directories retain the existing read-only management behavior.

Packages preserve instructions rather than converting them for another provider. Platform-specific scripts, tool names and absolute paths inside instructions may need editing on the destination.

## Transfer without hosting

- **USB drive or shared network folder:** copy the package and import it on the receiving device.
- **[LocalSend](https://localsend.org/):** free, open-source transfers between nearby devices on the same local network, without an account or external server.
- **[Syncthing](https://syncthing.net/):** synchronize a dedicated package-transfer folder between your devices without central storage. Import received packages through Skill-Desk when ready.

These tools are optional and are not bundled or configured by Skill-Desk. This release provides manual package transfer, not automatic skill synchronization. Keeping a transfer folder separate from active skill directories preserves the import review and conflict checks.

## Format and limits

The version 1 format uses `manifest.json` and `skills/<entry-number>/<relative-file-path>`. Each listed file has a SHA-256 digest. Checksums detect changes relative to the manifest; they do not authenticate the sender.

A package supports up to 500 skills, 10,000 files and 100 MB of file content, with a 100 MB compressed limit. Individual skills retain the existing 1,000-file / 30 MB limit and 10 MB per-file limit. Export smaller groups if necessary. Unsupported format versions, unsafe paths, links, duplicate ZIP paths, case collisions and unlisted files are rejected before staging an import.
