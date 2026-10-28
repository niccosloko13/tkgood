from datetime import datetime,timezone,timedelta
from app.market_radar.observation_windows import build_window
NOW=datetime(2026,10,28,15,tzinfo=timezone.utc)
def sample(rank,age,key="MLB123"):
 return {"marketplace":"MERCADO_LIVRE","external_id":key,"source_category":"MLB100","rank":rank,"title":"Produto","price":22,"observed_at":NOW-timedelta(hours=age)}
def test_rising_requires_separate_observations():
 data=build_window([sample(10,25),sample(3,2)],48,now=NOW,sort="rising")
 assert data["products"][0]["rank_movement"]==7
 assert data["products"][0]["observation_count"]==2
 assert data["products"][0]["rank_movement_label"]=="UP"
 assert data["products"][0]["units_sold_in_window"] is None
def test_one_observation_does_not_invent_growth():
 data=build_window([sample(2,3)],48,now=NOW,sort="rising")
 assert data["products"][0]["rank_movement"] is None
 assert data["products"][0]["rank_movement_label"]=="INSUFFICIENT_HISTORY"
def test_old_and_different_categories_not_mix():
 old=sample(8,49)
 other=sample(10,20);other["source_category"]="MLB200"
 data=build_window([old,sample(3,2),other],48,now=NOW)
 assert len(data["products"])==2
 assert all(item["units_sold_in_window"] is None for item in data["products"])
