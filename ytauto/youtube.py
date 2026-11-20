"""Optional YouTube upload (video + thumbnail + captions) via the YouTube Data API v3.

One-time setup (see README "YouTube upload"):
  1. Create an OAuth client (type "Desktop app") in Google Cloud Console and enable
     "YouTube Data API v3". Download the client JSON.
  2. On your own computer run:  python -m ytauto youtube-auth --client-secrets client.json
  3. Save the printed YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN as GitHub secrets.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .utils import YtautoError, log, warn

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]


def authorize(client_secrets: str) -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline", open_browser=True)
    data = json.loads(Path(client_secrets).read_text())
    info = data.get("installed") or data.get("web") or {}
    print("\nAdd these as GitHub repository secrets (Settings → Secrets and variables → Actions):\n")
    print(f"YT_CLIENT_ID={info.get('client_id')}")
    print(f"YT_CLIENT_SECRET={info.get('client_secret')}")
    print(f"YT_REFRESH_TOKEN={creds.refresh_token}")


def _service():
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise YtautoError("pip install google-api-python-client google-auth-oauthlib") from exc
    need = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"]
    missing = [k for k in need if not os.environ.get(k)]
    if missing:
        raise YtautoError(f"Missing environment variables for YouTube upload: {', '.join(missing)}")
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(build_dir: Path, privacy: str | None = None) -> str:
    from googleapiclient.http import MediaFileUpload

    manifest = json.loads((build_dir / "manifest.json").read_text())
    yt_cfg = manifest.get("youtube") or {}
    yt = _service()
    status = {
        "privacyStatus": privacy or yt_cfg.get("privacy", "private"),
        "selfDeclaredMadeForKids": bool(yt_cfg.get("made_for_kids", False)),
    }
    if yt_cfg.get("publish_at"):
        status["privacyStatus"] = "private"
        status["publishAt"] = yt_cfg["publish_at"]
    if "synthetic_media" in yt_cfg:
        status["containsSyntheticMedia"] = bool(yt_cfg["synthetic_media"])
    body = {
        "snippet": {
            "title": manifest["title"][:100],
            "description": manifest["description"][:5000],
            "tags": manifest.get("tags", [])[:30],
            "categoryId": str(yt_cfg.get("category_id", "22")),
            "defaultLanguage": yt_cfg.get("language", "en"),
            "defaultAudioLanguage": yt_cfg.get("language", "en"),
        },
        "status": status,
    }
    video = build_dir / manifest["video"]
    log(f"Uploading {video.name} ({video.stat().st_size / 1e6:.0f} MB) as {status['privacyStatus']} …")
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(video), chunksize=16 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        st, resp = req.next_chunk()
        if st:
            log(f"   upload {int(st.progress() * 100)}%")
    vid = resp["id"]
    log(f"Uploaded: https://youtu.be/{vid}")

    if manifest.get("thumbnail"):
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(build_dir / manifest["thumbnail"]))).execute()
            log("   thumbnail set")
        except Exception as exc:  # noqa: BLE001 — custom thumbnails need a verified channel
            warn(f"thumbnail not set (verify your channel to allow custom thumbnails): {exc}")
    if manifest.get("captions") and yt_cfg.get("upload_captions", True):
        try:
            yt.captions().insert(
                part="snippet",
                body={"snippet": {"videoId": vid, "language": yt_cfg.get("language", "en"), "name": "English"}},
                media_body=MediaFileUpload(str(build_dir / manifest["captions"]), mimetype="application/octet-stream"),
            ).execute()
            log("   captions uploaded")
        except Exception as exc:  # noqa: BLE001
            warn(f"captions not uploaded: {exc}")
    if yt_cfg.get("playlist_id"):
        try:
            yt.playlistItems().insert(part="snippet", body={"snippet": {
                "playlistId": yt_cfg["playlist_id"], "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        except Exception as exc:  # noqa: BLE001
            warn(f"could not add to playlist: {exc}")
    (build_dir / "youtube.json").write_text(json.dumps({"id": vid, "url": f"https://youtu.be/{vid}"}, indent=2))
    return vid
