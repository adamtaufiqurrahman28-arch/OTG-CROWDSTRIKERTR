import os
import re
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from falconpy import HostGroup, Hosts, RealTimeResponse, RealTimeResponseAdmin
from app.services.host_group_service import HostGroupService
from app.services.inventory_service import InventoryService
from app.services.putfile_service import PutFileService
from app.services.rtr_service import RTRService

EXPORT_DIR = Path("./exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

LOGO_PATH = Path("assets/seraphim_logo.png")

load_dotenv()

def is_online(last_seen_iso: str, minutes: int = 10) -> bool:
    if not last_seen_iso:
        return False
    try:
        dt = datetime.fromisoformat(last_seen_iso.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - dt
        return age.total_seconds() <= minutes * 60
    except Exception:
        return False


def to_build3(ver: str) -> str:
    nums = re.findall(r"\d+", str(ver or ""))
    if len(nums) < 3:
        return ""
    return ".".join(nums[:3])


def build_clients():
    cid = os.getenv("FALCON_CLIENT_ID")
    csec = os.getenv("FALCON_CLIENT_SECRET")
    if not cid or not csec:
        st.error("FALCON_CLIENT_ID / FALCON_CLIENT_SECRET belum di-set (env atau .env).")
        st.stop()

    return {
        "host_group": HostGroup(client_id=cid, client_secret=csec),
        "hosts": Hosts(client_id=cid, client_secret=csec),
        "rtr": RealTimeResponse(client_id=cid, client_secret=csec),
        "rtr_admin": RealTimeResponseAdmin(client_id=cid, client_secret=csec),
    }


def download_json_button(label: str, obj: dict, filename: str):
    st.download_button(
        label=label,
        data=json.dumps(obj, indent=2).encode("utf-8"),
        file_name=filename,
        mime="application/json",
    )


def download_csv_button(label: str, df: pd.DataFrame, filename: str):
    st.download_button(
        label=label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )


st.set_page_config(page_title="CrowdStrike Bulk Upgrade", layout="wide")

# Header branding + logo
colA, colB = st.columns([1, 8])
with colA:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=110)
    else:
        st.write("")  # logo optional
with colB:
    st.markdown("## CrowdStrike RTR Bulk Upgrade")

clients = build_clients()

# Services
host_group_service = HostGroupService(clients["host_group"])
inventory_service = InventoryService(clients["hosts"])
put_file_service = PutFileService(clients["rtr_admin"])
rtr_service = RTRService(clients["rtr"], clients["rtr_admin"], EXPORT_DIR)


# Sidebar inputs
with st.sidebar:
    st.header("Config")

    host_group_id = st.text_input("Host Group ID", value="", placeholder="a3102b1b...")
    target_build = st.text_input("Target Build (3-part)", value="7.34.20610")
    put_name = st.text_input("Put File Name", value="FalconSensor_Latest.exe")
    install_args = st.text_input(
        "Install Args",
        value='/install /quiet /norestart /log "C:\\Windows\\Temp\\FalconSensorLogs"',
    )

    # Optional token (kalau env butuh)
    prov_token = st.text_input("Maintenance Token (optional)", value="", type="password")
    if prov_token.strip():
        # jangan hardcode di code—ini hanya runtime concat
        install_args_runtime = f'{install_args} ProvToken={prov_token.strip()}'
    else:
        install_args_runtime = install_args

    st.divider()

    online_minutes = st.number_input("Online threshold (minutes)", min_value=1, max_value=1440, value=10)
    only_online = st.checkbox("Only show ONLINE candidates", value=False)
    top_n_online = st.number_input("Limit N hosts (0 = no limit)", min_value=0, max_value=5000, value=0)

    st.divider()

    queue_offline = st.checkbox("Queue offline hosts", value=False)
    do_monitor = st.checkbox("Monitor agent_version after run", value=True)
    poll_seconds = st.number_input("Poll seconds", min_value=10, max_value=600, value=120)
    max_polls = st.number_input("Max polls", min_value=1, max_value=500, value=60)

    st.divider()
    fetch_btn = st.button("1) Fetch Candidates", use_container_width=True)
    run_btn = st.button("2) Run Put-and-Run (Selected)", use_container_width=True)
    monitor_btn = st.button("3) Monitor Only (Selected)", use_container_width=True)


# State
if "inventory_df" not in st.session_state:
    st.session_state.inventory_df = None
if "candidates_df" not in st.session_state:
    st.session_state.candidates_df = None
if "selected_df" not in st.session_state:
    st.session_state.selected_df = None
if "last_response" not in st.session_state:
    st.session_state.last_response = None


def fetch_candidates():
    if not host_group_id.strip():
        st.error("Host Group ID wajib diisi.")
        return

    st.info("Ambil AID dari host-group...")
    aids = host_group_service.list_group_aids(host_group_id.strip())
    if not aids:
        st.warning("Host-group kosong.")
        return

    aids_path = EXPORT_DIR / f"{host_group_id}_aids.csv"
    pd.DataFrame({"aid": aids}).to_csv(aids_path, index=False)

    st.info("Ambil inventory host...")
    inventory = inventory_service.get_inventory(aids)
    summary = inventory_service.build_candidate_summary(inventory, to_build3(target_build))

    inv_df = pd.DataFrame(summary["inventory_rows"])
    cand_df = pd.DataFrame(summary["candidate_rows"])

    # tambahkan online indicator (kalau last_seen tersedia)
    if "last_seen" in inv_df.columns:
        inv_df["online"] = inv_df["last_seen"].apply(lambda x: is_online(str(x), online_minutes))

    # candidate_rows kadang tidak punya last_seen -> ambil dari inventory untuk join
    if "last_seen" not in cand_df.columns and "aid" in cand_df.columns and "aid" in inv_df.columns:
        join_cols = ["aid", "last_seen"]
        extra = inv_df[join_cols].drop_duplicates()
        cand_df = cand_df.merge(extra, on="aid", how="left")
    if "last_seen" in cand_df.columns:
        cand_df["online"] = cand_df["last_seen"].apply(lambda x: is_online(str(x), online_minutes))

    if only_online and "online" in cand_df.columns:
        cand_df = cand_df[cand_df["online"] == True]

    # limit N (ambil yang online dulu kalau ada kolom online)
    if top_n_online and top_n_online > 0:
        if "online" in cand_df.columns:
            cand_df = cand_df.sort_values(by=["online", "last_seen"], ascending=[False, False]).head(int(top_n_online))
        else:
            cand_df = cand_df.head(int(top_n_online))

    # simpan
    st.session_state.inventory_df = inv_df
    st.session_state.candidates_df = cand_df

    # export kandidat
    cand_path = EXPORT_DIR / f"{host_group_id}_upgrade_candidates_rtr.csv"
    cand_df.to_csv(cand_path, index=False)

    st.success("Fetch selesai. Kandidat & inventory sudah tersedia.")


def run_put_and_run(selected_df: pd.DataFrame):
    if selected_df is None or selected_df.empty:
        st.error("Tidak ada host terpilih.")
        return

    st.info("Resolve existing put-file dari RTR...")
    put_meta = put_file_service.resolve_existing_put_file(put_name=put_name, put_file_id=None)
    resolved_put_name = put_meta.get("name") or put_name

    aids = selected_df["aid"].dropna().astype(str).tolist()

    st.info("Batch init RTR sessions...")
    batch_id = rtr_service.batch_init(aids, queue_offline)

    st.info("Execute put-and-run (fire-and-forget)...")
    resp = rtr_service.put_and_run(
        batch_id=batch_id,
        host_ids=aids,
        put_name=resolved_put_name,
        install_args=install_args_runtime,
        queue_offline=queue_offline,
    )

    st.session_state.last_response = resp

    out_json = EXPORT_DIR / f"{host_group_id}_rtr_put_and_run_response.json"
    out_json.write_text(json.dumps(resp, indent=2), encoding="utf-8")

    st.success(f"Command dikirim. Response saved: {out_json}")
    download_json_button("Download response JSON", resp, out_json.name)

    if do_monitor:
        monitor_versions(selected_df)


def monitor_versions(selected_df: pd.DataFrame):
    aids = selected_df["aid"].dropna().astype(str).tolist()
    target = to_build3(target_build)

    placeholder = st.empty()
    progress = st.progress(0)

    remaining = set(aids)
    total = len(aids)

    for i in range(1, int(max_polls) + 1):
        time.sleep(int(poll_seconds))

        inv = inventory_service.get_inventory(list(remaining))
        # build quick map aid->build
        upgraded_now = []
        for row in inv:
            def pick(row, key, default=""):
                if isinstance(row, dict):
                    return row.get(key, default)
                return getattr(row, key, default)
            aid = pick(row, "aid") or pick(row, "device_id") or pick(row, "id")
            ver = pick(row, "agent_version") or ""
            if to_build3(ver) >= target:
                upgraded_now.append(aid)
                

        for aid in upgraded_now:
            if aid in remaining:
                remaining.remove(aid)

        done = total - len(remaining)
        placeholder.write(f"Poll {i}/{max_polls}: newly_upgraded={len(upgraded_now)} | total_upgraded={done}/{total} | remaining={len(remaining)}")
        progress.progress(min(done / max(total, 1), 1.0))

        if not remaining:
            break

    rem_path = EXPORT_DIR / f"{host_group_id}_monitor_remaining.csv"
    pd.DataFrame({"aid": sorted(list(remaining))}).to_csv(rem_path, index=False)
    st.success(f"Monitoring selesai. Remaining CSV: {rem_path}")
    download_csv_button("Download remaining CSV", pd.DataFrame({"aid": sorted(list(remaining))}), rem_path.name)


# Actions
if fetch_btn:
    fetch_candidates()

# Layout: show inventory & candidates
col1, col2 = st.columns(2)

with col1:
    st.subheader("Inventory")
    if st.session_state.inventory_df is not None:
        st.dataframe(st.session_state.inventory_df, use_container_width=True, height=420)
        download_csv_button("Download inventory CSV", st.session_state.inventory_df, f"{host_group_id}_inventory.csv")
    else:
        st.write("Klik **Fetch Candidates** dulu.")

with col2:
    st.subheader("Candidates")
    if st.session_state.candidates_df is not None:
        df = st.session_state.candidates_df.copy()
        if "selected" not in df.columns:
            df.insert(0, "selected", False)

        edited = st.data_editor(
            df,
            use_container_width=True,
            height=420,
            num_rows="fixed",
            hide_index=True,
        )
        st.session_state.selected_df = edited[edited["selected"] == True].drop(columns=["selected"], errors="ignore")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.write(f"Total candidates: **{len(df)}**")
        with c2:
            st.write(f"Selected: **{len(st.session_state.selected_df) if st.session_state.selected_df is not None else 0}**")
        with c3:
            if st.session_state.selected_df is not None and not st.session_state.selected_df.empty:
                download_csv_button("Download selected CSV", st.session_state.selected_df, f"{host_group_id}_selected.csv")
    else:
        st.write("Klik **Fetch Candidates** dulu.")

# Run button
if run_btn:
    if st.session_state.selected_df is None or st.session_state.selected_df.empty:
        st.error("Pilih minimal 1 host di tabel Candidates (centang kolom selected).")
    else:
        run_put_and_run(st.session_state.selected_df)

if monitor_btn:
    if st.session_state.selected_df is None or st.session_state.selected_df.empty:
        st.error("Pilih minimal 1 host untuk monitor-only.")
    else:
        monitor_versions(st.session_state.selected_df)

# Show last response summary
st.subheader("Last RTR Response (summary)")
if st.session_state.last_response:
    per_host = None
    try:
        per_host = st.session_state.last_response["body"]["combined"]["resources"]
    except Exception:
        per_host = None

    if isinstance(per_host, dict):
        rows = []
        for aid, d in per_host.items():
            errs = d.get("errors") or []
            code = errs[0].get("code") if errs else ""
            msg = errs[0].get("message") if errs else ""
            rows.append({
                "aid": aid,
                "complete": d.get("complete"),
                "offline_queued": d.get("offline_queued"),
                "task_id": d.get("task_id", ""),
                "error_code": code,
                "error_message": msg,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=260)
    else:
        st.json(st.session_state.last_response)
else:
    st.write("Belum ada response (jalankan put-and-run dulu).")
st.divider()
st.caption("Powered by Seraphim Digital Technology")