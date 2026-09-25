# Library maintenance

Version 0.4 adds **Manage skills > Add skills > Maintain library**.

## Updates and provenance

Search for a skill and choose **Origin and updates**. GitHub imports record the repository, exact commit, folder, and an untouched comparison baseline. Checks download a selected revision without executing repository content. Skill-Desk compares the baseline, installed files, and upstream files. It preserves local-only edits, merges non-overlapping text edits, and asks you to resolve other conflicts file by file. Binary conflicts support choosing either copy. Custom text resolutions have a 200 KB limit.

The merged result is another draft. Compare it with the destination and explicitly replace the installed copy. Both the installed tree and incoming draft are checked again before replacement. The previous copy stays archived. **Archived revisions** opens a rollback preview through the same comparison workflow.

Pins use full immutable commit IDs. Branches and tags can be checked, then their resolved commit can be pinned. **Pin installed revision** pins the recorded import. Clearing the pin field removes the pin. An older import can establish its baseline by fetching its recorded original commit; a missing commit or ambiguous skill folder requires a new precise import.

## Draft files

Choose **Files and revisions** in a draft preview. You can add, edit, rename, or remove supporting text files, preview basic Markdown, replace text across editable files, and compare all resulting changes. A file operation creates an independent preview. The original remains available if validation fails. SKILL.md references must resolve within the draft; supporting Markdown references outside the folder are advisory findings.

Folder revisions include supporting files. Up to ten revisions are retained per draft and copied into explicitly saved drafts. Restoring a revision creates another preview. Saved templates use the same reviewed draft mechanism. Open a template from **Saved drafts**, then fork it for another agent. Draft packages export without installation.

Drafts are not silently persisted. Instruction text, file edits, and recommendation runs stay in memory unless you explicitly save or export them. Closing the app loses unsaved previews.

## Organization and checks

Maintenance search reads complete SKILL.md text, names, notes, and tags. Filters cover agent, project, origin, modification date, favorites, tags, and local collections. Searches can be saved and deleted. Notes and collection membership are stored separately from skill files and survive managed updates at the same destination.

Batch favorite and archive actions return individual results. Batch exports validate each selected skill and report rejected entries. Local collections show coverage across agents and prepare reviewed copies with conflict and compatibility findings.

Duplicate checks compare filenames and bytes. Similarity suggestions use names and overlapping description words; they do not prove equivalent behavior. Effective-context checks consider personal skills together with each selected project's skills.

Quality checks cover metadata, invocation-policy disagreements, local references, known agent fields, platform-specific paths and commands, encoding, generated files, large files, and portable filenames. Invalid skill metadata or entrypoint references block installation. Portability findings can block portable export. Other findings are advisory. Export a skill or collection report, then rerun checks after editing to see resolved findings.

The documented field checks were reviewed against [Claude Code](https://code.claude.com/docs/en/skills), [Codex](https://developers.openai.com/codex/skills), [Cursor](https://cursor.com/docs/skills), and [OpenCode V2](https://opencode.ai/v2/docs/skills). They are conservative guidance rather than runtime certification. OpenCode V2 uses `metadata.opencode/autoinvoke`; the existing authoring checkbox is not yet an OpenCode metadata editor.

## Backup and recovery

Backups include only the selected skills, explicitly selected settings, and explicitly saved drafts. Skill backups retain upstream provenance and baselines. Workspace backups can contain private notes and local filesystem paths. Ordinary portable skill packages remain separate.

Restore verifies the manifest, checksums, path safety, file count, and expanded size before showing exact destinations. Select individual objects and explicitly permit replacing existing ones. Changed destinations or changed prepared files are rejected. Settings restoration requires an app restart before further mutations.

Filesystem transactions preserve before/after copies for installs, replacements, archives, restores, and settings restoration. **Recover interrupted work** shows incomplete operations. Recovery rechecks the reviewed destination and preserves displaced files, including newer edits. Linked-skill operations require manual link recovery from their preserved archive. Completed recovery copies are retained locally; they are not automatically deleted.

Job records contain action and status metadata, not prompts or reviewed history. After a restart, interrupted jobs are identified and old job links show a recovery message. Reopen explicitly saved drafts or re-enter unsaved authoring inputs. Agent requests are never automatically replayed.

Unreadable origin, project, or other managed state records remain intact. Affected writes fail with an explanation. Restore a verified backup or repair the preserved file; the app does not silently overwrite corrupt records.

## Reconnecting and relocating

Repository reconnection retains the project ID and its recommendation choices and notes. Path-bound origin records and skill annotations move to the new registered location. Unsaved draft destinations should be re-prepared; historical installation undo records keep their original location checks.

On macOS and other POSIX systems, managed personal-library relocation copies the library, preserves the original as a recovery copy, and leaves a directory link at the original path. This keeps agent discovery working. The reviewed link target is recorded so subsequent replacements can verify it. Project libraries remain in their repositories. Windows relocation is blocked until its directory-link workflow can be tested.

## History

History controls save exclusion paths for projects and history locations. Preview coverage explains timeframe, scope, duplicate, delegated-session, and exclusion counts. Excerpts remain editable before analysis, including manual redaction.

**Save reviewed sample locally** stores only the selected, edited excerpts after validating the active review. Saved samples can be reopened and deleted. They do not silently refresh themselves. Compare recommendation runs within the current app session to see changed suggestions and evidence fingerprints. Saved suggestions report whether installed descriptions or project notes changed and whether a same-name skill is now installed.

A metadata-only indexing experiment detected changed files without storing prompt text, but could not reconstruct excerpts without reading their contents. No persistent prompt-text index was introduced. The existing bounded standard/deep scanner remains the production reader.
