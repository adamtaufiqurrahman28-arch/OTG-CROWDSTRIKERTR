# app/services/selection_service.py
from typing import List
from app.utils.common import is_online

class SelectionService:
    def select(self, candidates: List[dict], online_minutes: int, top_n_online: int, interactive: bool):
        """
        candidates: list dict minimal punya hostname, aid, last_seen, agent_version
        """
        # sort online first
        def key(h):
            online = is_online(h.get("last_seen", ""), online_minutes)
            # online = 0 biar naik ke atas
            return (0 if online else 1, h.get("last_seen", ""))
        ordered = sorted(candidates, key=key)

        online = [h for h in ordered if is_online(h.get("last_seen", ""), online_minutes)]
        offline = [h for h in ordered if not is_online(h.get("last_seen", ""), online_minutes)]

        if not interactive:
            if top_n_online and top_n_online > 0:
                return online[:top_n_online]
            # default: online dulu + offline (kalau kamu mau online-only, tinggal return online)
            return ordered

        # interactive menu
        print(f"\nONLINE={len(online)} | OFFLINE={len(offline)} | TOTAL={len(ordered)}")
        print("1) Install ALL ONLINE")
        print("2) Install TOP N ONLINE")
        print("3) Pilih manual (index, contoh: 1,3,7)")
        print("4) Cancel\n")

        for i, h in enumerate(ordered, start=1):
            flag = "ONLINE" if is_online(h.get("last_seen", ""), online_minutes) else "OFFLINE"
            print(f"{i:>3}. [{flag}] {h.get('hostname')} | {h.get('agent_version')} | last_seen={h.get('last_seen')}")

        choice = input("\nPilih menu: ").strip()
        if choice == "1":
            return online
        if choice == "2":
            n = int(input("Top N: ").strip())
            return online[:n]
        if choice == "3":
            raw = input("Index: ").strip()
            picks = set(int(x) for x in raw.split(",") if x.strip().isdigit())
            return [h for i, h in enumerate(ordered, start=1) if i in picks]
        return []