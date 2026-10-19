from pathlib import Path
from typing import Dict, List, Union
import requests

def publish_github_release(
    repo: str,
    token: str,
    tag: str,
    asset_paths: Union[List[Path], Path],
    title: str,
    body: str
) -> Union[Dict[str, str], str]:
    """
    Creates or updates a GitHub Release for the given tag and uploads one or multiple assets.
    Returns mapping of asset.name -> download_url (or single download URL string if a single Path was passed).
    """
    single_mode = isinstance(asset_paths, Path)
    paths: List[Path] = [asset_paths] if single_mode else list(asset_paths)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    api_base = f"https://api.github.com/repos/{repo}"
    rel_res = requests.get(f"{api_base}/releases/tags/{tag}", headers=headers, timeout=30)

    target_names = {p.name for p in paths}

    if rel_res.status_code == 200:
        release_data = rel_res.json()
        release_id = release_data["id"]
        # Delete existing assets with same name if they exist
        assets_res = requests.get(f"{api_base}/releases/{release_id}/assets", headers=headers, timeout=30)
        if assets_res.status_code == 200:
            for asset in assets_res.json():
                if asset["name"] in target_names:
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

    uploaded_urls: Dict[str, str] = {}
    for p in paths:
        content_type = "application/zip" if p.suffix == ".zip" else "application/ld+json" if p.suffix == ".json" else "application/octet-stream"
        with open(p, "rb") as f:
            upload_res = requests.post(
                upload_url,
                headers={**headers, "Content-Type": content_type},
                params={"name": p.name},
                data=f,
                timeout=120
            )
        upload_res.raise_for_status()
        uploaded_urls[p.name] = upload_res.json().get(
            "browser_download_url",
            f"https://github.com/{repo}/releases/download/{tag}/{p.name}"
        )

    if single_mode:
        return uploaded_urls.get(paths[0].name, "")
    return uploaded_urls

