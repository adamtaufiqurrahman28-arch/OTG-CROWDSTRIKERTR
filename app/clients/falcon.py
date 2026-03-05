from dataclasses import dataclass
from falconpy import HostGroup, Hosts, RealTimeResponse, RealTimeResponseAdmin


@dataclass
class FalconClients:
    host_group: HostGroup
    hosts: Hosts
    rtr: RealTimeResponse
    rtr_admin: RealTimeResponseAdmin

    @classmethod
    def from_env(cls, client_id: str, client_secret: str) -> "FalconClients":
        return cls(
            host_group=HostGroup(client_id=client_id, client_secret=client_secret),
            hosts=Hosts(client_id=client_id, client_secret=client_secret),
            rtr=RealTimeResponse(client_id=client_id, client_secret=client_secret),
            rtr_admin=RealTimeResponseAdmin(client_id=client_id, client_secret=client_secret),
        )
