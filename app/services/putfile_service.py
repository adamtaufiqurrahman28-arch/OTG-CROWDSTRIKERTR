from typing import Any, Dict, List, Optional
from app.utils.common import chunked, ensure_success, get_resources


class PutFileService:
    def __init__(self, client):
        self.client = client

    def resolve_existing_put_file(
        self,
        put_name: Optional[str] = None,
        put_file_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if put_file_id:
            response = self.client.get_put_files_v2(ids=put_file_id)
            ensure_success(response, "get_put_files_v2(by id)")
            resources = get_resources(response)
            if not resources:
                raise RuntimeError(f"Put-file ID '{put_file_id}' tidak ditemukan.")
            if isinstance(resources[0], dict):
                return resources[0]
            raise RuntimeError(f"Format response get_put_files_v2(by id) tidak sesuai: {response}")

        if not put_name:
            raise RuntimeError("Isi salah satu: put_name atau put_file_id")

        lookup = self.client.list_put_files(filter=f"name:'{put_name}'", limit=100)
        ensure_success(lookup, "list_put_files(filter by name)")
        ids = get_resources(lookup)

        if not ids:
            fallback = self.client.list_put_files(limit=500)
            ensure_success(fallback, "list_put_files(fallback)")
            ids = get_resources(fallback)

        if not ids:
            raise RuntimeError(f"Tidak ada put-file di RTR untuk dicocokkan dengan '{put_name}'.")

        metadata: List[Dict[str, Any]] = []
        for batch_ids in chunked(ids, 100):
            response = self.client.get_put_files_v2(ids=batch_ids)
            ensure_success(response, "get_put_files_v2")
            for item in get_resources(response):
                if isinstance(item, dict):
                    metadata.append(item)

        exact = [item for item in metadata if (item.get("name") or "") == put_name]
        if exact:
            return exact[0]

        ci = [item for item in metadata if (item.get("name") or "").lower() == put_name.lower()]
        if ci:
            return ci[0]

        available_names = sorted({item.get("name") for item in metadata if item.get("name")})
        preview = ", ".join(available_names[:15]) if available_names else "(tidak ada nama file terbaca)"
        raise RuntimeError(
            f"Put-file '{put_name}' tidak ditemukan. Contoh yang terbaca: {preview}"
        )
