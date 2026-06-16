"""OSS upload utilities."""

import logging
from typing import Optional

import oss2

from ..config import APIKeys

logger = logging.getLogger(__name__)


class OSSUploader:
    def __init__(self, api_keys: Optional[APIKeys] = None):
        if api_keys is None:
            api_keys = APIKeys.from_env()

        if not api_keys.oss_access_key_id or not api_keys.oss_access_key_secret:
            raise ValueError("OSS credentials not set")

        self.api_keys = api_keys
        self.auth = oss2.Auth(
            api_keys.oss_access_key_id, api_keys.oss_access_key_secret
        )
        self.bucket_name = api_keys.oss_bucket
        self.endpoint = api_keys.oss_endpoint
        self._bucket = None

    @property
    def bucket(self) -> oss2.Bucket:
        if self._bucket is None:
            self._bucket = oss2.Bucket(
                self.auth, f"https://{self.endpoint}", self.bucket_name
            )
            try:
                self._bucket.get_bucket_info()
                logger.info(f"OSS bucket connected: {self.bucket_name}")
            except Exception as e:
                logger.warning(f"Bucket verify failed: {e}")
        return self._bucket

    def upload(self, local_path: str, oss_key: str) -> str:
        result = self.bucket.put_object_from_file(oss_key, local_path)
        if result.status != 200:
            raise RuntimeError(f"Upload failed: {result.status}")
        signed_url = self.bucket.sign_url("GET", oss_key, 7200)
        logger.info(f"Uploaded: {oss_key}")
        return signed_url


def upload_to_oss(
    local_path: str, oss_key: str, api_keys: Optional[APIKeys] = None
) -> str:
    uploader = OSSUploader(api_keys)
    return uploader.upload(local_path, oss_key)
