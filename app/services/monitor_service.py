import time
from typing import Dict, List, Set
from app.models.host import HostRecord
from app.utils.common import parse_version, to_build_3


class MonitorService:
    def __init__(self, inventory_service):
        self.inventory_service = inventory_service

    def wait_until_upgraded(
        self,
        remaining_aids: List[str],
        target_build: str,
        poll_seconds: int,
        max_polls: int,
    ) -> Set[str]:
        remaining = set(remaining_aids)
        target_tuple = parse_version(to_build_3(target_build))

        for index in range(1, max_polls + 1):
            time.sleep(poll_seconds)
            inventory: List[HostRecord] = self.inventory_service.get_inventory(list(remaining))
            upgraded_now = []
            for host in inventory:
                current_tuple = parse_version(to_build_3(host.agent_version))
                if current_tuple >= target_tuple:
                    upgraded_now.append(host.aid)

            for aid in upgraded_now:
                remaining.discard(aid)

            print(f"    Poll {index}/{max_polls}: upgraded={len(upgraded_now)} remaining={len(remaining)}")
            if not remaining:
                print("    Semua kandidat sudah mencapai target atau lebih tinggi.")
                break

        return remaining


