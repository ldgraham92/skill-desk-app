# Local development checks

Run automated checks before testing with a signed-in agent:

```sh
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/check_version.py
.venv/bin/python scripts/sync_ui_assets.py --check
```

The unit suite uses disposable libraries and fake provider responses. It checks history parsing, cancellation, replacement rollback, package integrity, nearby transfer recovery, project paths, and diagnostic privacy. It makes no inference requests.

## Browser checks

With Node, Playwright, and Chrome already installed:

```sh
.venv/bin/python tests/run_ui_smoke.py /tmp/skilldesk-ui-evidence
```

If Playwright is outside Node's module search path, set `PLAYWRIGHT_MODULE` to its installed module directory. `PLAYWRIGHT_CHANNEL` defaults to `chrome`.

The runner starts a loopback server with temporary libraries, fake agent executables, and synthetic conversation history. It patches the fixture process's home-directory lookup and uses a narrow environment. It never opens a native Skill-Desk window. The page displays **TEST INSTANCE · Synthetic data · Temporary libraries**. The runner removes its server and libraries on success or failure. Screenshots, check results, and error evidence remain in the supplied directory outside the repository.

The browser suite exercises history coverage, edited recommendation evidence, capabilities, diagnostics, cancellation, failure recovery, installation, replacement, project scope, unsupported history agents, keyboard focus, themes, narrow layouts, duplicate copies, and large libraries. It uses fake agents, so it does not establish live account access or current CLI compatibility.

## Packaged helper and native app

```sh
.venv/bin/python scripts/build_sidecar.py
.venv/bin/python scripts/smoke_sidecar.py
npm run desktop:dev
```

Rust must be on PATH when building. The helper smoke test uses isolated state and a temporary skill library. It exercises the packaged executable without agent inference. Native debug builds display **LOCAL DEVELOPMENT BUILD**. The `SKILL_DESK_NO_AUTHOR=1` setting suppresses automatic description authoring during local inspection; manually requested agent jobs remain available.

`SKILL_DESK_TEST_MODE=1` is reserved for synthetic QA instances. Do not leave one open for normal use.

## Manual account validation

Use a disposable skill brief to test an installed and signed-in CLI. Check readiness first. Then create a preview, inspect its destination, cancel one run, and retry. Do not include private conversation history when validating a new integration.

Cursor remains covered by mocked adapters. OpenCode also has installed-CLI tests against a local fake model; those do not establish remote model access. Live account testing needs an available model through the installed CLI. History recommendations remain limited to Codex and Claude Code. Native Windows and Linux behavior needs testing on those operating systems; cross-platform path tests on macOS do not substitute for that.

These commands do not publish a release. Version changes, signing, updater deployment, and release publishing are separate work.

## Drafts and installed OpenCode checks

The browser suite also covers editing/validation/diffs, saved draft recovery, supporting files, agent revisions, multi-agent copies, identical/diverged copies, deeper scans, filters, model discovery, connection tests, and library health.

With OpenCode V2 installed, run each optional integration check:

```sh
.venv/bin/python tests/check_opencode_local.py normal
.venv/bin/python tests/check_opencode_local.py denied
.venv/bin/python tests/check_opencode_local.py inherited
.venv/bin/python tests/check_opencode_local.py slow
.venv/bin/python tests/history_benchmark.py
```

The OpenCode checks use a loopback fake model, temporary HOME/XDG directories, synthetic global rules/plugins/MCP, and no API keys. They verify response parsing, tool denial, inherited context, retention/export/delete, and cancellation cleanup. They do not modify the user's normal OpenCode configuration. The benchmark generates and removes its own history corpus, compares an independent full reader with bounded samples, and prints aggregate measurements.

## Maintenance and recovery

The maintenance unit tests cover three-way updates, immutable pins, old-import baselines, full-folder revisions, stale windows, backup tampering, filesystem recovery, project reconnection, relocation, and saved recommendation context. The browser suite now also exercises these workflows through real controls, including a narrow supporting-file editor.

```sh
.venv/bin/python -m unittest discover -s tests
.venv/bin/python tests/maintenance_benchmark.py
.venv/bin/python tests/maintenance_stress.py 300 /tmp/skilldesk-maintenance-stress.json
.venv/bin/python tests/packaged_shutdown_smoke.py
```

The soak test uses disposable synthetic skills. It checks temporary-file cleanup each cycle, samples RSS and child processes, and records intentionally retained recovery bytes separately. The packaged shutdown test shadows Codex with a synthetic sleeping executable in its own child-process PATH. It confirms that quitting during an active job kills its descendants, rejects another concurrent job, and records interruption without persisting the prompt or replaying it.

## Actual macOS and Linux WebKit interactions

Build the helper first, then create a local debug test bundle. The bundle has a separate identifier and does not produce updater artifacts. No distribution or publisher signing is performed.

```sh
python scripts/build_sidecar.py
npm run desktop:build -- --debug --bundles app --config '{"identifier":"ca.lgraham.skilldesk.localtest","productName":"Skill-Desk Test","bundle":{"createUpdaterArtifacts":false}}'
.venv/bin/python tests/run_native_smoke.py /tmp/skilldesk-native-evidence
```

`run_native_smoke.py` launches this actual app with temporary state and a temporary library. Its debug-only JavaScript hook exercises import, supporting-file edits, installation, maintenance search, and annotations inside WebKit. It records checks and JavaScript errors, then stops the app and removes the fixture. The hook requires both a debug Rust build and explicit test environment variables. Test mode suppresses automatic update checks. Release builds have no script injection hook.

This verifies actual WebKit interactions; it does not replace manual VoiceOver testing or native Windows/Linux acceptance checks.

On Linux, CI builds the same isolated debug app with `--bundles appimage` and runs
`xvfb-run -a python tests/run_native_smoke.py <evidence-directory>`. The runner
extracts the AppImage into a temporary directory so the bundled runtime is tested
without requiring FUSE. The optimized glib regression runs separately:

```sh
python scripts/check_glib_backport.py
cargo test --locked --release --manifest-path src-tauri/Cargo.toml --test glib_variant_iter
```

For 0.4.0, the owner accepted automated Linux validation in place of hands-on
Linux acceptance. Required automated failures still block publication.
