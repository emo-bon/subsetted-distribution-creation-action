from pathlib import Path
import requests

def publish_github_release(
    repo: str,
    token: str,
    tag: str,
    asset_path: Path,
    title: str,
    body: str
) -> str:
    """
    Creates or updates a GitHub Release for the given tag and uploads asset_path.
    Returns the asset download URL.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    api_base = f"https://api.github.com/repos/{repo}"
    rel_res = requests.get(f"{api_base}/releases/tags/{tag}", headers=headers, timeout=30)

    if rel_res.status_code == 200:
        release_data = rel_res.json()
        release_id = release_data["id"]
        # Delete existing asset with same name if exists
        assets_res = requests.get(f"{api_base}/releases/{release_id}/assets", headers=headers, timeout=30)
        if assets_res.status_code == 200:
            for asset in assets_res.json():
                if asset["name"] == asset_path.name:
                    requests.delete(f"{api_base}/releases/assets/{asset['id']}", headers=headers, timeout=30)

        upload_url = release_data["upload_url"].split("{")[0]
    else:
        create_res = requests.post(
            f"{api_base}/releases",
            headers=headers,
            json={"tag_name": tag, "name": title, "body": body, "draft": False, "prerelease": False},
            timeout=30
        )
        create_res.raise_for_status()
        release_data = create_res.json()
        upload_url = release_data["upload_url"].split("{")[0]

    # Upload asset
    with open(asset_path, "rb") as f:
        upload_res = requests.post(
            upload_url,
            headers={**headers, "Content-Type": "application/zip"},
            params={"name": asset_path.name},
            data=f,
            timeout=120
        )
    upload_res.raise_for_status()
    return upload_res.json().get(
        "browser_download_url",
        f"https://github.com/{repo}/releases/download/{tag}/{asset_path.name}"
    )
