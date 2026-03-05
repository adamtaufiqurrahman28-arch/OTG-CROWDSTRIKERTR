from dataclasses import dataclass


@dataclass
class HostRecord:
    aid: str
    hostname: str
    platform_name: str
    agent_version: str
    status: str
    last_seen: str


@dataclass
class CandidateRecord:
    aid: str
    hostname: str
    current_version: str
    current_build: str
    target_build: str
