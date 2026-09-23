import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from downloader import stalk_tiktok_user, get_tiktok_user_posts, get_tiktok_user_reposts


def test_stalk_tiktok_user_success():
    mock_stdout = json.dumps({
        "status": "success",
        "result": {
            "user": {
                "username": "tiktok",
                "nickname": "TikTok",
                "verified": True,
                "privateAccount": False,
                "signature": "Make Your Day",
                "avatarLarger": "https://example.com/avatar.jpg"
            },
            "stats": {
                "followerCount": 80000000,
                "followingCount": 500,
                "heartCount": 1000000000,
                "videoCount": 1500
            }
        }
    })

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_stdout, stderr="")
        res = stalk_tiktok_user("tiktok")
        assert res["user"]["username"] == "tiktok"
        assert res["stats"]["followerCount"] == 80000000


def test_stalk_tiktok_user_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="User not found")
        with pytest.raises(RuntimeError) as exc_info:
            stalk_tiktok_user("non_existing_user_99999")
        assert "User not found" in str(exc_info.value)


def test_get_tiktok_user_posts_success():
    mock_stdout = json.dumps({
        "status": "success",
        "result": [
            {
                "id": "7123456789",
                "desc": "Check out this video!",
                "stats": {"likeCount": 15000, "playCount": 200000, "commentCount": 300}
            }
        ]
    })

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_stdout, stderr="")
        posts = get_tiktok_user_posts("tiktok", limit=5)
        assert len(posts) == 1
        assert posts[0]["id"] == "7123456789"
        assert posts[0]["stats"]["likeCount"] == 15000


def test_get_tiktok_user_reposts_success():
    mock_stdout = json.dumps({
        "status": "success",
        "result": [
            {
                "id": "7987654321",
                "desc": "Great repost!",
                "author": {"username": "original_creator"},
                "stats": {"likeCount": 5000, "shareCount": 120}
            }
        ]
    })

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_stdout, stderr="")
        reposts = get_tiktok_user_reposts("tiktok", limit=5)
        assert len(reposts) == 1
        assert reposts[0]["id"] == "7987654321"
        assert reposts[0]["author"]["username"] == "original_creator"
