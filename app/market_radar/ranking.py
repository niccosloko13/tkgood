from __future__ import annotations

from .models import Movement


def movement(current_rank: int | None, previous_rank: int | None) -> tuple[Movement, int | None]:
    if previous_rank is None and current_rank is not None:
        return Movement.NEW_ENTRY, None
    if current_rank is None or previous_rank is None:
        return Movement.UNKNOWN, None
    change = previous_rank - current_rank
    if change > 0: return Movement.UP, change
    if change < 0: return Movement.DOWN, change
    return Movement.STABLE, 0


def top_products(con, *, marketplace: str, category: str | None = None, limit: int = 20) -> list[dict]:
    limit = min(max(1, limit), 20)
    where = ["p.marketplace=?"]; params: list[object] = [marketplace]
    if category: where.append("p.category=?"); params.append(category)
    rows = con.execute(f"""
      SELECT p.*,s.id AS snapshot_id,s.* FROM market_products p JOIN market_snapshots s ON s.product_id=p.id
      WHERE {' AND '.join(where)} AND s.id=(SELECT s2.id FROM market_snapshots s2 WHERE s2.product_id=p.id ORDER BY s2.observed_at DESC,s2.id DESC LIMIT 1)
      ORDER BY CASE WHEN s.rank IS NULL THEN 1 ELSE 0 END,s.rank ASC,s.observed_at DESC LIMIT ?
    """, [*params, limit]).fetchall()
    result = []
    for row in rows:
        previous = con.execute("SELECT rank FROM market_snapshots WHERE product_id=? AND id<>? ORDER BY observed_at DESC,id DESC LIMIT 1", (row["product_id"], row["snapshot_id"])).fetchone()
        direction, change = movement(row["rank"], previous["rank"] if previous else None)
        first = con.execute("SELECT min(observed_at) FROM market_snapshots WHERE product_id=?", (row["product_id"],)).fetchone()[0]
        result.append({"external_id": row["external_id"], "title": row["title"], "category": row["category"], "current_rank": row["rank"], "previous_rank": previous["rank"] if previous else None, "rank_change": change, "movement": direction.value, "first_seen_at": first, "last_seen_at": row["observed_at"], "source_type": row["source_type"], "source_window": row["source_window"]})
    return result
