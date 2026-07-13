"""
Where free proxies come from.

Each source is a raw text URL plus the protocol its entries use. Most public
lists are plain `ip:port` per line; some use a `scheme://ip:port` format, which
the parser below also handles. These repos come and go — when one 404s it's just
skipped, and you can add/remove entries freely without touching anything else.
"""
import re
import asyncio
import aiohttp

# (url, default_protocol). If a line carries its own scheme:// it wins.
SOURCES = [
    # TheSpeedX/PROXY-List
    ("https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt", "http"),
    ("https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt", "socks4"),
    ("https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt", "socks5"),
    # monosans/proxy-list
    ("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt", "http"),
    ("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt", "socks4"),
    ("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt", "socks5"),
    # proxifly/free-proxy-list (scheme://ip:port format)
    ("https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt", "http"),
    # clarketm/proxy-list (http, ip:port with trailing flags — regex strips them)
    ("https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt", "http"),
    # ShiftyTR / Proxy-List
    ("https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt", "http"),
    ("https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt", "socks5"),
]

# scheme://host:port   OR   host:port   (host = IPv4 or domain)
LINE_RE = re.compile(
    r"(?:(?P<scheme>socks5|socks4|https?)://)?"
    r"(?P<host>(?:\d{1,3}\.){3}\d{1,3}|[a-zA-Z0-9.\-]+):(?P<port>\d{2,5})"
)

SCHEME_MAP = {"https": "http", "http": "http", "socks4": "socks4", "socks5": "socks5"}


def parse(text: str, default_protocol: str):
    """Yield (host, port, protocol) tuples from a raw proxy list."""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = LINE_RE.search(line)
        if not m:
            continue
        port = int(m.group("port"))
        if not (0 < port < 65536):
            continue
        proto = SCHEME_MAP.get(m.group("scheme"), default_protocol)
        yield (m.group("host"), port, proto)


async def _fetch(session, url, proto):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
            if r.status != 200:
                print(f"  ! {url} -> HTTP {r.status}")
                return []
            text = await r.text()
            found = list(parse(text, proto))
            print(f"  + {url} -> {len(found)}")
            return found
    except Exception as e:
        print(f"  ! {url} -> {type(e).__name__}")
        return []


async def gather_candidates():
    """Fetch every source concurrently and return a deduped set of proxies."""
    async with aiohttp.ClientSession(headers={"User-Agent": "proxy-checker"}) as s:
        results = await asyncio.gather(*[_fetch(s, u, p) for u, p in SOURCES])
    seen = set()
    for batch in results:
        for item in batch:
            seen.add(item)
    return seen
