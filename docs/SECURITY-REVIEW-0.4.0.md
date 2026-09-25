# Security review for 0.4.0

Reviewed against baseline `0572d138d0e48953672c2dd731562a0a648ffe63`. This is same-assistant source and behavior review, not independent certification. No alerts were dismissed, scanner paths excluded, bot PRs merged, or checks suppressed. The original recommendation failure remains unexplained because its response was not retained.

## Dependency alerts

GitHub reports all 19 original Dependabot alerts fixed after dependency commit `708afc0`. Pillow is a build dependency used to generate known icons; retaining vulnerable versions was unnecessary even without an identified untrusted-image input. The macOS helper archive was checked and contains no PIL/Pillow modules. This does not establish what older or other-platform archives contain.

The Linux GTK stack requires glib 0.18. Adding glib 0.20 alongside it would leave the affected copy present. The sole resolved glib dependency now uses the published 0.18.5 crate with exactly the upstream PR #1343 two-line fix. See [provenance and maintenance requirements](../src-tauri/vendor/GLIB-BACKPORT.md). The entire crate is checked against its published checksum, and optimized iterator regressions exercise next, next_back, nth, nth_back and last. GitHub's handling of a path dependency alone is not proof of remediation.

| Alert | Advisory | Affected range | First patched | Disposition |
| --- | --- | --- | --- | --- |
| #1 | [GHSA-cfh3-3jmp-rvhc](https://github.com/advisories/GHSA-cfh3-3jmp-rvhc) | `>= 10.3.0, < 12.1.1` | 12.1.1 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #2 | [GHSA-whj4-6x5x-4v2j](https://github.com/advisories/GHSA-whj4-6x5x-4v2j) | `>= 10.3.0, < 12.2.0` | 12.2.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #3 | [GHSA-5xmw-vc9v-4wf2](https://github.com/advisories/GHSA-5xmw-vc9v-4wf2) | `>= 11.2.1, < 12.2.0` | 12.2.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #4 | [GHSA-wjx4-4jcj-g98j](https://github.com/advisories/GHSA-wjx4-4jcj-g98j) | `< 12.2.0` | 12.2.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #5 | [GHSA-r73j-pqj5-w3x7](https://github.com/advisories/GHSA-r73j-pqj5-w3x7) | `>= 4.2.0, < 12.2.0` | 12.2.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #6 | [GHSA-pwv6-vv43-88gr](https://github.com/advisories/GHSA-pwv6-vv43-88gr) | `>= 10.3.0, < 12.2.0` | 12.2.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #7 | [GHSA-62p4-gmf7-7g93](https://github.com/advisories/GHSA-62p4-gmf7-7g93) | `< 12.3.0` | 12.3.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #8 | [GHSA-8v84-f9pq-wr9x](https://github.com/advisories/GHSA-8v84-f9pq-wr9x) | `< 12.3.0` | 12.3.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #9 | [GHSA-5x94-69rx-g8h2](https://github.com/advisories/GHSA-5x94-69rx-g8h2) | `< 12.3.0` | 12.3.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #10 | [GHSA-45hq-cxwh-f6vc](https://github.com/advisories/GHSA-45hq-cxwh-f6vc) | `< 12.3.0` | 12.3.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #11 | [GHSA-phj9-mv4w-65pm](https://github.com/advisories/GHSA-phj9-mv4w-65pm) | `< 12.3.0` | 12.3.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #12 | [GHSA-4x4j-2g7c-83w6](https://github.com/advisories/GHSA-4x4j-2g7c-83w6) | `< 12.3.0` | 12.3.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #13 | [GHSA-xj96-63gp-2gmr](https://github.com/advisories/GHSA-xj96-63gp-2gmr) | `< 12.3.0` | 12.3.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #14 | [GHSA-fj7v-r99m-22gq](https://github.com/advisories/GHSA-fj7v-r99m-22gq) | `>= 5.2.0, < 12.3.0` | 12.3.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #15 | [GHSA-6r8x-57c9-28j4](https://github.com/advisories/GHSA-6r8x-57c9-28j4) | `< 12.3.0` | 12.3.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #16 | [GHSA-jjj6-mw9f-p565](https://github.com/advisories/GHSA-jjj6-mw9f-p565) | `>= 5.1.0, < 12.3.0` | 12.3.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #17 | [GHSA-vjc4-5qp5-m44j](https://github.com/advisories/GHSA-vjc4-5qp5-m44j) | `>= 8.2.0, < 12.3.0` | 12.3.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #18 | [GHSA-9hw9-ch79-4vh6](https://github.com/advisories/GHSA-9hw9-ch79-4vh6) | `< 12.3.0` | 12.3.0 | Fixed by Pillow 12.3.0; GitHub reports fixed after 708afc0. |
| #19 | [GHSA-wrw7-89jp-8q8g](https://github.com/advisories/GHSA-wrw7-89jp-8q8g) | `>= 0.15.0, < 0.20.0` | 0.20.0 | Upstream fix backported into the sole glib 0.18.5 dependency. GitHub reports fixed; optimized Linux regression and native CI remain gates. |


