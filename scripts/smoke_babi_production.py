"""Read-only public production smoke test; no secrets or writes."""
from __future__ import annotations
import json
import sys
from urllib import request, error

BASE = "https://babi-product-hunter.vercel.app"
PATHS = [
    "/api/v2/tiktok-sync/status",
    "/api/v2/library?page=1&page_size=2",
    "/api/v2/home",
    "/api/v2/discovery",
    "/api/v2/opportunities",
    "/api/v2/system",
    "/api/v2/market-radar/overview",
]

def main():
    failures = 0
    for path in PATHS:
        try:
            req = request.Request(BASE + path, headers={"Accept": "application/json", "User-Agent": "BabiSmokeTest/1.0"})
            with request.urlopen(req, timeout=20) as response:
                status = response.status
                data = json.loads(response.read(100000))
            assert isinstance(data, dict), "unexpected JSON type"
            verdict = "PASS" if status == 200 else "FAIL"
            note = ""
            if path.startswith("/api/v2/tiktok-sync/status"):
                count = data.get("count")
                note = f"storage={data.get('storage')} count={count} synced={bool(data.get('last_synced_at'))}"
                if data.get("storage") != "NEON_MIRROR" or not isinstance(count,int) or count < 83:
                    verdict = "FAIL"
            if path.startswith("/api/v2/library"):
                note = f"storage={data.get('storage')} total={data.get('total')}"
                if data.get("storage") != "NEON_MIRROR" or not isinstance(data.get("total"),int) or data["total"] < 83:
                    verdict = "FAIL"
                else:
                    videos = data.get("items",[])
                    if videos:
                        video_id = videos[0].get("video_id")
                        if video_id:
                            from urllib.parse import quote
                            with request.urlopen(request.Request(BASE+"/api/v2/library/"+quote(str(video_id), safe=""),
                                 headers={"Accept":"application/json"}),timeout=20) as detail:
                                d = json.loads(detail.read(100000))
                            if d.get("video_id") != video_id:
                                verdict = "FAIL"
                                note += " detail_mismatch"
            print(f"{verdict} {path} HTTP {status} {note}")
            failures += verdict == "FAIL"
        except (error.HTTPError, error.URLError, TimeoutError, ValueError, AssertionError) as exc:
            print(f"FAIL {path} {type(exc).__name__}: {str(exc)[:140]}")
            failures += 1
    print(f"RESULT: {len(PATHS)-failures}/{len(PATHS)} endpoints passed")
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
