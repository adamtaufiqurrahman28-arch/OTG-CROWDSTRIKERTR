from dataclasses import asdict
from typing import Dict, List
from app.models.host import HostRecord, CandidateRecord
from app.utils.common import chunked, ensure_success, get_resources, parse_version, to_build_3


class InventoryService:
    def __init__(self, client):
        self.client = client

    def get_inventory(self, aids: List[str]) -> List[HostRecord]:
        inventory: List[HostRecord] = []
        for batch in chunked(aids, 5000):
            response = self.client.post_device_details_v2(ids=batch)
            ensure_success(response, "post_device_details_v2")
            for item in get_resources(response):
                if not isinstance(item, dict):
                    continue
                inventory.append(
                    HostRecord(
                        aid=item.get("device_id") or "",
                        hostname=item.get("hostname") or "",
                        platform_name=item.get("platform_name") or "",
                        agent_version=item.get("agent_version") or "",
                        status=item.get("status") or "",
                        last_seen=item.get("last_seen") or "",
                    )
                )
        return inventory

    def build_candidate_summary(self, inventory: List[HostRecord], target_build: str) -> Dict[str, object]:
        target_tuple = parse_version(to_build_3(target_build))
        candidates: List[CandidateRecord] = []
        counters = {
            "equal": 0,
            "higher": 0,
            "unknown": 0,
            "non_windows": 0,
        }

        for host in inventory:
            platform = (host.platform_name or "").lower()
            if "windows" not in platform:
                counters["non_windows"] += 1
                continue

            current_build = to_build_3(host.agent_version)
            current_tuple = parse_version(current_build)
            if not current_tuple:
                counters["unknown"] += 1
                continue

            if current_build == to_build_3(target_build):
                counters["equal"] += 1
            elif current_tuple < target_tuple:
                candidates.append(
                    CandidateRecord(
                        aid=host.aid,
                        hostname=host.hostname,
                        current_version=host.agent_version,
                        current_build=current_build,
                        target_build=to_build_3(target_build),
                    )
                )
            else:
                counters["higher"] += 1

        return {
            "candidates": candidates,
            "counts": counters,
            "inventory_rows": [asdict(host) for host in inventory],
            "candidate_rows": [asdict(candidate) for candidate in candidates],
        }
