# TikTok Safety Model — v0.1.4

The company account is STRICT READ ONLY.

The TikTok tab runs in normal Google Chrome, not in Playwright-controlled Chromium.

The Product Hunter Companion extension may:
- read current URL
- read document title
- read visible page text for coarse state signals
- send heartbeat to localhost
- navigate an existing TikTok tab to the fixed /search route for an explicit SEARCH command

It may not:
- click
- like
- comment
- reply
- follow/unfollow
- share/repost
- save/favorite
- send messages
- publish
- edit profile/settings
- read passwords
- read authentication cookie values
- bypass CAPTCHA/security checks

No stealth or browser-fingerprint manipulation is part of this project.
