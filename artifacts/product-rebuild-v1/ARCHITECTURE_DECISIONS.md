# Product Rebuild V1 — Architecture Decisions

1. The legacy static dashboard remains operational and unchanged as the active
   interface during V2 development.
2. `ui-v2/` is an independent Vite + React + TypeScript frontend. FastAPI,
   SQLite, the Chrome bridge and all safety components remain Python-owned.
3. UI V2 will consume read models (`/api/v2/*`) rather than reconstructing
   product intelligence from many browser-facing endpoints.
4. The main navigation is limited to Visão Geral, Descobrir, Oportunidades,
   Biblioteca and Sistema. Diagnostics move behind Sistema.
5. Publication timestamps are never inferred from Babi detection time.
