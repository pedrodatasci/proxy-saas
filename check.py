"""
Latency test for a single proxy.

We route a tiny request through the proxy to a known "generate 204" endpoint
(a few bytes, no body) and measure round-trip time. aiohttp_socks gives one
connector that speaks HTTP, SOCKS4 and SOCKS5, so all protocols share a path.
"""
import time
import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType

# Endpoints that return an empty 204. First to answer wins the latency number.
# All tiny and CORS/edge-cached, so they rarely become the bottleneck.
TEST_URL = "http://cp.cloudflare.com/generate_204"
FALLBACK_URL = "http://www.gstatic.com/generate_204"

PROXY_TYPES = {
    "http": ProxyType.HTTP,
    "socks4": ProxyType.SOCKS4,
    "socks5": ProxyType.SOCKS5,
}


async def _try(url, host, port, ptype, timeout):
    connector = ProxyConnector(proxy_type=ptype, host=host, port=port, rdns=True)
    start = time.perf_counter()
    async with aiohttp.ClientSession(
        connector=connector,
        timeout=aiohttp.ClientTimeout(total=timeout),
    ) as session:
        async with session.get(url) as resp:
            await resp.read()
            if resp.status in (200, 204):
                return (time.perf_counter() - start) * 1000
    return None


async def check(host, port, protocol, sem, timeout=8.0):
    """
    Return latency in ms if the proxy works, else None.
    `sem` is a shared asyncio.Semaphore that caps total concurrency.
    """
    ptype = PROXY_TYPES.get(protocol)
    if ptype is None:
        return None
    async with sem:
        for url in (TEST_URL, FALLBACK_URL):
            try:
                latency = await _try(url, host, port, ptype, timeout)
                if latency is not None:
                    return round(latency, 1)
            except Exception:
                continue
    return None
