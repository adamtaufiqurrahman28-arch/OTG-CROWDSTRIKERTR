import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppConfig:
    host_group_id: str
    target_build: str
    put_name: str | None
    put_file_id: str | None
    install_args: str
    queue_offline: bool
    monitor: bool
    poll_seconds: int
    max_polls: int
    dry_run: bool
    export_dir: Path
    client_id: str
    client_secret: str

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "AppConfig":
        client_id = os.getenv("FALCON_CLIENT_ID", "")
        client_secret = os.getenv("FALCON_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise RuntimeError("Set FALCON_CLIENT_ID dan FALCON_CLIENT_SECRET dulu (bisa lewat .env atau env var).")

        export_dir = Path(args.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        if not args.put_name and not args.put_file_id:
            raise RuntimeError("Isi salah satu: --put-name atau --put-file-id")

        return cls(
            host_group_id=args.host_group_id,
            target_build=args.target_build,
            put_name=args.put_name,
            put_file_id=args.put_file_id,
            install_args=args.install_args,
            queue_offline=args.queue_offline,
            monitor=args.monitor,
            poll_seconds=args.poll_seconds,
            max_polls=args.max_polls,
            dry_run=args.dry_run,
            export_dir=export_dir,
            client_id=client_id,
            client_secret=client_secret,
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bulk upgrade CrowdStrike sensor via RTR using existing Put Files"
    )
    parser.add_argument("--host-group-id", required=True, help="Host Group ID")
    parser.add_argument("--target-build", required=True, help="Target build 3-part / 4-part, contoh: 7.34.20610 atau 7.34.20610.0")
    parser.add_argument("--put-name", help="Nama file pada tab RTR Put Files")
    parser.add_argument("--put-file-id", help="ID put file RTR (lebih presisi)")
    parser.add_argument("--install-args", default="/install /quiet /norestart", help="Argumen installer")
    parser.add_argument("--queue-offline", action="store_true", help="Queue untuk host offline")
    parser.add_argument("--monitor", action="store_true", help="Polling versi setelah command dikirim")
    parser.add_argument("--poll-seconds", type=int, default=180, help="Interval polling (detik)")
    parser.add_argument("--max-polls", type=int, default=10, help="Jumlah polling maksimum")
    parser.add_argument("--dry-run", action="store_true", help="Hanya inventory + candidate, tanpa RTR execute")
    parser.add_argument("--export-dir", default="./exports", help="Folder output CSV/JSON")
    return parser
