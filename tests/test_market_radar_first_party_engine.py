from datetime import datetime, timezone, timedelta
import pytest
from app.market_radar.first_party_engine import normalize_observations
from app.market_radar.commercial_metrics import cumulative_growth

def product(at, counter=120):
 return {"marketplace":"SHOPEE","product_id":"123","title":"Copo","product_url":"https://shopee.com.br/abc",
         "observed_at":at.isoformat(),"metric_name":"historical_sold","metric_value":counter}

def test_free_public_counter_is_observation_not_30_day_sales():
 now=datetime.now(timezone.utc)-timedelta(hours=1)
 row=normalize_observations([product(now)],source_id="public_listing",origin="PUBLIC_LISTING")[0]
 assert row["metric_name"]=="historical_sold"
 assert row["metric_kind"]=="CUMULATIVE_OBSERVED"
 assert row["window_start"] if "window_start" in row else True
 assert "origin" in row["evidence"]

def test_denies_fake_count_and_external_link():
 now=datetime.now(timezone.utc)
 for bad in [-1,"NaN","20k"]:
  with pytest.raises(ValueError):
   normalize_observations([product(now,bad)],source_id="listing",origin="PUBLIC_LISTING")
 bad=product(now);bad["product_url"]="https://evil.example/abc"
 with pytest.raises(ValueError):
  normalize_observations([bad],source_id="listing",origin="PUBLIC_LISTING")

def test_growth_only_when_counter_snapshots_span_window():
 now=datetime.now(timezone.utc)
 items=[{"marketplace":"SHOPEE","product_id":"1","metric_name":"historical_sold","provider":"BABI_PUBLIC_TEST",
         "metric_value":100,"observed_at":now-timedelta(hours=49)},
        {"marketplace":"SHOPEE","product_id":"1","metric_name":"historical_sold","provider":"BABI_PUBLIC_TEST",
         "metric_value":142,"observed_at":now-timedelta(hours=1)}]
 result=cumulative_growth(items,hours=48,now=now)
 assert len(result)==1
 assert result[0]["growth"]==42
 assert result[0]["measurement"]=="COUNTER_DELTA_OBSERVED"
