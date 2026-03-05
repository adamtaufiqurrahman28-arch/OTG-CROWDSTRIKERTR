from typing import List
from app.utils.common import ensure_success, get_body, get_resources


class HostGroupService:
    def __init__(self, client):
        self.client = client

    def list_group_aids(self, host_group_id: str) -> List[str]:
        aids: List[str] = []
        offset = None

        while True:
            kwargs = {"id": host_group_id, "limit": 5000}
            if offset:
                kwargs["offset"] = offset

            response = self.client.query_group_members(**kwargs)
            ensure_success(response, "query_group_members")

            for item in get_resources(response):
                if isinstance(item, str):
                    aids.append(item)
                elif isinstance(item, dict):
                    aid = item.get("device_id") or item.get("aid") or item.get("id")
                    if aid:
                        aids.append(aid)

            meta = get_body(response).get("meta", {})
            pagination = meta.get("pagination", {}) if isinstance(meta, dict) else {}
            next_offset = pagination.get("offset")
            if not next_offset or next_offset == offset:
                break
            offset = next_offset

        deduped: List[str] = []
        seen = set()
        for aid in aids:
            if aid not in seen:
                seen.add(aid)
                deduped.append(aid)
        return deduped
