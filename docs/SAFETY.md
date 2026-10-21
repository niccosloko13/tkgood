# TikTok Safety Model — v0.1.4

The company account is STRICT READ ONLY.

The TikTok tab runs in normal Google Chrome, not in Playwright-controlled Chromium.

The Product Hunter Companion extension may:
- read current URL
- read document title
- read visible page text for coarse state signals
- send heartbeat to localhost
- navigate an existing TikTok tab to the fixed /search route for an explicit SEARCH command
- read only the visible DOM of the current /search page for an explicit READ_SEARCH_RESULTS command
- send at most 100 unique visible video observations per manual capture to localhost

It may not:
- click
- like
- dislike
- comment
- reply
- follow/unfollow
- share/repost
- save/favorite
- send messages
- publish
- edit profile/settings
- edit account/settings
- read passwords
- read authentication cookie values
- bypass CAPTCHA/security checks

No stealth or browser-fingerprint manipulation is part of this project.

Search Capture never clicks, scrolls, expands cards, opens comments, follows result
links, inspects page scripts/internal state, or requests TikTok APIs. The only
network destination used by the extension is the local backend; SEARCH alone
navigates the existing normal Chrome tab. No Playwright is added to this flow.

Video links must be HTTPS TikTok /@username/video/numeric-id URLs. Tracking query
parameters and fragments are removed for deduplication. Text and metrics must be
rendered inside the viewport; absent or hidden fields stay null. Usernames are
not inferred from URLs. Reading visible metric labels does not activate buttons.
No generic click(selector), cookie/token/password access, CAPTCHA bypass, stealth,
webdriver modification, fingerprint spoofing, AI or product scoring is provided.
