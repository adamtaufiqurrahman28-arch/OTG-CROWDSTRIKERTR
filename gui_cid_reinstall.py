import os
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from falconpy import HostGroup, Hosts, RealTimeResponse, RealTimeResponseAdmin

from app.services.host_group_service import HostGroupService
from app.services.inventory_service import InventoryService
from app.services.putfile_service import PutFileService
from app.services.cid_reinstall_rtr_service import CIDReinstallRTRService


load_dotenv()

EXPORT_DIR = Path("./exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

LOGO_PATH = Path("assets/seraphim_logo.png")


def build_clients():
    client_id = os.getenv("FALCON_CLIENT_ID")
    client_secret = os.getenv("FALCON_CLIENT_SECRET")

    if not client_id or not client_secret:
        st.error("FALCON_CLIENT_ID / FALCON_CLIENT_SECRET belum di-set.")
        st.stop()

    return {
        "host_group": HostGroup(client_id=client_id, client_secret=client_secret),
        "hosts": Hosts(client_id=client_id, client_secret=client_secret),
        "rtr": RealTimeResponse(client_id=client_id, client_secret=client_secret),
        "rtr_admin": RealTimeResponseAdmin(client_id=client_id, client_secret=client_secret),
    }


def inventory_to_df(inventory) -> pd.DataFrame:
    rows = []

    for host in inventory:
        if hasattr(host, "__dict__"):
            row = host.__dict__
        elif isinstance(host, dict):
            row = host
        else:
            continue

        rows.append(
            {
                "aid": row.get("aid") or row.get("device_id") or row.get("id") or "",
                "hostname": row.get("hostname") or "",
                "platform_name": row.get("platform_name") or "",
                "agent_version": row.get("agent_version") or "",
                "status": row.get("status") or "",
                "last_seen": row.get("last_seen") or "",
            }
        )

    return pd.DataFrame(rows)


def filter_windows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "platform_name" not in df.columns:
        return pd.DataFrame()

    return df[df["platform_name"].fillna("").str.lower().str.contains("windows")].copy()


def chunk_list(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def download_csv(label: str, df: pd.DataFrame, filename: str):
    st.download_button(
        label=label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )


def download_json(label: str, obj: dict, filename: str):
    st.download_button(
        label=label,
        data=json.dumps(obj, indent=2).encode("utf-8"),
        file_name=filename,
        mime="application/json",
    )


def verify_put_file(put_service: PutFileService, name: str) -> bool:
    try:
        put_service.resolve_existing_put_file(put_name=name.strip(), put_file_id=None)
        return True
    except Exception:
        return False


st.set_page_config(
    page_title="CID Reinstall via RTR",
    layout="wide",
)

col_logo, col_title = st.columns([1, 8])

with col_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=90)

with col_title:
    st.markdown("## CID Reinstall via RTR")
    st.caption("Simple tool untuk uninstall sensor lama lalu install ulang ke Destination CID.")


clients = build_clients()

host_group_service = HostGroupService(clients["host_group"])
inventory_service = InventoryService(clients["hosts"])
put_file_service = PutFileService(clients["rtr_admin"])
cid_rtr_service = CIDReinstallRTRService(
    clients["rtr"],
    clients["rtr_admin"],
    EXPORT_DIR,
)


with st.sidebar:
    st.header("Config")

    host_group_id = st.text_input("Host Group ID")
    destination_cid = st.text_input("Destination CID")

    st.divider()

    workdir = st.text_input(
        "Workdir",
        value=r"C:\ProgramData\CSMigration",
    )

    installer_name = st.text_input(
        "Installer Put File",
        value="WindowsSensor.exe",
    )

    uninstall_tool_name = st.text_input(
        "Uninstall Tool Put File",
        value="CsUninstallTool.exe",
    )

    bat_name = st.text_input(
        "BAT Put File",
        value="migrate_falcon_sensor.bat",
    )

    st.divider()

    batch_size = st.number_input(
        "Batch Size",
        min_value=1,
        max_value=50,
        value=5,
    )

    queue_offline = st.checkbox(
        "Queue Offline Hosts",
        value=False,
    )

    st.divider()

    fetch_btn = st.button("1. Fetch Hosts", use_container_width=True)
    verify_btn = st.button("2. Verify Put Files", use_container_width=True)
    run_btn = st.button("3. Run Selected", use_container_width=True)


if "inventory_df" not in st.session_state:
    st.session_state.inventory_df = None

if "windows_df" not in st.session_state:
    st.session_state.windows_df = None

if "selected_df" not in st.session_state:
    st.session_state.selected_df = None

if "put_verified" not in st.session_state:
    st.session_state.put_verified = False

if "last_result" not in st.session_state:
    st.session_state.last_result = None


def fetch_hosts():
    if not host_group_id.strip():
        st.error("Host Group ID wajib diisi.")
        return

    with st.spinner("Mengambil member Host Group..."):
        aids = host_group_service.list_group_aids(host_group_id.strip())

    if not aids:
        st.warning("Tidak ada host ditemukan dari Host Group ID tersebut.")
        return

    with st.spinner("Mengambil inventory host..."):
        inventory = inventory_service.get_inventory(aids)

    inventory_df = inventory_to_df(inventory)
    windows_df = filter_windows(inventory_df)

    inventory_df.to_csv(
        EXPORT_DIR / f"{host_group_id}_cid_reinstall_inventory.csv",
        index=False,
    )

    windows_df.to_csv(
        EXPORT_DIR / f"{host_group_id}_cid_reinstall_windows.csv",
        index=False,
    )

    st.session_state.inventory_df = inventory_df
    st.session_state.windows_df = windows_df

    st.success(f"Fetch selesai. Total host: {len(inventory_df)} | Windows: {len(windows_df)}")


def verify_put_files():
    names = [installer_name, uninstall_tool_name, bat_name]
    rows = []

    for name in names:
        found = verify_put_file(put_file_service, name.strip())
        rows.append(
            {
                "file": name,
                "status": "FOUND" if found else "NOT FOUND",
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if all(row["status"] == "FOUND" for row in rows):
        st.session_state.put_verified = True
        st.success("Semua Put Files ditemukan.")
    else:
        st.session_state.put_verified = False
        st.error("Ada file yang belum ada di RTR Put Files.")


def run_selected():
    selected_df = st.session_state.selected_df

    if selected_df is None or selected_df.empty:
        st.error("Pilih minimal 1 host.")
        return

    if not destination_cid.strip():
        st.error("Destination CID wajib diisi.")
        return

    if not st.session_state.put_verified:
        st.warning("Klik Verify Put Files dulu.")
        return

    aids = selected_df["aid"].dropna().astype(str).tolist()

    all_results = []
    trace_rows = []

    batches = list(chunk_list(aids, int(batch_size)))
    progress = st.progress(0)

    for index, batch_aids in enumerate(batches, start=1):
        st.info(f"Running batch {index}/{len(batches)} - {len(batch_aids)} host")

        result = cid_rtr_service.run_cid_reinstall_batch(
            host_ids=batch_aids,
            destination_cid=destination_cid.strip(),
            workdir=workdir.strip(),
            installer_name=installer_name.strip(),
            uninstall_tool_name=uninstall_tool_name.strip(),
            bat_name=bat_name.strip(),
            queue_offline=bool(queue_offline),
        )

        all_results.append(
            {
                "batch": index,
                "result": result,
            }
        )

        for step in result.get("steps", []):
            resp = step.get("response") or {}
            per_host = cid_rtr_service.extract_per_host_results(resp)

            if per_host:
                for aid, data in per_host.items():
                    errors = data.get("errors") or []
                    error_code = ""
                    error_message = ""

                    if errors and isinstance(errors, list) and isinstance(errors[0], dict):
                        error_code = errors[0].get("code", "")
                        error_message = errors[0].get("message", "")

                    trace_rows.append(
                        {
                            "batch": index,
                            "step": step.get("step", ""),
                            "aid": aid,
                            "complete": data.get("complete", ""),
                            "offline_queued": data.get("offline_queued", ""),
                            "session_id": data.get("session_id", ""),
                            "task_id": data.get("task_id", ""),
                            "error_code": error_code,
                            "error_message": error_message,
                        }
                    )
            else:
                for aid in batch_aids:
                    trace_rows.append(
                        {
                            "batch": index,
                            "step": step.get("step", ""),
                            "aid": aid,
                            "complete": "",
                            "offline_queued": "",
                            "session_id": "",
                            "task_id": "",
                            "error_code": "" if step.get("status") == "success" else "STEP_FAILED",
                            "error_message": step.get("error", ""),
                        }
                    )

        progress.progress(index / max(len(batches), 1))

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "host_group_id": host_group_id,
        "destination_cid": destination_cid,
        "workdir": workdir,
        "installer_name": installer_name,
        "uninstall_tool_name": uninstall_tool_name,
        "bat_name": bat_name,
        "batch_size": int(batch_size),
        "results": all_results,
    }

    prefix = host_group_id or "cid_reinstall"
    export_paths = cid_rtr_service.export_result(
        prefix=prefix,
        payload=payload,
        trace_rows=trace_rows,
    )

    selected_path = EXPORT_DIR / f"{prefix}_cid_reinstall_selected_hosts.csv"
    selected_df.to_csv(selected_path, index=False)

    st.session_state.last_result = payload

    st.success("Command selesai dikirim. Validasi final tetap cek dari Destination CID.")

    trace_df = pd.DataFrame(trace_rows)

    download_json("Download Response JSON", payload, export_paths["json"].name)
    download_csv("Download Trace CSV", trace_df, export_paths["csv"].name)
    download_csv("Download Selected Hosts CSV", selected_df, selected_path.name)


if fetch_btn:
    fetch_hosts()

if verify_btn:
    verify_put_files()


st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Windows Hosts")

    if st.session_state.windows_df is not None:
        df = st.session_state.windows_df.copy()

        if "selected" not in df.columns:
            df.insert(0, "selected", False)

        edited = st.data_editor(
            df,
            use_container_width=True,
            height=430,
            hide_index=True,
            num_rows="fixed",
        )

        st.session_state.selected_df = edited[edited["selected"] == True].drop(
            columns=["selected"],
            errors="ignore",
        )

        selected_count = 0
        if st.session_state.selected_df is not None:
            selected_count = len(st.session_state.selected_df)

        st.write(f"Total Windows: **{len(df)}**")
        st.write(f"Selected: **{selected_count}**")

        if st.session_state.selected_df is not None and not st.session_state.selected_df.empty:
            download_csv(
                "Download Selected CSV",
                st.session_state.selected_df,
                f"{host_group_id}_cid_reinstall_selected.csv",
            )
    else:
        st.write("Klik **Fetch Hosts** dulu.")


with right:
    st.subheader("Checklist")

    st.markdown(
        """
        **Sebelum run:**

        1. Uninstall protection sudah disable dari policy.
        2. Policy sudah apply ke target host.
        3. Tiga file sudah ada di RTR Put Files:
           - `WindowsSensor.exe`
           - `CsUninstallTool.exe`
           - `migrate_falcon_sensor.bat`
        4. Destination CID sudah benar.
        5. Test 1 host dulu sebelum banyak host.
        """
    )

    st.warning(
        "Setelah sensor lama di-uninstall, RTR bisa putus. "
        "Validasi akhir harus cek host muncul di Destination CID."
    )


if run_btn:
    run_selected()


st.divider()

st.subheader("Last Result")

if st.session_state.last_result:
    st.json(st.session_state.last_result)
else:
    st.write("Belum ada eksekusi.")

st.caption("Powered by Seraphim Digital Technology")
