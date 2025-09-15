import os
import secrets
import subprocess
import requests
import time
import logging

from celery import shared_task
from django.conf import settings

from .models import Video

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def encrypt_video(self, video_id: int):
    """Package and encrypt a video via docker packager.

    Steps:
    - Ensure output dir media/encrypted/<id>
    - Generate 16-byte kid/key if missing; store on model
    - Run docker packager mounting input and output
    - On success, set status=READY and set encrypted_path
    - On failure, mark status=failed
    """
    logger.info(f"Starting encrypt_video task for video_id: {video_id}")
    
    try:
        video = Video.objects.get(pk=video_id)
        logger.info(f"Found video: {video.title} (ID: {video.id})")
    except Video.DoesNotExist:
        logger.error(f"Video with ID {video_id} does not exist")
        return

    # Resolve paths relative to shared Docker volume 'media_data'
    # In Django/Celery containers the volume is mounted at /app/media
    # In the packager container the same volume is mounted at /work
    input_rel_path = video.file.name  # e.g. 'uploads/<file>'
    input_path_in_packager = f"/work/{input_rel_path}"
    out_dir_in_packager = f"/work/encrypted/{video.id}"
    # Also ensure the output dir exists in our container (harmless if not visible to packager)
    media_root = settings.MEDIA_ROOT
    os.makedirs(os.path.join(media_root, "encrypted", str(video.id)), exist_ok=True)

    # Ensure 16-byte KID/KEY in hex (32 hex chars)
    updated_keys = False
    if not video.kid_hex or len(video.kid_hex) != 32:
        video.kid_hex = secrets.token_hex(16)
        updated_keys = True
    if not video.key_hex or len(video.key_hex) != 32:
        video.key_hex = secrets.token_hex(16)
        updated_keys = True
    if updated_keys:
        video.save(update_fields=["kid_hex", "key_hex", "updated_at"])

    # Call packager HTTP API instead of docker CLI
    packager_url = os.getenv("PACKAGER_SERVICE_URL", "http://packager:8080").rstrip("/") + "/pack"

    payload = {
        "input_rel_path": input_rel_path,
        "output_rel_dir": f"encrypted/{video.id}",
        "kid_hex": video.kid_hex,
        "key_hex": video.key_hex,
    }

    # Retry with backoff to wait for packager readiness/DNS
    last_err = None
    for attempt in range(8):
        try:
            resp = requests.post(packager_url, json=payload, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                encrypted_rel_path = data.get("mpd", f"encrypted/{video.id}/stream.mpd")
                logger.info(f"Encryption successful via API, setting encrypted_path: {encrypted_rel_path}")
                Video.objects.filter(pk=video.pk).update(
                    status="READY",
                    encrypted_path=encrypted_rel_path,
                )
                return
            else:
                last_err = f"HTTP {resp.status_code}: {resp.text}"
        except Exception as e:
            last_err = str(e)

        sleep_sec = min(5 * (attempt + 1), 30)
        logger.info(f"Packager not ready, retrying in {sleep_sec}s (attempt {attempt+1}/8): {last_err}")
        time.sleep(sleep_sec)

    logger.error(f"Packager API failed after retries: {last_err}")
    Video.objects.filter(pk=video.pk).update(status="failed")
    return
