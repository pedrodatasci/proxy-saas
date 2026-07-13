# Proxy Latency Board

A $0 SaaS that scrapes free public proxies, tests their latency every ~10
minutes, drops the dead ones, and shows the survivors sorted by speed.

**No server. No database bill. No always-on process.** The whole thing runs on
free GitHub infrastructure:

| Concern      | How it's $0                                                  |
|--------------|--------------------------------------------------------------|
| Scheduler    | GitHub Actions cron (`*/10 * * * *`)                          |
| Compute      | GitHub-hosted runners (free minutes; unlimited on public repos) |
| Database     | the git repo — each run commits `docs/data/proxies.json`     |
| Hosting      | GitHub Pages serves the static frontend                      |

```
Actions (every 10m) → scrape sources → test latency → write proxies.json → commit
                                                              │
                                    GitHub Pages → index.html → fetch proxies.json
```

## How the recheck loop works

Each run tests `(last run's survivors) ∪ (freshly scraped candidates)`.
A proxy that responds is kept and its latency/uptime updated. A proxy that
fails `MAX_FAILS` times in a row (default 2) is evicted. State lives in
`docs/data/state.json`.

## Deploy in 4 steps

1. **Create a repo** and push this folder to it (a **public** repo gets
   unlimited Actions minutes).
2. **Enable Pages:** repo → Settings → Pages → *Deploy from a branch* →
   branch `main`, folder `/docs` → Save.
   Your board is then at `https://<user>.github.io/<repo>/`.
3. **Enable Actions:** the Actions tab → enable workflows. Open
   *check-proxies* → **Run workflow** to trigger the first scan immediately
   (the cron takes over after that).
4. Wait a couple of minutes, refresh the Pages URL — proxies appear.

> Note: GitHub pauses scheduled workflows after 60 days with no repo activity,
> and scheduled runs can be delayed under load — treat "10 min" as approximate.

## Tuning

Set as env vars in `.github/workflows/check.yml`:

| Var            | Default | Meaning                                  |
|----------------|---------|------------------------------------------|
| `CONCURRENCY`  | 600     | simultaneous proxy checks                |
| `TIMEOUT`      | 8       | seconds before a proxy is called dead    |
| `MAX_FAILS`    | 2       | consecutive fails before eviction        |
| `MAX_CANDIDATES` | 40000 | safety ceiling on proxies tested per run |

## Adding / removing sources

Edit the `SOURCES` list in `checker/sources.py`. Each entry is a raw text URL
and a default protocol. Both `ip:port` and `scheme://ip:port` formats parse
automatically; dead source URLs are skipped, not fatal.

## Run locally

```bash
pip install -r checker/requirements.txt
python -m checker.main         # writes docs/data/proxies.json
cd docs && python -m http.server   # open http://localhost:8000
```

## Ideas to extend

- **Country/geo:** add MaxMind GeoLite2 (free key) or an offline IP DB.
- **Anonymity level:** test against an echo endpoint and inspect forwarded headers.
- **HTTPS support test:** request an `https://` target through each proxy.
- **API:** the committed `proxies.json` already *is* a public JSON API.

---

Free public proxies are unvetted and often short-lived — fine for scraping or
testing, never for anything sensitive.
