from datetime import datetime, timezone, timedelta
from app.market_radar.observation_windows import build_window

NOW=datetime(2026,10,28,15,tzinfo=timezone.utc)
def row(key, rank, age, price=None):
    return {"marketplace":"MERCADO_LIVRE","external_id":key,"source_category":"MLB1",
        "title":key,"rank":rank,"price":price,"observed_at":NOW-timedelta(hours=age)}

def test_window_48h_excludes_stale_and_never_invents_sales():
    data=build_window([row("A",2,3),row("B",1,50),row("C",3,47)],48,now=NOW)
    assert [p["external_id"] for p in data["products"]]==["A","C"]
    assert all(p["units_sold_in_window"] is None and p["visits_in_window"] is None for p in data["products"])
    assert not data["complete_window"]

def test_deduplicates_latest_per_category_and_period():
    data=build_window([row("A",5,10),row("A",2,2)],168,now=NOW)
    assert data["observation_count"]==1
    assert data["products"][0]["rank"]==2

def test_top_filter_and_price_sort():
    data=build_window([row("A",4,1,100),row("B",10,2,20),row("C",2,4,80)],48,sort="price_low",min_rank=5,now=NOW)
    assert [p["external_id"] for p in data["products"]]==["C","A"]
