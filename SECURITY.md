# Security policy

Report vulnerabilities through [GitHub private vulnerability reporting](https://github.com/ldgraham92/skill-desk/security/advisories/new). Please do not post exploit details or credentials in a public issue.

Include the affected version, operating system, reproduction steps and expected impact. Use a temporary skill library. Remove account tokens, private prompts and personal paths from attachments. Maintainers will investigate as availability permits; this volunteer project does not promise a response SLA.

Security fixes target the latest release and `main`. Early 0.x releases are previews.

Skill-Desk runs locally and can install skill files and launch signed-in authoring CLIs. Importing a repository does not execute its scripts, but a skill may ask your agent to execute them later. Review imported instructions and resources. AI creation and reference generation send their input to the selected CLI provider and use that account's allowance.

Desktop installers are currently unsigned. Download them from this repository's Releases page and compare the provided SHA-256 checksum when verifying file integrity. Checksums do not replace publisher signing.
