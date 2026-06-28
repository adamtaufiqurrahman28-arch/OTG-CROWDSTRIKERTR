from pathlib import Path
from typing import Any, Dict, List
import json
import time
import pandas as pd


class CIDReinstallRTRService:
    """
    Service khusus untuk CID reinstall via RTR.

    Flow per batch:
    1. Init RTR batch session
    2. mkdir workdir
    3. cd workdir
    4. put WindowsSensor.exe
    5. put CsUninstallTool.exe
    6. put migrate_falcon_sensor.bat
    7. run migrate_falcon_sensor.bat <DESTINATION_CID>
    """

    def __init__(self, rtr, rtra, export_dir: Path):
        self.rtr = rtr
        self.rtra = rtra
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def batch_init(self, host_ids: List[str], queue_offline: bool = False) -> str:
        resp = self.rtr.batch_init_sessions(
            host_ids=host_ids,
            queue_offline=queue_offline,
        )

        if resp.get("status_code") not in (200, 201):
            raise RuntimeError(f"batch_init_sessions gagal: {resp.get('body')}")

        body = resp.get("body") or {}

        batch_id = body.get("batch_id")
        if batch_id:
            return batch_id

        resources = body.get("resources")
        if isinstance(resources, list) and resources:
            batch_id = resources[0].get("batch_id")
            if batch_id:
                return batch_id

        raise RuntimeError(f"batch_id tidak ditemukan di response: {body}")

    def run_admin_command(
        self,
        batch_id: str,
        host_ids: List[str],
        base_command: str,
        command_string: str,
        queue_offline: bool = False,
        timeout_seconds: int = 600,
    ) -> Dict[str, Any]:
        resp = self.rtra.batch_admin_command(
            base_command=base_command,
            batch_id=batch_id,
            command_string=command_string,
            optional_hosts=host_ids,
            persist_all=queue_offline,
            timeout=timeout_seconds,
            timeout_duration="5m",
            host_timeout_duration="5m",
        )

        if resp.get("status_code") not in (200, 201):
            raise RuntimeError(
                f"batch_admin_command gagal. "
                f"base_command={base_command}, command_string={command_string}, body={resp.get('body')}"
            )

        return resp

    def mkdir(self, batch_id: str, host_ids: List[str], workdir: str, queue_offline: bool) -> Dict[str, Any]:
        return self.run_admin_command(
            batch_id=batch_id,
            host_ids=host_ids,
            base_command="mkdir",
            command_string=workdir,
            queue_offline=queue_offline,
        )

    def cd(self, batch_id: str, host_ids: List[str], workdir: str, queue_offline: bool) -> Dict[str, Any]:
        return self.run_admin_command(
            batch_id=batch_id,
            host_ids=host_ids,
            base_command="cd",
            command_string=workdir,
            queue_offline=queue_offline,
        )

    def put(self, batch_id: str, host_ids: List[str], put_file_name: str, queue_offline: bool) -> Dict[str, Any]:
        return self.run_admin_command(
            batch_id=batch_id,
            host_ids=host_ids,
            base_command="put",
            command_string=put_file_name,
            queue_offline=queue_offline,
            timeout_seconds=900,
        )

    def run_bat(
        self,
        batch_id: str,
        host_ids: List[str],
        bat_name: str,
        destination_cid: str,
        queue_offline: bool,
    ) -> Dict[str, Any]:
        command = f'{bat_name} "{destination_cid}"'

        return self.run_admin_command(
            batch_id=batch_id,
            host_ids=host_ids,
            base_command="run",
            command_string=command,
            queue_offline=queue_offline,
            timeout_seconds=900,
        )

    @staticmethod
    def extract_per_host_results(resp: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        body = resp.get("body") or {}
        combined = body.get("combined") or {}
        resources = combined.get("resources")

        if isinstance(resources, dict):
            return resources

        return {}

    def run_cid_reinstall_batch(
        self,
        host_ids: List[str],
        destination_cid: str,
        workdir: str,
        installer_name: str,
        uninstall_tool_name: str,
        bat_name: str,
        queue_offline: bool = False,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "host_ids": host_ids,
            "destination_cid": destination_cid,
            "workdir": workdir,
            "steps": [],
        }

        batch_id = self.batch_init(host_ids, queue_offline=queue_offline)
        result["batch_id"] = batch_id

        steps = [
            ("mkdir", lambda: self.mkdir(batch_id, host_ids, workdir, queue_offline)),
            ("cd", lambda: self.cd(batch_id, host_ids, workdir, queue_offline)),
            ("put_installer", lambda: self.put(batch_id, host_ids, installer_name, queue_offline)),
            ("put_uninstall_tool", lambda: self.put(batch_id, host_ids, uninstall_tool_name, queue_offline)),
            ("put_bat", lambda: self.put(batch_id, host_ids, bat_name, queue_offline)),
            ("run_bat", lambda: self.run_bat(batch_id, host_ids, bat_name, destination_cid, queue_offline)),
        ]

        for step_name, action in steps:
            step_result: Dict[str, Any] = {
                "step": step_name,
                "status": "started",
            }

            try:
                resp = action()
                step_result["status"] = "success"
                step_result["response"] = resp
            except Exception as exc:
                step_result["status"] = "failed"
                step_result["error"] = str(exc)
                result["steps"].append(step_result)
                result["status"] = "failed"
                return result

            result["steps"].append(step_result)
            time.sleep(1)

        result["status"] = "success"
        return result

    def export_result(
        self,
        prefix: str,
        payload: Dict[str, Any],
        trace_rows: List[Dict[str, Any]],
    ) -> Dict[str, Path]:
        json_path = self.export_dir / f"{prefix}_cid_reinstall_response.json"
        csv_path = self.export_dir / f"{prefix}_cid_reinstall_trace.csv"

        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        pd.DataFrame(trace_rows).to_csv(csv_path, index=False)

        return {
            "json": json_path,
            "csv": csv_path,
        }
