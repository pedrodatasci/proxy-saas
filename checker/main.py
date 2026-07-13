"""
Orchestrator — one full cycle:

  1. Load last run's survivors from state.json
  2. Scrape all sources for fresh candidates
  3. Test  (survivors ∪ candidates)  concurrently, measuring latency
  4. Keep whatever responds; evict anything that has failed MAX_FAILS times
  5. Write docs/data/proxies.json (sorted by latency) + state.json

Tunables live at the top and are overridable via env vars so you can adjust
them from the GitHub Actions workflow without editing code.
"""
import os
import json
import time
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from .sources import gather_candidates
from .check import check

# ---- tunables -------------------------------------------------------------
CONCURRENCY = int(os.getenv("CONCURRENCY", "500"))   # simultaneous checks
TIMEOUT = float(os.getenv("TIMEOUT", "8.0"))         # per-proxy seconds
MAX_FAILS = int(os.getenv("MAX_FAILS", "2"))         # consecutive fails before eviction
MAX_CANDIDATES = int(os.getenv("MAX_CANDIDATES", "40000"))  # safety ceiling per run
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"
STATE_FILE = DATA_DIR / "state.json"
OUTPUT_FILE = DATA_DIR / "proxies.json"


def key(host, port, proto):
    return f"{proto}://{host}:{port}"


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


async def run():
    started = time.perf_counter()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state = load_state()  # key -> {first_seen, last_ok, checks, oks, fail_streak, host, port, protocol}

    print("Fetching sources...")
    candidates = await gather_candidates()
    print(f"Scraped {len(candidates)} unique candidates")

    # Build the working set: everything we knew was alive + everything just scraped.
    work = {}
    for k, rec in state.items():
        work[k] = (rec["host"], rec["port"], rec["protocol"])
    for host, port, proto in candidates:
        work.setdefault(key(host, port, proto), (host, port, proto))

    items = list(work.items())
    if len(items) > MAX_CANDIDATES:
        items = items[:MAX_CANDIDATES]
    print(f"Testing {len(items)} proxies (concurrency={CONCURRENCY}, timeout={TIMEOUT}s)...")

    sem = asyncio.Semaphore(CONCURRENCY)

    async def worker(k, triple):
        host, port, proto = triple
        latency = await check(host, port, proto, sem, TIMEOUT)
        return k, triple, latency

    results = await asyncio.gather(*[worker(k, t) for k, t in items])

    new_state = {}
    alive = []
    for k, (host, port, proto), latency in results:
        rec = state.get(k, {
            "first_seen": now, "last_ok": None,
            "checks": 0, "oks": 0, "fail_streak": 0,
        })
        rec.update({"host": host, "port": port, "protocol": proto})
        rec["checks"] += 1
        if latency is not None:
            rec["oks"] += 1
            rec["last_ok"] = now
            rec["fail_streak"] = 0
            rec["latency"] = latency
            new_state[k] = rec
            alive.append({
                "host": host,
                "port": port,
                "protocol": proto,
                "latency_ms": latency,
                "uptime": round(100 * rec["oks"] / rec["checks"], 1),
                "checks": rec["checks"],
                "first_seen": rec["first_seen"],
                "last_ok": rec["last_ok"],
            })
        else:
            rec["fail_streak"] += 1
            if rec["fail_streak"] < MAX_FAILS:
                new_state[k] = rec  # keep on probation
            # else: evicted (dropped from state entirely)

    alive.sort(key=lambda p: p["latency_ms"])

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(new_state, indent=0))
    OUTPUT_FILE.write_text(json.dumps({
        "updated": now,
        "count": len(alive),
        "took_seconds": round(time.perf_counter() - started, 1),
        "proxies": alive,
    }, indent=1))

    print(f"Done: {len(alive)} alive / {len(items)} tested "
          f"in {time.perf_counter() - started:.0f}s")


if __name__ == "__main__":
    asyncio.run(run())
