from app.policy import ReadOnlyPolicy
import pytest


@pytest.mark.parametrize('action', [
    'like', 'dislike', 'comment', 'reply', 'follow', 'unfollow', 'share',
    'repost', 'save', 'favorite', 'dm', 'message', 'publish', 'post',
    'edit_profile', 'edit_account', 'edit_settings', 'edit_account/settings',
])
def test_permanently_forbidden_actions(action):
    assert not ReadOnlyPolicy().check(action).allowed

def test_search_allowed():
    assert ReadOnlyPolicy().check("search", "home gadgets").allowed

def test_like_denied():
    assert not ReadOnlyPolicy().check("like", "video").allowed

def test_comment_denied():
    assert not ReadOnlyPolicy().check("comment", "video").allowed

def test_follow_denied():
    assert not ReadOnlyPolicy().check("follow", "@creator").allowed

def test_forbidden_target_denied():
    assert not ReadOnlyPolicy().check("open_result", "Follow").allowed

def test_unknown_action_denied():
    assert not ReadOnlyPolicy().check("click_anything", "button").allowed
