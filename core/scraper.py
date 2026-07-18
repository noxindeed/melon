import logging
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

log = logging.getLogger(__name__)

_DEFAULT_FEED = "https://news.google.com/rss/search?q={query}&hl=en-US&ceid=US:en"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

class ScrapeError(Exception):
    """a feed could not be reached  or xml could not be parsed"""

#public and internals 

def fetch_for_topic(
        keyword: str,
        source_urls: list[str] | None = None,
        timeout: int = 10,

) -> list[dict]:
    """
    need to explain ts later
    """
    templates  = source_urls or [_DEFAULT_FEED]
    seen_in_batch: set[str] = set()
    headlines: list[dict]=[]

    for template in templates:
        try:
            items = _fetch_one_feed(template,keyword,timeout)
        except ScrapeError as exc:
            log.warning("feed skipped: %s (%s)", template, exc)
            continue
        for item in items:
            if item["url"] in seen_in_batch:
                continue
            seen_in_batch.add(item["url"])
            headlines.append(item)
    return headlines 

def _matches_keyword(title: str, keyword: str) -> bool:
    return keyword.lower() in title.lower()

def _text(item: ET.Element, tag: str) -> str | None:

    node = item.find(tag)
    if node is not None and node.text:
        return node.text.strip()
    return None

def _parse_rss(xml_bytes: bytes) -> list[dict]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ScrapeError(f"bad xml: {exc}") from exc
    
    items = []
    for item in root.findall(".//item"):
        title = _text(item,"title")
        link = _text(item,"link")
        date = _text(item,"pubDate")
        if title and link:
            items.append({"title": title, "url": link, "date": date})

    return items


def _fetch_raw(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers ={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ScrapeError(f"could not fetch {url}: {exc}") from exc
    

def _fetch_one_feed(template: str, keyword: str, timeout: int) -> list[dict]:
    if "{query}" in template:
        url = template.format(query=urllib.parse.quote(keyword))
        return _parse_rss(_fetch_raw(url,timeout))
    
    raw = _fetch_raw(template,timeout)
    return [item for item in _parse_rss(raw) if _matches_keyword(item, keyword)]

def  filter_new(items: list[dict], seen_urls: set[str]) -> list[dict]:
    return [item for item in items if item["url"] not in seen_urls]