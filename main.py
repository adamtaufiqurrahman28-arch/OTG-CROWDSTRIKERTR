from app.config.settings import AppConfig, build_arg_parser
from app.clients.falcon import FalconClients
from app.services.orchestrator import run_bulk_upgrade


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    config = AppConfig.from_args(args)
    clients = FalconClients.from_env(config.client_id, config.client_secret)
    run_bulk_upgrade(config, clients)


if __name__ == "__main__":
    main()
