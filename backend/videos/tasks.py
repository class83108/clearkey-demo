import os
import secrets
import subprocess
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

    # Build docker run command
    # We mount the named volume 'media_data' directly so paths are valid for the host docker daemon.
    # Input/Output paths are passed via env IN/OUT inside the packager container.
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "--platform", "linux/amd64",
        "-v", "media_data:/work",
        "-e",
        f"KID_HEX={video.kid_hex}",
        "-e",
        f"KEY_HEX={video.key_hex}",
        "-e",
        f"IN={input_path_in_packager}",
        "-e",
        f"OUT={out_dir_in_packager}",
        "packager",
        "sh",
        "/work/pack.sh",
    ]

    logger.info(f"Running docker command: {' '.join(docker_cmd)}")
    
    try:
        proc = subprocess.run(
            docker_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        
        logger.info(f"Docker command stdout: {proc.stdout}")
        logger.info(f"Docker command stderr: {proc.stderr}")
        logger.info(f"Docker command return code: {proc.returncode}")
        
        if proc.returncode != 0:
            logger.error(f"Docker command failed with return code {proc.returncode}")
            logger.error(f"Docker stderr: {proc.stderr}")
            Video.objects.filter(pk=video.pk).update(status="failed")
            return

        # Success: update status and path
        encrypted_rel_path = f"encrypted/{video.id}/stream.mpd"
        logger.info(f"Encryption successful, setting encrypted_path: {encrypted_rel_path}")
        Video.objects.filter(pk=video.pk).update(
            status="READY",
            encrypted_path=encrypted_rel_path,
        )
    except Exception as e:
        logger.exception(f"Unexpected error during encryption for video {video_id}: {e}")
        Video.objects.filter(pk=video.pk).update(status="failed")
        return
