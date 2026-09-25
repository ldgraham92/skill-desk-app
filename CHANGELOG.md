# Changelog

## 0.4.0

- Clarify recommendation review and installation, preserve saved job outcomes, and report fixed diagnostic codes without private conversation content.
- Update Pillow to 12.3.0, PyInstaller to 6.22.3, Tauri to 2.11.6, its CLI to 2.11.5, and single-instance to 2.4.5. Backport the upstream Linux glib iterator safety fix; see [backport provenance](src-tauri/vendor/GLIB-BACKPORT.md).
- Check static asset containment and saved revision paths, bound Nearby address parsing, and preserve malformed job records without preventing startup.
- Reviewed GitHub updates with immutable pins, three-way file merges, conflict decisions, provenance, and archived rollback previews.
- Supporting-file edits, whole-folder revisions, templates, Markdown preview, and draft export.
- Verified workspace backups, selective restoration, operation recovery, restart interruption records, and stale-window checks.
- Full-instruction search, saved searches, local notes/tags/collections, batch actions, and agent-aware quality reports.
- History exclusions, explicitly saved reviewed samples, recommendation comparisons, and saved-suggestion freshness.
- Actual macOS WebKit interaction checks, a packaged active-job shutdown test, failure injection, and bounded soak testing.

- Editable draft instructions, revision diffs, bounded supporting-file previews, and explicitly saved local drafts.
- Reviewed duplication and copies to multiple agents, identical/diverged copy comparisons, and a read-only library health report.
- OpenCode V2 private-server support, model discovery/search, explicit connection tests, and specific free-tier errors.
- Fairer history read budgets, registered project labels, date/project breakdowns, review filters, and a cancellable deeper scan.
- Real OpenCode CLI tests against a synthetic local model; history recommendations stay disabled after inherited configuration and persistence were confirmed.

- History coverage counts, refresh timestamps, project labels, and sampling across dates and projects.
- Cancellable agent/import jobs, preserved form inputs, actionable errors, and retry-safe installation requests.
- Agent capability matrix, broader executable discovery, validated model settings, and local diagnostics without private content.
- Duplicate-copy warnings and reviewed single-skill replacement with archived originals and rollback checks.
- Recommendation evidence labels and exclusion of saved/dismissed skill names across collections.
- Keyboard focus recovery, responsive capability details, visible QA/development labels, and disposable browser tests.


- Read current Codex desktop user-message records, exclude subagent sessions and injected context, and retain a bounded opening section of large histories.
- Default project recommendation previews to repository-matched prompts, with an explicit All projects option and notices for missing metadata and incomplete samples.
- Add OpenCode and Cursor personal/project skill destinations, compatible-library discovery, installation previews, authoring through signed-in CLIs, and local readiness checks.
- Save optional CLI model selections, including configured DeepSeek models through OpenCode. No direct API-key provider or SDK is added.
- Keep automatic history recommendations limited to the isolated Codex and Claude Code integrations. Publisher signing remains deferred.

## 0.3.0

- Reorganize Manage skills into Installed, Discover, and For you, with project and agent destinations.
- Onboard local Git repositories and install reviewed skills into their Codex or Claude Code folders.
- Bundle 37 AI Hero and 47 PStack skills with nested discovery, supporting files, licenses, and source attribution.
- Recommend skills using the destination agent's own history, with editable previews, overlap comparisons, and first-step prompts.
- Keep project notes, saved suggestions, and dismissals separate for each agent and project.
- Record new installations, collect local usefulness assessments, and offer reviewed undo that preserves modified files and archives unchanged copies.
- Add local agent readiness checks and editable feedback reports that open GitHub drafts without sending telemetry.
- Add a five-step first-launch walkthrough with high-resolution screenshots and a release-specific What's new panel.
- Show Update Ready in the sidebar and move printing to Print Cheatsheet in Quick reference.

## 0.2.6

- Show the selected skill count and disable installation when no skills are selected.
- Hide duplicate package entries on request, explain why they are excluded, and describe how to resolve conflicts.
- Select a receiver immediately after finding it by address.
- Show transfer success dialogs with package review and a close-and-stop-sharing action.

## 0.2.5

- Send skill packages directly to another Skill-Desk device on your local network, without another app or a hosted service.
- Discover receivers automatically or enter an address; compare security codes, enter a PIN and accept each incoming package.
- Encrypt transfers, report progress, validate received data and retain import review before installation.
- Stop network listeners when sharing closes, expires or loses its UI connection.
- Fix the immediate Manage refresh after bulk package installation and add packaged transfer tests on every platform.

## 0.2.4

- Export selected skills as portable packages and import multiple skills with preview and conflict checks.
- Preserve supporting files and invocation settings across devices without a hosted service.
- Remove personal seed data from the app template and make the public root the marketing page.
- Fix the marketing provider selection indicator and document source builds and website deployment.

## 0.2.3

Move updater window creation off synchronous event callbacks to avoid Windows WebView2 deadlocks. Make status IPC asynchronous, report window creation failures, and exercise the actual Windows updater UI in CI before publishing.

## 0.2.2

Add a dark default theme, remembered appearance, refined navigation, accessible focus and hover states, and reduced-motion support across the app and demo. Correct provider-specific prompt copying and quick-reference skill names. Refresh the demo’s cross-platform installation and updater information.

## 0.2.1

Not released. Windows CI caught a text-encoding error in the shared-theme build check.

## 0.2.0

Introduce signed in-app updates, native progress and retry controls, a GitHub update feed, and Linux AppImage distribution. Active skill work completes before installation.

## 0.1.4

Add harness filtering, harness labels, and previewed cross-harness copying with destination conflict checks.

## 0.1.3

Complete the personal library discovery fix without a redundant home-directory lookup. Version 0.1.2 did not pass Windows CI and was not released.

## 0.1.2

Discover personal Codex and Claude skill folders alongside shared skills, with location overrides, linked-folder deduplication, and live updates for newly created folders.

## 0.1.1

Repository documentation and attribution corrections. See [release notes](docs/releases/v0.1.1.md).

## 0.1.0

Initial desktop preview. See [release notes](docs/releases/v0.1.0.md) for capabilities and known limits.
