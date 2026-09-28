import json
from unittest.mock import MagicMock, patch

import pytest

from downloader import stalk_tiktok_user


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
