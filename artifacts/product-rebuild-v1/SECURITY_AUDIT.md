# Product Rebuild V1 — Security Audit

## Finding: tracked extension private key

`extension.pem` is present in the working tree and tracked by Git. It is a
private-key-formatted extension identity file and must be treated as exposed,
because prior commits are already published remotely.

## Immediate containment

- Added `*.pem` to `.gitignore`.
- The key is being removed from future Git tracking only; the local file is
  preserved so the currently installed extension identity is not disrupted.
- No key material is reproduced in this report.

## Required follow-up before a public release

1. Generate a replacement extension signing identity in a controlled step.
2. Update the installed extension/profile deliberately.
3. Verify the new extension ID and backend provisioning.
4. Remove the old key from reachable Git history with owner-approved history
   rewrite, then force-push according to repository policy.

`.env`, runtime state, browser profiles and database files are already ignored.
