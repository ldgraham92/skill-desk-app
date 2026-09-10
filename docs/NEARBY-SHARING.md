# Send skills to a nearby device

Nearby sharing is built into Skill-Desk on Windows, macOS and Linux. Install Skill-Desk on both devices; no separate LocalSend app, account, subscription or hosted service is needed.

## Receive on your other device

1. Open **Manage skills → Receive from device**.
2. Leave the window open. It shows a temporary device name, receiver PIN, security code and local address.
3. When the sender requests a transfer, choose **Accept package** or **Reject**.
4. After receipt, choose a destination library and **Review received package**.
5. Review the skills and included files, then choose **Install selected skills**.

Acceptance receives the ZIP into temporary memory. It does not install skills or run their scripts. Import uses the existing [package validation and conflict checks](SKILL-PACKAGES.md).

## Send selected skills

1. Open **Manage skills → Export package**.
2. Select the skills, choose **Review package**, and inspect the included files for private content.
3. Choose **Send to device** and select the receiving device.
4. Compare the displayed security code with the code on the receiver's screen. Confirm that they match and enter its six-digit PIN.
5. Choose **Request transfer**. The receiver must accept before any package content is sent.

Both devices must be online and reachable on the same local network. This feature transfers selected packages, not automatic updates to your entire library.

## If discovery does not find the receiver

Open **Connect using an address** in the sender window. Enter the IPv4 address and port shown by the receiver, then choose **Find device**. Compare security codes before sending, just as with automatic discovery.

Allow Skill-Desk local-network access if macOS requests it. Windows Firewall may ask about the bundled service; allow it on your trusted private network if you want to use nearby sharing. Guest Wi-Fi, client isolation, VPN routing and managed network policies can prevent devices from reaching one another. Skill-Desk does not change firewall rules or router settings.

The first version supports local IPv4 networks. It does not transfer across the public internet or discover IPv6-only peers. USB or file-based package transfer remains available if the network blocks sharing.

## Stop, reject and retry

**Stop sharing**, Close, or Escape closes the sharing listener and cancels local transfer work. A pending request on the other device may remain visible until it is rejected or expires. Pending approval expires after 90 seconds; an approved upload has a 120-second transfer deadline. Interrupted transfers are discarded and can be sent again; there is no partial-file resume.

Sharing sessions expire after 10 minutes. They also expire after 60 seconds without the sharing window checking in, including a closed browser tab or disconnected UI. A completed received package must be opened for review before the session expires. App updates wait for sharing to close.

## What is exposed while sharing

A dedicated temporary HTTPS listener handles transfer requests. It has no management, filesystem-browsing, skill-listing or installation endpoints. The existing application management API remains bound to loopback.

Discovery advertises a random session name, a certificate fingerprint, a port and transfer capability. It does not announce your hostname, skill names, files or CLI login. Local addresses are necessarily visible to devices on the same network.

Transfers use TLS with a fresh session certificate. The sender checks the complete certificate fingerprint before sending metadata or package bytes. Comparing the displayed security code establishes that you selected the intended receiver; device names alone are not verified identities. The receiver PIN and explicit acceptance provide additional checks. Ten incorrect PIN attempts block further offers for that session; reopen Receive to create a new session.

The receiver checks the transfer's SHA-256 digest before making it available for package review. A checksum detects changes, not whether skill instructions are safe. Review imported instructions and scripts before using them.

## Implementation scope

This implements the discovery and upload portion of the [LocalSend v2 protocol](https://github.com/localsend/protocol), with Skill-Desk-specific discovery metadata and a one-package limit. It is tested between Skill-Desk instances. General file sharing, browser downloads, remembered device trust and full interoperability with the standalone LocalSend app are not supported in this release.

UDP discovery uses multicast address `224.0.0.167` on port `53317`. HTTPS prefers TCP `53317` and selects an available port if it is occupied; the selected address is shown in Receive. Multicast responses are rate-limited. Metadata, simultaneous connections and package sizes are bounded. No sharing listener or discovery loop starts until you open Send or Receive.
