# AI Coding Assistant Instructions for FALCONBUKRTR

## Project Overview
This is a modular Python application for bulk upgrading CrowdStrike Falcon sensors via Real-Time Response (RTR) using existing installer files in RTR Put Files. It processes host groups, filters Windows hosts below target build, and executes `put-and-run` commands without uploading/downloading files locally.

## Architecture
- **Entry Point**: `main.py` - Thin CLI parser that builds config, initializes FalconPy clients, and calls orchestrator.
- **Orchestrator**: `app/services/orchestrator.py` - Coordinates sequential execution: AID retrieval → inventory → candidate filtering → selection → put-file resolution → RTR batch init → command execution → monitoring.
- **Services**: Each in `app/services/` handles specific responsibilities (e.g., `inventory_service.py` for host data, `rtr_service.py` for RTR operations).
- **Data Flow**: Host Group → AIDs (CSV export) → Inventory (CSV) → Filtered Candidates (CSV) → Selected Hosts → Put-and-Run → Response JSON → Monitor Remaining (CSV).
- **Clients**: `app/clients/falcon.py` - Factory for FalconPy API clients (HostGroup, Hosts, RealTimeResponse, RealTimeResponseAdmin).
- **Models**: `app/models/host.py` - Dataclasses for `HostRecord` and `CandidateRecord` with consistent field naming.
- **Utils**: `app/utils/common.py` - Shared helpers like `ensure_success()` for API validation, `chunked()` for batching (5000 AIDs), `to_build_3()` for version normalization.

## Key Patterns
- **API Error Handling**: Always call `ensure_success(response, "context")` after FalconPy calls to check `status_code` 200-299.
- **Version Comparison**: Normalize to 3-part build using `to_build_3()` before tuple comparison (e.g., `parse_version("7.34.20610.0")` → `(7,34,20610)`).
- **Batching**: Use `chunked(list, 5000)` for API limits; process in batches to avoid timeouts.
- **Data Serialization**: Use `asdict()` on dataclasses for CSV/JSON export; headers match dataclass fields.
- **Command Formatting**: For `put-and-run`, use `base_command="put-and-run"` and `command_string=f"put-and-run {filename} -CommandLine='{args}'"` (no duplicate "put-and-run" in string).
- **File Quoting**: Apply `quote_if_needed()` to filenames/args containing spaces or quotes.
- **Export Naming**: Files prefixed with `{host_group_id}_` (e.g., `a3102b1b645b4b658f787adea003bd2c_inventory.csv`).

## Development Workflow
- **Setup**: `pip install -r requirements.txt`; Set `FALCON_CLIENT_ID` and `FALCON_CLIENT_SECRET` via `.env` or env vars.
- **Testing**: Use `--dry-run` for inventory/candidate validation without RTR execution.
- **Running**: `python main.py --host-group-id <ID> --target-build 7.34.20610 --put-name "FalconSensor.exe" --install-args "/install /quiet /norestart" --monitor`.
- **Debugging**: Check exported CSVs for data flow; JSON responses for RTR errors; use `--poll-seconds 30` for faster monitoring feedback.
- **Adding Features**: Extend services (e.g., new filter in `selection_service.py`); update `AppConfig` dataclass and arg parser; integrate into orchestrator flow.

## Conventions
- **Language**: Indonesian comments and prints for operational context.
- **Imports**: Group by standard library, third-party (falconpy), then local (app.*).
- **Error Messages**: Include context and response body for debugging (e.g., `RuntimeError(f"batch_init_sessions gagal: {resp.get('body')}")`).
- **Path Handling**: Use `pathlib.Path` for exports; ensure `export_dir.mkdir(parents=True, exist_ok=True)`.
- **Online Check**: Use `is_online(last_seen_iso, minutes=10)` for host availability filtering.

## Integration Points
- **FalconPy**: Primary API library; clients initialized once in `FalconClients.from_env()`.
- **RTR Put Files**: Only uses existing files; resolves by name (exact/case-insensitive) or ID.
- **Batch Operations**: RTR sessions batched by host IDs; commands persisted for offline hosts if `--queue-offline`.
- **Monitoring**: Polls inventory post-execution; compares builds to detect upgrades.

Focus on modular service extensions, API response validation, and version/build comparisons when modifying code.