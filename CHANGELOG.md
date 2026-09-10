# Changelog

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
