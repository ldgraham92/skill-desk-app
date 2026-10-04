# App updates

The desktop's Updates button and tray menu open a native updater window. It checks the GitHub update feed at most once a day automatically and offers an explicit Check for updates button. Available releases show notes and an Update and restart action. The download is signature-verified before installation. Skill jobs and outstanding previews must finish before the service pauses mutations and the app restarts.

When a release is available, an Update Ready button with a download icon appears at the bottom of the main sidebar. It opens the updater to review and install the release. The indicator also shows download and installation states, remains available after a failed retry, and disappears when a successful check reports that the app is current.

Windows uses the per-user NSIS updater. macOS uses an application update archive. Linux users who want in-app updates should use AppImage; Debian packages remain managed by the system package manager. Publisher signing and macOS notarization are separate from the required updater signature.

The app replaces its own binaries; skill directories, preferences, and CLI credentials are not installation targets. Cross-harness skill copies remain independent of app updates.

## Legacy v0.4.0 installations

The old public repository is being retained privately. Existing v0.4.0 clients still point to its updater feed and will need a manual install of the next verified clean release. They can continue using their installed app. The new repository's `updates` branch intentionally has no `latest.json` until a clean, signed release is approved; it must never advertise the old website-containing installers.

The existing public updater key is retained. Its private key is not copied, logged, or configured by this migration. Release publication requires the owner to configure signing securely and approve the exact new version and artifacts. `RELEASE_PUBLICATION_ENABLED` is unset by default, so source tags alone cannot publish a release.

## Publish an update

1. Increment the version in package.json, package-lock.json, Cargo.toml, Cargo.lock, and tauri.conf.json.
2. Add docs/releases/vVERSION.md and update CHANGELOG.md.
3. Push the code and matching annotated vVERSION tag.
4. After signing setup and exact artifact approval, enable `RELEASE_PUBLICATION_ENABLED` for the approved release. GitHub Actions tests and builds all platforms, signs updater bundles, publishes an immutable release, and then advances latest.json on the updates branch.

Normal main pushes run validation. Only version tags publish updates. Users receive each published version through the updater; they do not need to download a new installer. Versions before the updater was introduced require one manual upgrade.

The feed uses the updates branch because this project's preview releases are not selected by GitHub's latest-release redirect. Installers and signatures stay on the versioned release. The feed advances only after the complete release is published and will not move backward to an older version.

## Signing key

Generate the updater key outside the repository using the Tauri signer. Store a protected backup. Put its private value in the repository Actions secret TAURI_SIGNING_PRIVATE_KEY. Only the public key belongs in tauri.conf.json. Never commit the private key, paste it into documentation, or print it in workflow logs. Pull-request and main validation builds use unsigned.conf.json and receive no signing key.

An OSS fork must generate its own signing key and change the repository/feed URLs before distributing builds. Do not reuse another project's identity or update feed.

## Recovery

If a check or download fails, retry from Updates. A bad signature prevents installation. If installation itself fails after the service stops, quit and reopen the existing app before retrying. A manual installer remains available on GitHub Releases as a recovery option.

If release publication succeeds but the feed update fails, inspect the published latest.json and update the feed to that exact version. Do not replace immutable installer assets or regenerate their signatures. A new signing key requires a migration plan for already-installed clients.
