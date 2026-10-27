from app import gold_set
from test_detection_benchmark import prepare, review
from test_product_detection import library


def test_export_download_contains_all_saved_reviews_without_mutation(library, monkeypatch):
    import csv
    import io
    import json
    import zipfile
    from app import gold_set_api
    prepare(library)
    with library.connect() as con:
        gold_set.save_review(con, 3, review(raw_product_name='=unsafe',fn_reason='visual_only',review_method='video_opened'))
        gold_set.benchmark(con)
        before = list(con.iterdump())
    monkeypatch.setattr(gold_set_api, 'connect', library.connect)
    response = gold_set_api.export_reviews()
    assert response.media_type == 'application/zip'
    assert 'attachment' in response.headers['content-disposition']
    with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
        gold = json.loads(archive.read('gold_set_reviews.json'))
        assert len(gold['reviews']) == 1 and gold['progress']['pending'] == 4
        assert gold['reviews'][0]['review_method'] == 'video_opened'
        assert gold['review_history']
        rows = list(csv.DictReader(io.StringIO(archive.read('gold_set_reviews.csv').decode('utf-8-sig'))))
        assert rows[0]['raw_product_name'] == "'=unsafe"
        assert json.loads(archive.read('benchmark_latest.json'))['fn'] == 1
        assert len(json.loads(archive.read('benchmark_history.json'))) == 1
    with library.connect() as con:
        assert list(con.iterdump()) == before


def test_categories_match_strict_benchmark_and_preserve_pending_names(library):
    prepare(library)
    with library.connect() as con:
        cid = gold_set.detail(con, 1)['candidates'][0]['id']
        gold_set.save_review(con, 1, review())
        assert gold_set.detail(con, 1)['benchmark_category'] == 'pending_name_match'
        gold_set.save_review(con, 1, review(candidate_reviews=[{'candidate_id': cid, 'name_match': 'wrong'}]))
        gold_set.save_review(con, 2, review('no'))
        gold_set.save_review(con, 3, review())
        gold_set.save_review(con, 4, review('no'))
        gold_set.save_review(con, 5, review('unclear'))
        listing = gold_set.listing(con)
        report = gold_set.benchmark(con, persist=False)
        assert listing['filter_counts'] == {'fn': 2, 'fp': 1, 'tn': 1, 'unclear': 1}
        for category in ('tp', 'fp', 'fn', 'tn'):
            assert listing['filter_counts'].get(category, 0) == report[category]


def test_human_metadata_nullable_explicit_idempotent_and_legacy_preserved(library):
    prepare(library)
    with library.connect() as con:
        before = gold_set.benchmark(con, persist=False)
        assert all(v['review_method'] is None for v in gold_set.listing(con)['items'])
        for reason in ('visual_only', 'visual_helped', 'product_only_in_comments', 'unknown_vocabulary',
                       'generic_caption', 'missing_enrichment', 'unsupported_language', 'normalization_failure', 'other'):
            payload = review(fn_reason=reason, review_method='lens_assisted')
            result = gold_set.save_review(con, 3, payload)
            assert result['fn_reason'] == reason and result['review_method'] == 'lens_assisted'
            count = con.execute('SELECT count(*) FROM gold_review_history').fetchone()[0]
            gold_set.save_review(con, 3, payload)
            assert con.execute('SELECT count(*) FROM gold_review_history').fetchone()[0] == count
        gold_set.save_review(con, 3, review(fn_reason='generic_phrase'))
        assert gold_set.detail(con, 3)['review_method'] == 'lens_assisted'
        gold_set.migrate(con)
        assert gold_set.detail(con, 3)['fn_reason'] == 'generic_phrase'
        assert gold_set.benchmark(con, persist=False)['candidate_audit'] == before['candidate_audit']
