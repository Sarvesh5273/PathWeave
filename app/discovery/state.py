"""Durable local hunt/job/cache/accounting ledger, separate from FalkorDB reasoning.

SQLite transactions coordinate worker instances sharing this file. This is not a
distributed multi-host queue; FalkorDB remains the preparation context/evidence DB.
Runtime state is ignored by Git. Preparation ownership is enforced by the API's browser token.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from datetime import datetime,timezone
from contextlib import contextmanager
from pathlib import Path

from .contracts import DiscoveryListing, DiscoveryPreferences, EngineResult, RunEvent


class StateError(RuntimeError):
    pass


class DiscoveryState:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS hunts(id TEXT PRIMARY KEY, owner TEXT NOT NULL,
                name TEXT NOT NULL, preferences TEXT NOT NULL, created REAL NOT NULL,
                viewed REAL NOT NULL, next_refresh REAL, result TEXT);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, hunt TEXT NOT NULL,
                status TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                events TEXT NOT NULL DEFAULT '[]', error TEXT);
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON runs(hunt)
                WHERE status IN ('queued','running');
            CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, value TEXT NOT NULL,
                expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS usage(key TEXT PRIMARY KEY, amount REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS flags(hunt TEXT NOT NULL, listing TEXT NOT NULL,
                saved INTEGER NOT NULL DEFAULT 0, hidden INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(hunt, listing));
            """)
            if "progress" not in {row[1] for row in db.execute("PRAGMA table_info(runs)")}:
                db.execute("ALTER TABLE runs ADD COLUMN progress TEXT")

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def owner(client: str) -> str:
        return hashlib.sha256(client.encode()).hexdigest()

    def create_hunt(self, client: str, preferences: DiscoveryPreferences, name: str = "") -> dict:
        now = time.time()
        identifier = uuid.uuid4().hex
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT count(*) FROM hunts WHERE owner=?", (self.owner(client),)).fetchone()[0] >= 6:
                raise StateError("At most six hunts per browser; reuse an existing hunt.")
            db.execute("INSERT INTO hunts VALUES(?,?,?,?,?,?,?,NULL)",
                       (identifier, self.owner(client), name[:120] or ", ".join(preferences.roles)[:120],
                        preferences.model_dump_json(), now, now, now + 86400))
        return self.hunt(identifier, client)

    def hunt(self, identifier: str, client: str) -> dict:
        with self._db() as db:
            row = db.execute("SELECT * FROM hunts WHERE id=? AND owner=?", (identifier, self.owner(client))).fetchone()
            if not row:
                raise StateError("Hunt not found in this browser.")
            db.execute("UPDATE hunts SET viewed=? WHERE id=?", (time.time(), identifier))
        data = dict(row)
        data.pop("owner")
        data["preferences"] = json.loads(data["preferences"])
        data["result"] = json.loads(data["result"]) if data["result"] else None
        with self._db() as db:
            progress=db.execute("SELECT progress FROM runs WHERE hunt=? AND status='running' AND progress IS NOT NULL ORDER BY created DESC LIMIT 1",(identifier,)).fetchone()
        if progress:data["result"]=json.loads(progress[0])
        if data["result"]:
            with self._db() as db:
                flags = {r["listing"]: r for r in db.execute("SELECT * FROM flags WHERE hunt=?", (identifier,))}
            for listing in data["result"]["listings"]:
                flag = flags.get(listing["id"])
                listing["saved"] = bool(flag and flag["saved"])
                listing["hidden"] = bool(flag and flag["hidden"])
        return data

    def hunts(self, client: str) -> list[dict]:
        with self._db() as db:
            rows = db.execute("SELECT h.id,h.name,h.created,(SELECT id FROM runs r WHERE r.hunt=h.id ORDER BY created DESC LIMIT 1) AS latest_run FROM hunts h WHERE owner=? ORDER BY h.created DESC", (self.owner(client),)).fetchall()
        return [dict(r) for r in rows]

    def enqueue(self, hunt: str, client: str) -> dict:
        self.hunt(hunt, client)
        now, identifier = time.time(), uuid.uuid4().hex
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            active = db.execute("SELECT id FROM runs WHERE hunt=? AND status IN ('queued','running')", (hunt,)).fetchone()
            if active:
                return self.run(active[0], client)
            if db.execute("SELECT count(*) FROM runs WHERE status IN ('queued','running')").fetchone()[0] >= 10:
                raise StateError("Discovery queue is full; try later.")
            recent = db.execute("SELECT count(*) FROM runs WHERE created>?", (now - 3600,)).fetchone()[0]
            own = db.execute("SELECT count(*) FROM runs r JOIN hunts h ON h.id=r.hunt WHERE h.owner=? AND r.created>?",
                             (self.owner(client), now - 3600)).fetchone()[0]
            if recent >= 20 or own >= 6:
                raise StateError("Discovery hourly request limit reached; try later.")
            db.execute("INSERT INTO runs(id,hunt,status,created,updated) VALUES(?,?,'queued',?,?)", (identifier,hunt,now,now))
        return self.run(identifier, client)

    def claim(self, identifier: str) -> bool:
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT count(*) FROM runs WHERE status='running'").fetchone()[0] >= 2:
                return False
            return db.execute("UPDATE runs SET status='running',updated=? WHERE id=? AND status='queued'",
                              (time.time(), identifier)).rowcount == 1

    def run(self, identifier: str, client: str) -> dict:
        with self._db() as db:
            row = db.execute("SELECT r.*,h.result AS hunt_result FROM runs r JOIN hunts h ON r.hunt=h.id WHERE r.id=? AND h.owner=?",
                             (identifier, self.owner(client))).fetchone()
        if not row:
            raise StateError("Run not found in this browser.")
        data = dict(row)
        stored_result=data.pop("hunt_result")
        progress=data.pop("progress",None)
        result=json.loads(progress) if data["status"]=="running" and progress else json.loads(stored_result) if stored_result else {}
        data["listing_count"]=len(result.get("listings",[]))
        data["events"] = json.loads(data["events"])
        return data

    def queued(self) -> list[str]:
        with self._db() as db:
            return [r[0] for r in db.execute("SELECT id FROM runs WHERE status='queued' ORDER BY created")]

    def job_hunt(self, run: str) -> dict:
        """Internal worker access; never expose this unscoped method as an endpoint."""
        with self._db() as db:
            row=db.execute("SELECT h.* FROM hunts h JOIN runs r ON h.id=r.hunt WHERE r.id=?",(run,)).fetchone()
        if not row:
            raise StateError("Queued hunt disappeared.")
        data=dict(row)
        data["preferences"]=json.loads(data["preferences"])
        data["result"]=json.loads(data["result"]) if data["result"] else None
        return data

    def event(self, run: str, event: RunEvent):
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT events FROM runs WHERE id=?", (run,)).fetchone()
            events = json.loads(row[0]) if row else []
            events.append(event.model_dump())
            db.execute("UPDATE runs SET events=?,updated=? WHERE id=?", (json.dumps(events[-180:]),time.time(),run))

    def progress(self,run: str,result: EngineResult):
        """Publish retrieved leads while reading continues; never accept a plan."""
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT hunt FROM runs WHERE id=? AND status='running'",(run,)).fetchone()
            if row:
                db.execute("UPDATE runs SET progress=?,updated=? WHERE id=?",(result.model_dump_json(),time.time(),run))

    def finish(self, run: str, result: EngineResult | None, error: str | None = None):
        now = time.time()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT hunt FROM runs WHERE id=?", (run,)).fetchone()
            if result and row:
                previous = db.execute("SELECT result FROM hunts WHERE id=?", (row[0],)).fetchone()[0]
                old = json.loads(previous) if previous else {}
                prior_ids = {v["id"] for v in old.get("listings", [])}
                for listing in result.listings:
                    listing.is_new = listing.id not in prior_ids
                db.execute("UPDATE hunts SET result=?,next_refresh=? WHERE id=?", (result.model_dump_json(),now+86400,row[0]))
            db.execute("UPDATE runs SET status=?,error=?,updated=? WHERE id=?",
                       ("failed" if error else "partial" if result and result.partial else "completed",error,now,run))
            if error and row:
                db.execute("UPDATE hunts SET next_refresh=? WHERE id=?",(now+2*3600,row[0]))

    def flags(self, hunt: str, listing: str, client: str, *, saved: bool, hidden: bool):
        record = self.hunt(hunt, client)
        if not record["result"] or not any(v["id"] == listing for v in record["result"]["listings"]):
            raise StateError("Listing not found in this hunt.")
        with self._db() as db:
            db.execute("INSERT INTO flags VALUES(?,?,?,?) ON CONFLICT(hunt,listing) DO UPDATE SET saved=excluded.saved,hidden=excluded.hidden",
                       (hunt,listing,int(saved),int(hidden)))

    def cached(self, key: str):
        with self._db() as db:
            row = db.execute("SELECT value FROM cache WHERE key=? AND expires>?", (key,time.time())).fetchone()
        return json.loads(row[0]) if row else None

    def cache(self, key: str, value, seconds: int):
        with self._db() as db:
            db.execute("INSERT INTO cache VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,expires=excluded.expires",
                       (key,json.dumps(value),time.time()+seconds))

    def cache_observed_at(self,key: str,ttl: int) -> str|None:
        with self._db() as db:
            row=db.execute("SELECT expires FROM cache WHERE key=? AND expires>?",(key,time.time())).fetchone()
        return datetime.fromtimestamp(row[0]-ttl,timezone.utc).isoformat() if row else None

    def acquire(self,key: str,value,seconds: int) -> bool:
        """Atomically acquire an in-flight goal key; expired entries may be replaced."""
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM cache WHERE key=? AND expires<=?",(key,time.time()))
            return db.execute("INSERT OR IGNORE INTO cache VALUES(?,?,?)",(key,json.dumps(value),time.time()+seconds)).rowcount==1

    def delete_cache(self,key: str):
        with self._db() as db:
            db.execute("DELETE FROM cache WHERE key=?",(key,))

    def reserve(self, key: str, amount: float, cap: float, *, window: int = 86400) -> bool:
        if amount < 0 or cap < 0:
            return False
        bucket = f"{key}:{int(time.time())//window}"
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT amount FROM usage WHERE key=?", (bucket,)).fetchone()
            total = row[0] if row else 0
            if total + amount > cap:
                return False
            db.execute("INSERT INTO usage VALUES(?,?) ON CONFLICT(key) DO UPDATE SET amount=excluded.amount", (bucket,total+amount))
        return True

    def recover_interrupted(self):
        """Only call on explicit single-server startup, never during an active worker."""
        with self._db() as db:
            db.execute("UPDATE runs SET status='interrupted',error='Server restarted; no automatic provider resubmission.',updated=? WHERE status IN ('queued','running')", (time.time(),))

    def schedule_due(self) -> list[str]:
        """Opt-in scheduler capability. Caller must separately authorize recurring work.

        User hunts: 24 hours, viewed within three days; failed runs retry in two hours.
        No public showcases are automatically published or seeded by this method.
        """
        now=time.time()
        identifiers=[]
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            room=10-db.execute("SELECT count(*) FROM runs WHERE status IN ('queued','running')").fetchone()[0]
            rows=db.execute("SELECT id FROM hunts h WHERE next_refresh<=? AND viewed>=? AND NOT EXISTS(SELECT 1 FROM runs r WHERE r.hunt=h.id AND r.status IN ('queued','running')) ORDER BY next_refresh LIMIT ?",
                            (now,now-3*86400,max(0,room))).fetchall()
            for row in rows:
                identifier=uuid.uuid4().hex
                db.execute("INSERT INTO runs(id,hunt,status,created,updated) VALUES(?,?,'queued',?,?)",(identifier,row[0],now,now))
                db.execute("UPDATE hunts SET next_refresh=? WHERE id=?",(now+86400,row[0]))
                identifiers.append(identifier)
        return identifiers
