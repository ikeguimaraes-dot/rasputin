from __future__ import annotations

from urllib.parse import quote

import httpx

from auditoria.config import Settings


class Storage:
    def __init__(self, settings: Settings):
        self.settings = settings

    def request(self, method, path, **kwargs):
        headers = kwargs.pop("headers", {})
        headers.update(
            {
                "apikey": self.settings.supabase_service_role_key,
                "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
            }
        )
        response = httpx.request(
            method,
            self.settings.supabase_url.rstrip("/") + "/storage/v1/" + path,
            headers=headers,
            timeout=60,
            **kwargs,
        )
        if response.is_error:
            raise RuntimeError(f"Storage indisponível (HTTP {response.status_code})")
        return response

    def put(self, bucket: str, path: str, content: bytes, mime: str):
        self.request(
            "POST",
            f"object/{quote(bucket)}/{quote(path)}",
            content=content,
            headers={"Content-Type": mime, "x-upsert": "true"},
        )

    def get(self, bucket: str, path: str) -> bytes:
        return self.request("GET", f"object/{quote(bucket)}/{quote(path)}").content

    def sign(self, bucket: str, path: str) -> str:
        data = self.request(
            "POST", f"object/sign/{quote(bucket)}/{quote(path)}", json={"expiresIn": 120}
        ).json()
        url = data["signedURL"]
        return self.settings.supabase_url.rstrip("/") + "/storage/v1" + url
