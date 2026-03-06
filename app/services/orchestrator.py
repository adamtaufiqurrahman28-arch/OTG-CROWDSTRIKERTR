from pathlib import Path
from app.config.settings import AppConfig
from app.clients.falcon import FalconClients
from app.services.host_group_service import HostGroupService
from app.services.inventory_service import InventoryService
from app.services.putfile_service import PutFileService
from app.services.rtr_service import RTRService
from app.services.monitor_service import MonitorService
from app.utils.common import write_aids_csv, write_csv, write_json
from app.services.selection_service import SelectionService


def run_bulk_upgrade(config: AppConfig, clients: FalconClients) -> None:
    host_group_service = HostGroupService(clients.host_group)
    inventory_service = InventoryService(clients.hosts)
    put_file_service = PutFileService(clients.rtr_admin)
    rtr_service = RTRService(clients.rtr, clients.rtr_admin, config.export_dir)
    monitor_service = MonitorService(inventory_service)
    selection_service = SelectionService()

    print(f"[1] Ambil AID dari host-group: {config.host_group_id}")
    aids = host_group_service.list_group_aids(config.host_group_id)
    if not aids:
        print("Host-group kosong.")
        return

    aids_csv = config.export_dir / f"{config.host_group_id}_aids.csv"
    write_aids_csv(aids_csv, aids)
    print(f"    Total AID: {len(aids)}")
    print(f"    Export AID: {aids_csv}")

    print("[2] Ambil inventory host")
    inventory = inventory_service.get_inventory(aids)
    summary = inventory_service.build_candidate_summary(inventory, config.target_build)

    inventory_csv = config.export_dir / f"{config.host_group_id}_inventory.csv"
    write_csv(
        inventory_csv,
        summary["inventory_rows"],
        ["aid", "hostname", "platform_name", "agent_version", "status", "last_seen"],
    )
    print(f"    Export inventory: {inventory_csv}")

    candidate_rows = summary["candidate_rows"]
    counts = summary["counts"]
    candidates_csv = config.export_dir / f"{config.host_group_id}_upgrade_candidates_rtr.csv"
    write_csv(
        candidates_csv,
        candidate_rows,
        ["aid", "hostname", "current_version", "current_build", "target_build"],
    )

    print("[3] Summary Windows")
    print(f"    Sudah target : {counts['equal']}")
    print(f"    Perlu upgrade: {len(candidate_rows)}")
    print(f"    Lebih tinggi : {counts['higher']}")
    print(f"    Unknown ver  : {counts['unknown']}")
    print(f"    Non-Windows  : {counts['non_windows']}")
    print(f"    Export kandidat: {candidates_csv}")

    if config.dry_run:
        print("[DRY-RUN] stop di sini.")
        return

    if not candidate_rows:
        print("Tidak ada kandidat upgrade Windows.")
        return

    # ====== SELECTION (yang kamu minta) ======
    # Letakkan DI SINI: setelah kandidat dihitung, sebelum resolve put-file & RTR execute
    # SelectionService akan menentukan host mana yang diprioritaskan/diinstall
    selected_rows = selection_service.select(
        candidates=candidate_rows,
        online_minutes=getattr(config, "online_minutes", 10),
        top_n_online=getattr(config, "top_n_online", 0),
        interactive=getattr(config, "interactive", False),
    )
    if not selected_rows:
        print("Tidak ada host dipilih. Stop.")
        return

    candidate_rows = selected_rows
    # ========================================

    print("[4] Resolve existing put-file dari RTR")
    put_meta = put_file_service.resolve_existing_put_file(
        put_name=config.put_name,
        put_file_id=config.put_file_id,
    )
    put_id = put_meta.get("id") or ""
    put_name = put_meta.get("name") or config.put_name or ""
    print(f"    Put-file ditemukan: id={put_id} | name={put_name}")

    candidate_aids = [row["aid"] for row in candidate_rows]

    print("[5] Batch init RTR sessions")
    batch_id = rtr_service.batch_init(candidate_aids, config.queue_offline)
    print(f"    batch_id: {batch_id}")

    print("[6] Execute batch admin command: put-and-run")
    
    response = rtr_service.put_and_run(
        batch_id=batch_id,
        host_ids=candidate_aids,
        put_name=put_name,
        install_args=config.install_args,
        queue_offline=config.queue_offline,
)

    response_json = config.export_dir / f"{config.host_group_id}_rtr_put_and_run_response.json"
    write_json(response_json, response)
    print(f"    Response saved: {response_json}")

    if not config.monitor:
        print("[SELESAI] Command sudah dikirim.")
        return

    print("[7] Monitoring build host")
    remaining = monitor_service.wait_until_upgraded(
        remaining_aids=candidate_aids,
        target_build=config.target_build,
        poll_seconds=config.poll_seconds,
        max_polls=config.max_polls,
    )

    remaining_csv = config.export_dir / f"{config.host_group_id}_monitor_remaining.csv"
    write_csv(remaining_csv, [{"aid": aid} for aid in sorted(remaining)], ["aid"])
    print(f"    Remaining AIDs: {remaining_csv}")
    print("[SELESAI]")