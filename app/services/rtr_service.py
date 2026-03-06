# app/services/rtr_service.py
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.utils.common import quote_if_needed


class RTRService:
    def __init__(self, rtr, rtra, export_dir: Path):
        self.rtr = rtr
        self.rtra = rtra
        self.export_dir = export_dir

    def batch_init(self, host_ids: List[str], queue_offline: bool) -> str:
        resp = self.rtr.batch_init_sessions(host_ids=host_ids, queue_offline=queue_offline)
        if resp.get("status_code") not in (200, 201):
            raise RuntimeError(f"batch_init_sessions gagal: {resp.get('body')}")
        body = resp.get("body") or {}
        # falconpy bisa beda format, jadi cari paling aman
        batch_id = body.get("batch_id")
        if not batch_id:
            res = body.get("resources")
            if isinstance(res, list) and res and isinstance(res[0], dict):
                batch_id = res[0].get("batch_id")
        if not batch_id:
            raise RuntimeError(f"batch_id tidak ditemukan di response: {body}")
        return batch_id

    def resolve_putfile_by_name(self, put_name: str) -> Dict[str, Any]:
        # 1) list id by filter
        lookup = self.rtra.list_put_files(filter=f"name:'{put_name}'", limit=100)
        if lookup.get("status_code") != 200:
            raise RuntimeError(f"list_put_files gagal: {lookup.get('body')}")
        ids = (lookup.get("body") or {}).get("resources") or []
        if not ids:
            raise RuntimeError(f"Put-file '{put_name}' tidak ditemukan di RTR Put Files.")
        # 2) get metadata
        meta = self.rtra.get_put_files_v2(ids=ids[:100])
        if meta.get("status_code") != 200:
            raise RuntimeError(f"get_put_files_v2 gagal: {meta.get('body')}")
        candidates = (meta.get("body") or {}).get("resources") or []
        # exact match
        for x in candidates:
            if (x.get("name") or "") == put_name:
                return x
        # fallback case-insensitive
        for x in candidates:
            if (x.get("name") or "").lower() == put_name.lower():
                return x
        raise RuntimeError(f"Put-file '{put_name}' tidak ditemukan (setelah metadata).")

    def put_and_run(
        self,
        batch_id: str,
        host_ids: List[str],
        put_name: str,
        install_args: str,
        queue_offline: bool,
        timeout_seconds: int = 600,
    ) -> Dict[str, Any]:
        """
        FIX UTAMA:
        - base_command = "put-and-run"
        - command_string = '<putfile> -CommandLine="<args>"'
          (JANGAN diawali "put-and-run" lagi)
        """
        safe_put = quote_if_needed(put_name)
        safe_args = (install_args or "").replace('"', '\\"')

        # kalau args kosong, kirim file saja
      
        if install_args:
            cmd = f"put-and-run {put_name} -CommandLine='{install_args}'"
        else:
            cmd = f"put-and-run {put_name}"

        resp = self.rtra.batch_admin_command(
            base_command="put-and-run",
            batch_id=batch_id,
            command_string=cmd,
            optional_hosts=host_ids,
            persist_all=queue_offline,
            timeout=timeout_seconds,
            timeout_duration="4m",
            host_timeout_duration="4m"
        )

        if resp.get("status_code") not in (200, 201):
            raise RuntimeError(f"batch_admin_command gagal: {resp.get('body')}")

        return resp

    @staticmethod
    def extract_per_host_results(resp: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Support 2 format:
        - body.combined.resources[aid] = {...}
        - body.resources (lebih sederhana)
        """
        body = resp.get("body") or {}
        combined = body.get("combined", {})
        if isinstance(combined, dict):
            resources = combined.get("resources")
            if isinstance(resources, dict):
                return resources

        # fallback: kalau tidak ada combined, return kosong
        return {}

    def save_json(self, filename: str, payload: Dict[str, Any]) -> Path:
        p = self.export_dir / filename
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return p

    def export_trace_csv(self, filename: str, per_host: Dict[str, Dict[str, Any]]) -> Path:
        import csv
        p = self.export_dir / filename
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["aid", "complete", "offline_queued", "session_id", "error_code", "error_message", "stdout", "stderr"])
            for aid, data in per_host.items():
                errs = data.get("errors") or []
                code = ""
                msg = ""
                if errs and isinstance(errs, list) and isinstance(errs[0], dict):
                    code = errs[0].get("code", "")
                    msg = errs[0].get("message", "")
                w.writerow([
                    aid,
                    data.get("complete", ""),
                    data.get("offline_queued", ""),
                    data.get("session_id", ""),
                    code,
                    msg,
                    (data.get("stdout") or "")[:2000],
                    (data.get("stderr") or "")[:2000],
                ])
        return p