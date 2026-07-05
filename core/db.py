import sqlite3
import logging 
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path 
from typing import Generator 

log = logging.getLogger(__name__)

#resolve db path relative to ts file so the projec is portable 
#override by passing path in tests
_DEFAULT_PATH = Path(__file__).parent.parent/ "data"/ "tracker.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

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
    keyword TEXT NOT NULL,
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
    label TEXT,
    added_at TEXT NOT NULL,
    UNIQUE(slack_id, topic_id,url)
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


#topics


def add_topic(keyword: str, slack_id: str, db_path: Path = _DEFAULT_PATH) -> int | None :
    """
    Add a new topic to the database. Returns the topic id if successful, or None if the topic already exists.
    """
    try:
        with _connect(db_path) as conn:
            cur=conn.execute(
                "INSERT INTO topics (slack_id, keyword, added_at) VALUES (?, ?, ?)",
                (slack_id, keyword.strip().lower(), _now())
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        log.debug("already tracked by %s: %s", slack_id, keyword)
        return None 
            
def get_active_topics(slack_id: str, db_path: Path = _DEFAULT_PATH) -> list[sqlite3.Row]:
    """
    Get all active topics for a given_slack_id. Returns a list of sqlite3.Row objects.
    has a sertial column with 1,2,3,4.... which is displayed by /mel-atcive 
    and /mel-edit {serial} resolves against this

    """
    with _connect(db_path) as conn:
        return conn.execute(
            """SELECT *, ROW_NUMBER() OVER (ORDER BY added_at) AS serial 
            FROM topics 
            WHERE slack_id = ? AND active = 1
            ORDER BY added_at""",
            (slack_id,)
        ).fetchall()
    

def resolve_serial(slack_id: str, serial: int, db_path: Path = _DEFAULT_PATH) -> sqlite3.Row | None:
    """
    resolve a serial number to a topic for a given slack_id. Returns the topic row if found, or None if not found.
    also called by /mel-edit {serial} before touching sources
    """

    rows = get_active_topics(slack_id, db_path)
    # serial is 1-indexed from the display, list is 0-indexed
    return rows[serial-1] if 0<serial<=len(rows) else None


def deactivate_topic(slack_id: str, topic_id: int, db_path: Path = _DEFAULT_PATH) -> bool:
    """Soft delete, scanning is stopped but history is preserved """

    with _connect(db_path) as conn :
        cur = conn.execute(
            "UPDATE topics SET active = 0 WHERE id = ? AND slack_id = ?"
            ,(topic_id, slack_id),
        
        )
        return cur.rowcount > 0  # true if row was updated otherwise gives false
    
def get_topic_by_keyword(keyword: str, slack_id: str, db_path: Path = _DEFAULT_PATH)-> sqlite3.Row | None:
    with _connect(db_path) as conn:
        return conn.execute(
            "SELECT * FROM topics WHERE keyword = ? AND slack_id = ?",
            (keyword.strip().lower(), slack_id)
        ).fetchone()


#signals

def store_signal(
        topic_id: int,
        title: str,
        url: str,
        summary: str | None = None ,
        db_path: Path = _DEFAULT_PATH,) -> int | None:
    """"""""
    try:
        with  _connect(db_path) as conn:
            cur = conn.execute(
                """INSERT INTO signals (topic_id, title, url, summary, caught_at) VALUES (?, ?, ?, ?, ?)""",
                (topic_id, title, url, summary, _now())
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        log.debug("already stored: %s", url )
        return None
    
def get_recent_signals(
        topic_id: int,
        limit: int = 3,
        db_path: Path= _DEFAULT_PATH

)-> list[sqlite3.Row]:
    """ last n signals for a topic which gemini gets as ctxt"""
    with _connect(db_path) as conn:
        return conn.execute(
            """SELECT * FROM signals WHERE topic_id = ?
            ORDER BY caught_at DESC LIMIT ?""",
            (topic_id, limit),

        ).fetchall()
    
def known_urls(topic_id: int, db_path: Path = _DEFAULT_PATH)-> set[str]:
    """stores every url for a topic and is checkd by scraper before clustering 
    returns a set"""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT url FROM signals WHERE topic_id = ?", (topic_id,)
        ).fetchall()
        return {row["url"] for row in rows}
    

def signal_history(
        topic_id: int,
        limit: int = 20,
        db_path: Path = _DEFAULT_PATH,
) -> list[sqlite3.Row]:
    """caught signals for a topic in reverse order """
    with _connect(db_path) as conn:
        return conn.execute(
            """ SELECT * FROM signals WHERE topic_id = ? ORDER BY caught_at DESC LIMIT ?""",
            (topic_id, limit)
        ).fetchall()

#sources 

def add_source(
        slack_id: str,
        url: str,
        label : str | None = None,
        topic_id: int | None = None,
        db_path: Path = _DEFAULT_PATH,
        
) -> int | None:
    """
    add a customn news source for a user 
    topic id = None  is global and applies to all trackings
    topic id = <id> is scoped to a single only
    """
    try:
        with _connect(db_path) as conn:
            cur = conn.execute(
                """ INSERT INTO sources (slack_id, topic_id, url, label, added_at)
                VALUES (?, ?, ?, ?, ?)""",
                (slack_id, topic_id, url, label, _now()),

            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        log.debug("source already exists for %s: %s", slack_id, url)
        return None

def remove_source(slack_id: str, source_id: int, db_path: Path = _DEFAULT_PATH) -> bool:
    """remove a source for a user"""
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM sources WHERE id = ? AND slack_id = ?",
            (source_id, slack_id)


        )
        return cur.rowcount > 0
    
def get_sources(
        slack_id: str,
        topic_id: int | None = None,
        db_path: Path = _DEFAULT_PATH,

)-> list[sqlite3.Row]:
    """
    fetch sources for a user
    topic_id=None  > global sources only (/mel-edit global view).
    topic_id=<id>  >  scoped + globals merged, scoped listed first.
    
    called by scraper for feed list
    """

    with _connect(db_path) as conn:
        if topic_id is None:
            return conn.execute(
                """SELECT * FROM sources 
                WHERE slack_id = ? AND topic_id IS NULL
                ORDER BY added_at""",
                (slack_id,),
                
                
            ).fetchall()
        return conn.execute(
            """SELECT * FROM sources
            WHERE slack_id = ? AND (topic_id = ? OR topic_id IS NULL)
            ORDER BY topic_id IS NULLS LAST, added_at""",
            (slack_id, topic_id)
        ).fetchall()