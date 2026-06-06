import sqlite3
import logging 
from contextlib import contextmanager
from pathlib import Path 
from typing import Generator 

log = logging.getLogger(__name__)

#resolve db path relative to ts file so the projec is portable 
#override by passing path in tests
_DEFAULT_PATH = Path(__file__).parent.parent/ "data"/ "tracker.db"
