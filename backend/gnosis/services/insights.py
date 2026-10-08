"""The product's numbers for admins: the same arithmetic as before
(`coach.metrics.summarize`), over our tables. Totals only."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.engine import Connection

from coach import metrics
from gnosis.data import schema as t


def summary(conn: Connection, since: date, today: date) -> dict:
    users = [{"user_id": r["id"], "created_at": r["created_at"].isoformat()}
             for r in conn.execute(select(t.users.c.id, t.users.c.created_at)
                                   .where(t.users.c.status != "deleted")).mappings()]
    events = [{"user_id": r["user_id"], "day": r["day"], "event": r["event"], "count": r["count"]}
              for table in (t.usage_events, t.learning_signals)
              for r in conn.execute(select(table).where(table.c.day >= since)).mappings()]
    return metrics.summarize(users, events, since, today)
