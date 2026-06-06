import sqlite3
import logging 
from contextlib import contextmanager
from pathlib import Path 
from typing import Generator 

log = logging.getLogger(__name__)

#resolve db path relative to ts file so the projec is portable 
#override by passing path in tests
_DEFAULT_PATH = Path(__file__).parent.parent/ "data"/ "tracker.db"

#connection 
@contextmanager
def _connect(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

#schema 

_SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_id TEXT NOT NULL,
    keyword TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    added_at TEXT NOT NULL
    UNIQUE(slack_id, keyword)

);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    summary TEXT,
    caught_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_id TEXT NOT NULL,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    UNIQUE(slack_id, url)
);

CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_id TEXT NOT NULL,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL,
    UNIQUE(slack_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_signals_topic ON signals(topic_id);
CREATE INDEX IF NOT EXISTS idx_signals_caught ON signals(caught_at DESC);
CREATE INDEX IF NOT EXISTS idx_sources_user ON sources(slack_id);
CREATE INDEX IF NOT EXISTS idx_sources_topic ON sources(topic_id);
CREATE INDEX IF NOT EXISTS idx_topics_user ON topics(slack_id);

"""

def init_db(db_path: Path = _DEFAULT_PATH) -> Path:
    """
    Boot the database. Safe to call multiple times; CREATE IF NOT EXISTS means repeat calls are
    no ops, returns the resolved path so callers can log or display it."""

    db_path.parent.mkdir(parents=True , exist_ok=True
    )
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)
    log.info("db ready at %s", db_path)
    return db_path 