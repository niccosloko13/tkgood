import json
from pathlib import Path

import pytest

from app.market_radar.offline_import import OfflineImportError, import_offline_file


def test_shopee_json_deduplicates_and_never_infers_sales(tmp_path: Path):
    path = tmp_path / "products.json"
    rows = [{"id": "123", "name": "Cabo USB", "price": "19.50", "currency": "BRL",
             "url": "https://shopee.com.br/product/5/123", "sold": 400},
            {"id": "123", "name": "Cabo USB duplicado"},
            {"id": "124", "name": "Outro produto", "price": "30"}]
    path.write_text(json.dumps(rows), encoding="utf-8")
    result = import_offline_file(path, marketplace="shopee", source_category="cabos")
    assert len(result) == 2
    assert result[0].price == 19.5
    assert result[0].rank is None
    assert result[0].sales_count is None
    assert result[0].views is None
    assert result[0].product.source_category == "cabos"
    assert result[0].evidence["import_origin"] == "IMPORTED_FILE"


def test_jsonl_aliexpress_rejects_bad_product_url(tmp_path: Path):
    path = tmp_path / "a.jsonl"
    path.write_text(json.dumps({"id": "X1", "name": "Mini ventilador",
                               "url": "https://evil.example/product", "price": 7}) + "\n")
    result = import_offline_file(path, marketplace="aliexpress", fixture=True)
    assert len(result) == 1
    assert result[0].product.product_url is None
    assert result[0].evidence["import_origin"] == "FIXTURE"


def test_csv_parses_local_input(tmp_path: Path):
    path = tmp_path / "a.csv"
    path.write_text("id,title,price,currency\nABC,Produto,12.75,BRL\n", encoding="utf-8")
    assert len(import_offline_file(path, marketplace="shopee")) == 1


def test_local_html_jsonld_not_executed(tmp_path: Path):
    path = tmp_path / "item.html"
    path.write_text('<script>throw new Error("not executed")</script>'
                    '<script type="application/ld+json">'
                    '{"@type":"Product","name":"Teste","sku":"abc","offers":{"price":"25","priceCurrency":"BRL"}}'
                    '</script>', encoding="utf-8")
    result = import_offline_file(path, marketplace="shopee")
    assert result[0].price == 25.0


def test_invalid_and_oversize_rejected(tmp_path: Path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{oops", encoding="utf-8")
    with pytest.raises(OfflineImportError):
        import_offline_file(bad, marketplace="shopee")
    huge = tmp_path / "big.json"
    huge.write_bytes(b" " * (2_000_001))
    with pytest.raises(OfflineImportError):
        import_offline_file(huge, marketplace="aliexpress")


def test_category_does_not_leak_between_calls(tmp_path: Path):
    path = tmp_path / "products.json"
    path.write_text('[{"id":"42","title":"A"}]')
    a = import_offline_file(path, marketplace="shopee", source_category="casa")
    b = import_offline_file(path, marketplace="shopee", source_category="beleza")
    assert a[0].product.source_category == "casa"
    assert b[0].product.source_category == "beleza"
