from typing import Any, Dict, List
from app.utils.common import ensure_success, get_body, quote_if_needed


class RTRService:
    def __init__(self, rtr_client, rtr_admin_client):
        self.rtr_client = rtr_client
        self.rtr_admin_client = rtr_admin_client

    def init_batch(self, aids: List[str], queue_offline: bool) -> str:
        response = self.rtr_client.batch_init_sessions(
            host_ids=aids,
            queue_offline=queue_offline,
        )
        ensure_success(response, "batch_init_sessions")
        return self._extract_batch_id(response)

    def run_put_and_run(
        self,
        batch_id: str,
        candidate_aids: List[str],
        put_name: str,
        install_args: str,
        queue_offline: bool,
    ) -> Dict[str, Any]:
        # Penting: command_string hanya file + argumen, karena base_command sudah put-and-run.
        command_string = f"{quote_if_needed(put_name)} {install_args}".strip()
        response = self.rtr_admin_client.batch_admin_command(
            base_command="put-and-run",
            batch_id=batch_id,
            command_string=command_string,
            optional_hosts=candidate_aids,
            persist_all=queue_offline,
            timeout=600,
            timeout_duration="4m",
            host_timeout_duration="4m",
        )
        ensure_success(response, "batch_admin_command(put-and-run)")
        return response

    @staticmethod
    def _extract_batch_id(response: Dict[str, Any]) -> str:
        body = get_body(response)
        if body.get("batch_id"):
            return body["batch_id"]

        resources = body.get("resources")
        if isinstance(resources, list) and resources:
            first = resources[0]
            if isinstance(first, dict) and first.get("batch_id"):
                return first["batch_id"]

        meta = body.get("meta", {})
        if isinstance(meta, dict) and meta.get("batch_id"):
            return meta["batch_id"]

        raise RuntimeError("batch_id tidak ditemukan pada response batch_init_sessions.")
