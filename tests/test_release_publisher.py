from pathlib import Path
from unittest.mock import MagicMock, patch
from action.release_publisher import publish_github_release

def test_publish_github_release_new(tmp_path: Path):
    asset_file = tmp_path / "BPNS_bluecloud-ENA.zip"
    asset_file.write_bytes(b"PK00mockzip")

    mock_resp_get = MagicMock()
    mock_resp_get.status_code = 404

    mock_resp_post = MagicMock()
    mock_resp_post.status_code = 201
    mock_resp_post.json.return_value = {
        "id": 12345,
        "upload_url": "https://uploads.github.com/repos/emo-bon/test/releases/12345/assets{?name,label}"
    }

    mock_resp_upload = MagicMock()
    mock_resp_upload.status_code = 201
    mock_resp_upload.json.return_value = {
        "browser_download_url": "https://github.com/emo-bon/test/releases/download/bluecloud-ENA-latest/BPNS_bluecloud-ENA.zip"
    }

    with patch("requests.get", return_value=mock_resp_get), \
         patch("requests.post", side_effect=[mock_resp_post, mock_resp_upload]):
        download_url = publish_github_release(
            repo="emo-bon/test",
            token="ghp_mocktoken",
            tag="bluecloud-ENA-latest",
            asset_path=asset_file,
            title="Release Title",
            body="Release Body"
        )

    assert "releases/download/bluecloud-ENA-latest/BPNS_bluecloud-ENA.zip" in download_url
