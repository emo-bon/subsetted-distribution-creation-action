from pathlib import Path
from unittest.mock import MagicMock, patch
from action.release_publisher import publish_github_release

def test_publish_github_release_single(tmp_path: Path):
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
         patch("requests.post", side_effect=[mock_resp_post, mock_resp_upload]) as mock_post:
        download_url = publish_github_release(
            repo="emo-bon/test",
            token="ghp_mocktoken",
            tag="bluecloud-ENA-latest",
            asset_paths=asset_file,
            title="Release Title",
            body="Release Body"
        )

    assert "releases/download/bluecloud-ENA-latest/BPNS_bluecloud-ENA.zip" in download_url
    # Verify content-type header
    assert mock_post.call_args_list[1][1]["headers"]["Content-Type"] == "application/zip"


def test_publish_github_release_multiple(tmp_path: Path):
    zip_file = tmp_path / "BPNS_bluecloud-ENA.zip"
    zip_file.write_bytes(b"PK00mockzip")
    meta_file = tmp_path / "ro-crate-metadata.json"
    meta_file.write_text('{"@context": "https://w3id.org/ro/crate/1.2/context"}')

    mock_resp_get = MagicMock()
    mock_resp_get.status_code = 404

    mock_resp_post = MagicMock()
    mock_resp_post.status_code = 201
    mock_resp_post.json.return_value = {
        "id": 12345,
        "upload_url": "https://uploads.github.com/repos/emo-bon/test/releases/12345/assets{?name,label}"
    }

    mock_resp_upload1 = MagicMock()
    mock_resp_upload1.status_code = 201
    mock_resp_upload1.json.return_value = {
        "browser_download_url": "https://github.com/emo-bon/test/releases/download/bluecloud-ENA-latest/BPNS_bluecloud-ENA.zip"
    }

    mock_resp_upload2 = MagicMock()
    mock_resp_upload2.status_code = 201
    mock_resp_upload2.json.return_value = {
        "browser_download_url": "https://github.com/emo-bon/test/releases/download/bluecloud-ENA-latest/ro-crate-metadata.json"
    }

    with patch("requests.get", return_value=mock_resp_get), \
         patch("requests.post", side_effect=[mock_resp_post, mock_resp_upload1, mock_resp_upload2]) as mock_post:
        urls = publish_github_release(
            repo="emo-bon/test",
            token="ghp_mocktoken",
            tag="bluecloud-ENA-latest",
            asset_paths=[zip_file, meta_file],
            title="Release Title",
            body="Release Body"
        )

    assert isinstance(urls, dict)
    assert urls["BPNS_bluecloud-ENA.zip"] == "https://github.com/emo-bon/test/releases/download/bluecloud-ENA-latest/BPNS_bluecloud-ENA.zip"
    assert urls["ro-crate-metadata.json"] == "https://github.com/emo-bon/test/releases/download/bluecloud-ENA-latest/ro-crate-metadata.json"
    # Check mime types used
    assert mock_post.call_args_list[1][1]["headers"]["Content-Type"] == "application/zip"
    assert mock_post.call_args_list[2][1]["headers"]["Content-Type"] == "application/ld+json"

