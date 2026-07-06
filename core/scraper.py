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

