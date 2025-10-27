import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class Frontend:
    name: str
    bind_host: str
    bind_port: int
    mode: str
    backend: str

@dataclass
class BackendServer:
    name: str
    host: str
    port: int

@dataclass
class Backend:
    name: str
    servers: List[BackendServer] = field(default_factory=list)

@dataclass
class GlobalConfig:
    log_level: str = "info"
    use_uvloop: bool = True
    timeout: int = 300
    max_connections: int = 100

@dataclass
class ProxyConfig:
    global_cfg: GlobalConfig
    frontends: List[Frontend]
    backends: Dict[str, Backend]

def parse_conf(file_path: str = "proxy.conf") -> ProxyConfig:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file '{file_path}' not found")

    raw_lines = [l.rstrip() for l in path.read_text().splitlines() if l.strip() and not l.strip().startswith("#")]

    global_cfg = GlobalConfig()
    frontends: List[Frontend] = []
    backends: Dict[str, Backend] = {}
    current_section = None
    current_name = None
    section_data = {}
    section_lines: List[str] = []

    def flush_section():
        nonlocal current_section, current_name, section_data, section_lines
        if current_section == "frontend":
            if "bind" not in section_data or "default_backend" not in section_data:
                return
            frontends.append(Frontend(
                name=current_name,
                bind_host=section_data["bind"].split(":")[0],
                bind_port=int(section_data["bind"].split(":")[1]),
                mode=section_data.get("mode", "tcp"),
                backend=section_data.get("default_backend"),
            ))
        elif current_section == "backend":
            servers: List[BackendServer] = []
            for line in section_lines:
                line_clean = line.lstrip()
                if line_clean.startswith("server "):
                    parts = line_clean.split()
                    if len(parts) < 3:
                        continue
                    name = parts[1]
                    host, port = parts[2].split(":")
                    servers.append(BackendServer(name=name, host=host, port=int(port)))
            backends[current_name] = Backend(name=current_name, servers=servers)

        section_data = {}
        section_lines = []

    for line in raw_lines:
        if line.startswith(("global", "defaults", "frontend", "backend")):
            if current_section:
                flush_section()
            parts = line.split()
            current_section = parts[0]
            current_name = parts[1] if len(parts) > 1 else None
        else:
            if current_section in ("global", "defaults"):
                key, *values = line.split()
                value = " ".join(values)
                if key == "log-level":
                    global_cfg.log_level = value
                elif key == "use-uvloop":
                    global_cfg.use_uvloop = value.lower() == "true"
                elif key == "timeout":
                    global_cfg.timeout = int(value)
                elif key == "max-connections":
                    global_cfg.max_connections = int(value)
            elif current_section == "frontend":
                key, *values = line.split()
                section_data[key] = " ".join(values)
            elif current_section == "backend":
                section_lines.append(line)

    if current_section:
        flush_section()

    return ProxyConfig(global_cfg=global_cfg, frontends=frontends, backends=backends)
