from collections import deque
from pathlib import Path
from urllib.parse import unquote_plus
import logging
import os
import subprocess
import sys

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from secret_keys import SecretKeys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("video-transcoder")

secret_keys = SecretKeys()


class VideoTranscoder:
    def __init__(self):
        client_kwargs = {
            "config": Config(
                signature_version="s3v4",
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            )
        }
        if secret_keys.REGION_NAME:
            client_kwargs["region_name"] = secret_keys.REGION_NAME
        if secret_keys.AWS_ACCESS_KEY_ID and secret_keys.AWS_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = secret_keys.AWS_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = secret_keys.AWS_SECRET_ACCESS_KEY
        self.s3_client = boto3.client("s3", **client_kwargs)

    def _get_content_type(self, file_path: str):
        if file_path.endswith(".m3u8"):
            return "application/vnd.apple.mpegurl"
        elif file_path.endswith(".ts"):
            return "video/MP2T"
        else:
            return "video/mp4"

    # get location from env variable and fetch from s3
    def download_video(self, local_path: str):
        s3_key = unquote_plus(secret_keys.S3_KEY)
        logger.info("Downloading s3://%s/%s", secret_keys.S3_BUCKET, s3_key)
        self.s3_client.download_file(
            secret_keys.S3_BUCKET, s3_key, str(local_path)
        )

    def transcode_video(self, input_path: str, output_dir: str):
        # HLS transcoding
        # cmd = [
        #     "ffmpeg",
        #     "-i",
        #     input_path,
        #     "-filter_complex",
        #     "[0:v]split=3[v1][v2][v3];"
        #     "[v1]scale=640:360:flags=fast_bilinear[360p];"
        #     "[v2]scale=1280:720:flags=fast_bilinear[720p];"
        #     "[v3]scale=1920:1080:flags=fast_bilinear[1080p]",
        #     "-map",
        #     "[360p]",
        #     "-map",
        #     "[720p]",
        #     "-map",
        #     "[1080p]",
        #     "-c:v",
        #     "libx264",
        #     "-preset",
        #     "veryfast",
        #     "-profile:v",
        #     "high",
        #     "-level:v",
        #     "4.1",
        #     "-g",
        #     "48",
        #     "-keyint_min",
        #     "48",
        #     "-sc_threshold",
        #     "0",
        #     "-b:v:0",
        #     "1000k",
        #     "-b:v:1",
        #     "4000k",
        #     "-b:v:2",
        #     "8000k",
        #     "-f",
        #     "hls",
        #     "-hls_time",
        #     "6",
        #     "-hls_playlist_type",
        #     "vod",
        #     "-hls_flags",
        #     "independent_segments",
        #     "-hls_segment_type",
        #     "mpegts",
        #     "-hls_list_size",
        #     "0",
        #     "-master_pl_name",
        #     "master.m3u8",
        #     "-var_stream_map",
        #     "v:0 v:1 v:2",
        #     "-hls_segment_filename",
        #     f"{output_dir}/%v/segment_%03d.ts",
        #     f"{output_dir}/%v/playlist.m3u8",
        # ]

        # Dash transcoding
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostats",
            "-progress",
            "pipe:1",
            "-stats_period",
            "15",
            "-i",
            input_path,
            "-filter_complex",
            "[0:v]split=3[v1][v2][v3];"
            "[v1]scale=640:360:flags=fast_bilinear[360p];"
            "[v2]scale=1280:720:flags=fast_bilinear[720p];"
            "[v3]scale=1920:1080:flags=fast_bilinear[1080p]",
            # 360p video stream
            "-map",
            "[360p]",
            "-c:v:0",
            "libx264",
            "-b:v:0",
            "1000k",
            "-preset",
            "veryfast",
            "-profile:v",
            "high",
            "-level:v",
            "4.1",
            "-g",
            "48",
            "-keyint_min",
            "48",
            # 720p video stream
            "-map",
            "[720p]",
            "-c:v:1",
            "libx264",
            "-b:v:1",
            "4000k",
            "-preset",
            "veryfast",
            "-profile:v",
            "high",
            "-level:v",
            "4.1",
            "-g",
            "48",
            "-keyint_min",
            "48",
            # 1080p video stream
            "-map",
            "[1080p]",
            "-c:v:2",
            "libx264",
            "-b:v:2",
            "8000k",
            "-preset",
            "veryfast",
            "-profile:v",
            "high",
            "-level:v",
            "4.1",
            "-g",
            "48",
            "-keyint_min",
            "48",
            # Audio stream
            "-map",
            "0:a",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            # DASH specific settings
            "-use_timeline",
            "1",
            "-use_template",
            "1",
            "-adaptation_sets",
            "id=0,streams=v id=1,streams=a",
            "-f",
            "dash",
            f"{output_dir}/manifest.mpd",
        ]
        logger.info("Transcoding %s", input_path)
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        progress = {}
        error_lines = deque(maxlen=50)
        for line in process.stdout:
            key, sep, value = line.strip().partition("=")
            if not sep:
                error_lines.append(line.rstrip())
                continue
            progress[key] = value
            if key == "progress":
                logger.info(
                    "ffmpeg progress: time=%s speed=%s fps=%s",
                    progress.get("out_time", "?").split(".")[0],
                    progress.get("speed", "?"),
                    progress.get("fps", "?"),
                )
        returncode = process.wait()
        if returncode != 0:
            logger.error(
                "ffmpeg exited with code %s:\n%s", returncode, "\n".join(error_lines)
            )
            raise RuntimeError(f"Failed to transcode video: {returncode}")
        logger.info("Transcoding finished")

    def upload_video(self, prefix: str, local_dir):
        logger.info(
            "Uploading to s3://%s/%s", secret_keys.S3_PROCESSED_VIDEOS_BUCKET, prefix
        )
        for root, _, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                s3_key = f"{prefix}/{os.path.relpath(local_path,local_dir)}"
                self.s3_client.upload_file(
                    local_path,
                    secret_keys.S3_PROCESSED_VIDEOS_BUCKET,
                    s3_key,
                    ExtraArgs={
                        "ACL": "public-read",
                        "ContentType": self._get_content_type(local_path),
                    },
                )

    def process_video(self):
        work_dir = Path("/tmp/workspace")
        work_dir.mkdir(exist_ok=True)
        input_path = work_dir / "input.mp4"
        output_path = work_dir / "output"
        output_path.mkdir(exist_ok=True)
        try:
            self.download_video(input_path)
            self.transcode_video(str(input_path), str(output_path))
            self.upload_video(unquote_plus(secret_keys.S3_KEY), str(output_path))

        finally:
            if input_path.exists():
                input_path.unlink()
            if output_path.exists():
                import shutil

                shutil.rmtree(str(output_path))


if __name__ == "__main__":
    try:
        VideoTranscoder().process_video()
        logger.info("Video processed successfully")
    except ClientError as e:
        error = e.response.get("Error", {})
        logger.exception(
            "AWS %s failed: code=%s message=%s request_id=%s",
            e.operation_name,
            error.get("Code"),
            error.get("Message"),
            e.response.get("ResponseMetadata", {}).get("RequestId"),
        )
        sys.exit(1)
    except Exception:
        logger.exception("Video processing failed")
        sys.exit(1)
