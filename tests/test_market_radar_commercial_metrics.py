from datetime import datetime,timezone,timedelta
from app.market_radar.commercial_metrics import nexscope_shopee_rows

NOW=datetime(2026,10,28,16,tzinfo=timezone.utc)

def test_provider_fields_preserve_type_and_period():
 rows=nexscope_shopee_rows({"products":[{"pid":"123","title":"Produto real","sold":80,"estimateSold":99,
     "historicalSold":300,"viewCount":1000,"payment":4500,"price":30}]},observed_at=NOW)
 index={r["metric_name"]:r for r in rows}
 assert index["sold_30d"]["metric_kind"]=="ACTUAL_PROVIDER"
 assert index["estimated_sold_30d"]["metric_kind"]=="ESTIMATED_PROVIDER"
 assert index["historical_sold"]["window_start"] is None
 assert index["sold_30d"]["window_start"]==NOW-timedelta(days=30)
 assert index["views_total"]["window_start"] is None

def test_empty_or_invalid_values_rejected_without_fake_counts():
 rows=nexscope_shopee_rows({"products":[{"pid":"8","title":"Produto","sold":None,
     "historicalSold":-8,"viewCount":True,"estimateSold":float("nan")}]},observed_at=NOW)
 assert rows==[]

def test_missing_identity_never_creates_commercial_product():
 assert nexscope_shopee_rows({"products":[{"pid":"example-id","sold":10}]},observed_at=NOW)==[]
