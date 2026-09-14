# Architecture note — Grok wakes (Sep 2026)

Fast path: Python notify (mock JSONL → later SMS/Discord). Never waits on Grok.

Slow path: after notify, POST to configured webhooks (`src/jobradar/grok.py`).  
If specialist webhook URL/key UI is unavailable, configure **Director only**; Director messages specialists in the JobRadar group.

HTTP 200 from a Grok webhook means the run **started**, not finished.