## Original CodeQL findings

| Alert | Disposition and source evidence |
| --- | --- |
| #1, test HTML regex | Fixed. Replaced the test-only script extraction regex with HTMLParser and malformed-attribute/end-tag regression coverage. No unsupported production XSS claim. GitHub reports fixed. |
| #2, Nearby all-interface bind | Intentional opt-in LAN discovery. Authenticated UI initiation, bounded datagrams, private-address filtering, TLS, fingerprint comparison, PIN attempt limits, receiver approval, one-use upload credentials, checksum/size/expiry checks, installation preview, timeout and shutdown were reviewed. Listener defaults remain inactive. Not dismissed. |
| #3, Nearby regex | Fixed. Deterministic parsing bounds input to 64 characters and validates private IPv4 plus an ASCII port in 1..65535 before connection. No unmeasured claim about the old pattern's exploit runtime. GitHub reports fixed. |
| #4, registered project path | Intended user-selected filesystem root. Actual POST handler requires Host/Origin/token authorization; project registration requires an absolute existing Git repository and rejects redirected agent directories. Boundary tests exercise the actual handler. Not dismissed. |
| #5, static asset path | Fixed. The original exact route allowlist already limited exposure. A constant route-to-filename map plus resolved web-root containment now makes the boundary explicit. Traversal, hostile Host and external symlink regressions pass. GitHub reports fixed. |

## Newly scanned maintenance paths

The first complete candidate scan at `d0b5f83` surfaced 35 additional Python path warnings. All begin in the authenticated local HTTP handler. The table follows the concrete traced values through their checks; authentication alone does not establish path safety. Findings remain visible in GitHub; no dismissal or suppression is used to obtain a clean count.

| Alerts | Source, boundary and sink | Disposition |
| --- | --- | --- |
| #13 | Saved draft ID to revision copy in AdvancedDrafts.remember_tree. | IDs must fully match 32 lowercase hex characters under the saved-drafts directory. Revisions are bounded unique integer indices, ordinary contained directories, inventory-checked and digest-verified before staging. Traversing/absolute/boolean indices and symlinks are tested. No arbitrary revision path reaches the copy. |
| #14–#20 | Supporting-file names and rename destinations to existence checks, mkdir, rename, unlink and write in an independent temporary draft. | portable_path rejects absolute, drive, backslash, dot-segment and reserved Windows paths. Existing files must be in the checked inventory; links are rejected. Review found a separate reserved-folder omission: rename to .git could silently discard the renamed file when staging. Add and rename now reject .git/.skilldesk path components. The regression fails before and passes after the fix; the original draft remains intact. |
| #21–#23 | Saved draft ID to directory checks and record.json read. | Strict full-match hex ID and an ordinary saved directory constrain the path. Traversal is rejected. Saved destinations must still be in the registered root set. |
| #24–#27 | Saved revision directories to symlink/is-dir/resolve checks. | These are the containment checks themselves, followed by bounded indices, inventory and digest verification. The check does not authorize arbitrary external reads. |
| #28–#29 | Saved draft ID to upstream-baseline directory check/copy. | Same constrained saved-draft directory. Workspace archives reject unsafe names and symbolic links before extraction. The baseline is copied to a fresh server-generated temporary ID. |
| #30 | Saved draft ID to rmtree. | Same strict ID and ordinary saved-directory check. Deletes that saved draft only; installed skills are preserved. Tested with malformed IDs and restart/reopen behavior. |
| #31–#33 | Saved revision path to tree_digest traversal/stat/read. | Receives contained inventory-validated revisions as described above; the digest routine independently rejects links and enforces a size bound. |
| #34–#43 | Saved draft path through stage to inventory, metadata/reference reads and copytree. | Same strict saved-draft ID, registered destination and validated inventory. Entry-point references must resolve inside the source tree. Supporting references are resolved and checked without opening external contents. Staging copies only into fresh temporary candidate directories. |
| #44 | History-exclusion strings to Path.expanduser and is_absolute. | Intended user-selected absolute exclusion paths, bounded to 100 strings of 2,000 characters each. This flow stores exclusions; it does not open arbitrary file contents. |
| #45 | Reconnect path to resolve. | Explicit user-selected repository root; all agent destinations are validated before preview, then revalidated on confirmation. Registration and existing skill contents are preserved. |
| #46 | Library-relocation path to resolve. | Explicit destination preview; existing, nested and overlapping destinations are rejected. Confirmation checks the original digest, destination absence and unchanged resolved parent before a journaled copy. Windows relocation remains unavailable and has a rejection regression. |
| #47 | Usage-preview payload through project_matches to resolve. | The HTTP handler replaces the supplied project value with Projects.get on a registered ID before calling the reader. Matching only selects history under that registered root; it does not accept an arbitrary project object from the request. Scope and sibling/nested repository regressions pass. |

## Newly scanned upstream Rust code

Vendoring made seven existing upstream locations visible to CodeQL. Source bytes match the published crate except for the documented iterator fix. The provided traces were inspected individually.

