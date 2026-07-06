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

#public 

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

