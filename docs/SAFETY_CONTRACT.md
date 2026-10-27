# Canonical Safety contract v1

`config/safety_contract.json` lists the shared page and security states. Python
`app/safety.py` and Companion `extension/safety_gate.js` map the already existing
session/page detector evidence into this contract; they do not add a DOM detector.
Search admission also requires the existing fresh heartbeat, current TikTok home
or valid search route, build identity, account evidence and bounded settle checks.

Hard challenge/403 and confirmed logout block immediately. Loading and incomplete
evidence are bounded holds. A target quarantine blocks only that target; pending
target-health review holds the collector. `may_continue` never clears a persistent
global latch. Browser request observation, backend incident persistence and
explicit human release remain separate adapters.

Safety answers whether the existing authorized operation can proceed. It contains
no query planning, candidate priority, lifecycle inference or opportunity score.