| Alerts | Disposition |
| --- | --- |
| #6–#7, ObjectRef conversions | The reported paths connect charset or GError pointers through generic from_glib helpers to GObject conversion implementations. Actual Rust return types select GString or Error, not ObjectRef. Error paths additionally test the returned pointer for null before conversion. These traces do not form callable paths to the reported GObject dereferences. |
| #8, boxed derive in cfg(test) | The trace similarly routes charset/Error conversions into generated MyBoxed conversion in an upstream test-only module. The concrete conversion types do not match; this test module is absent from the application dependency build. |
| #9–#10, GValue copy/clear | Reported charset/Error paths are again dispatched through unrelated generic GValue wrapper implementations. The concrete function return types select their corresponding conversions, not GValue. No reachable null dereference is established by these traces. |
| #11, PtrSlice.truncate | drop_in_place destroys the T value in a slot; it does not free the containing PtrSlice allocation. Writing a null sentinel to that same still-allocated slot is intentional. The len guard bounds the slot and length is decremented before access. |
| #12, cleartext logging | The source is g_uuid_string_is_valid's boolean result, routed by the analysis into LogLevel.from_glib's panic. uuid_string_is_valid returns bool and selects bool's conversion; it does not call LogLevel's u32 conversion. The traced value is a validity result, not a UUID or secret string. |

These dispositions concern the reported flows, not a claim that all upstream unsafe code has been proven correct. No vendor files were altered to silence the scanner.

## Dependabot PRs

Compatible changes were incorporated explicitly. Passing bot-branch builds were treated as compatibility evidence only; the combined candidate requires its own all-platform checks.

| PR | Local decision | Compatibility evidence and remaining limits |
| --- | --- | --- |
| [#6](https://github.com/ldgraham92/skill-desk/pull/6), reqwest 0.13.5 | Deferred; keep 0.12.28. | Breaking defaults change the TLS backend to rustls/AWS-LC and root verification; form/query support changes. The app's direct call is loopback JSON POST in `updates.rs`. This major migration is not required to resolve any of the reported 19 alerts. It needs separate compatibility coverage rather than broad lockfile churn. |
| [#7](https://github.com/ldgraham92/skill-desk/pull/7), PyInstaller 6.22.3 | Adopted pin. | Reviewed onefile parent/privilege handling and Windows junction/symlink/RAMDISK fixes. Rebuilt the helper in an isolated Python 3.13 environment, with fresh package and shutdown tests. Other platform bundles remain CI gates. |
| [#8](https://github.com/ldgraham92/skill-desk/pull/8), checkout v7 | Adopted both workflow occurrences. | Node 24 requires runner 2.327.1 or later; container credential support needs 2.329.0. Existing jobs use hosted runners, no container. Credentials move outside the working tree; the changed fork restrictions concern workflow_run/pull_request_target, which this workflow does not use. Permissions were not broadened. Exact-candidate CI still required. |
| [#9](https://github.com/ldgraham92/skill-desk/pull/9), setup-node v7 | Adopted. | Node 24 action runtime requires runner 2.327.1 or later; project Node stays 22. Existing explicit npm cache remains; no registry-auth/always-auth configuration needs migration. Exact-candidate CI still required. |
| [#10](https://github.com/ldgraham92/skill-desk/pull/10), Tauri CLI 2.11.5 | Adopted package and lock. | Generates version-bearing trusted comments in updater signatures. CLI update alone does not enforce signed versions in the updater; `requireSignedVersion` was not enabled. Fresh isolated macOS build passes. Signed delivery remains untested. |
| [#11](https://github.com/ldgraham92/skill-desk/pull/11), Tauri 2.11.6 | Adopted minimal Cargo lock change. | Upstream diff fixes GHSA-w28w-mhc8-qvjv with per-webview IPC queues/IDs and cleanup on close. The app uses multiple windows. This patch does not fix glib #19. |
| [#12](https://github.com/ldgraham92/skill-desk/pull/12), single-instance 2.4.5 | Adopted minimal Cargo lock change. | Actual plugin changelog grants the existing instance foreground permission on Windows. The bot body included the wrong plugin's changelog, so that body was not treated as sufficient evidence. Existing API usage is unchanged. Windows behavior still needs CI/native checks. |


## Release validation

The owner accepted automated Linux testing in place of hands-on Linux acceptance. Optimized glib regressions, the Linux package build and the isolated AppImage WebKit check remain release gates. The shared updater feed is unchanged until publication; a 0.x prerelease reaches existing updater users.

Fresh local tests cover unit, browser, packaged helper/transfer/shutdown and isolated macOS WebKit behavior. A disposable updater harness uses the actual locked updater plugin to verify the published 0.3.0 signature, reject bad signatures, preserve an old app after a malformed archive, and install the separately signed test candidate. The temporary test key is unrelated to the production key. Synthetic saved-state compatibility is verified separately. This does not substitute for checking the published candidate's signatures and immutable downloads after release.

Publication requires all-platform CI and security scans on the exact tagged commit. Immutable public downloads, checksums, signatures and the shared feed must then be verified. OpenCode history recommendations and Windows relocation stay unavailable; live Cursor access and manual VoiceOver acceptance are not claimed.
