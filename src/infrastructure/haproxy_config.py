"""
HAProxy Config - AgenteDeVoz
Gap #13: Generacion de configuracion HAProxy

Genera haproxy.cfg con frontends, backends, health checks y stats.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HAProxyServer:
    name: str
    host: str
    port: int
    weight: int = 1
    check: bool = True
    check_interval_ms: int = 2000
    rise: int = 2           # checks OK antes de marcar UP
    fall: int = 3           # checks KO antes de marcar DOWN
    maxconn: int = 1000


@dataclass
class HAProxyBackendConfig:
    name: str
    balance: str = "roundrobin"   # roundrobin | leastconn | source | uri
    servers: List[HAProxyServer] = field(default_factory=list)
    timeout_connect: str = "5s"
    timeout_server: str = "30s"
    option_httpchk: Optional[str] = "GET /health"
    retries: int = 3


@dataclass
class HAProxyFrontendConfig:
    name: str
    bind_address: str = "*"
    bind_port: int = 80
    default_backend: str = "agentevoz_backend"
    mode: str = "http"
    timeout_client: str = "30s"
    acls: List[str] = field(default_factory=list)
    use_backends: List[str] = field(default_factory=list)


class HAProxyConfigGenerator:
    """
    Genera configuracion HAProxy para AgenteDeVoz.
    Soporta HTTP y TCP modes con health checks y SSL termination.
    """

    def __init__(self):
        self._frontends: List[HAProxyFrontendConfig] = []
        self._backends: List[HAProxyBackendConfig] = []
        logger.info("HAProxyConfigGenerator inicializado")

    def add_frontend(self, frontend: HAProxyFrontendConfig) -> None:
        self._frontends.append(frontend)

    def add_backend(self, backend: HAProxyBackendConfig) -> None:
        self._backends.append(backend)

    def generate_config(
        self,
        stats_port: int = 8404,
        stats_uri: str = "/stats",
        stats_user: str = "admin",
        stats_password: str = "CHANGE_ME",
    ) -> str:
        """Genera el archivo haproxy.cfg completo."""
        sections = [
            self._global_section(),
            self._defaults_section(),
            self._stats_section(stats_port, stats_uri, stats_user, stats_password),
        ]
        for frontend in self._frontends:
            sections.append(self._frontend_section(frontend))
        for backend in self._backends:
            sections.append(self._backend_section(backend))

        return "\n\n".join(sections)

    def _global_section(self) -> str:
        return """global
    log /dev/log local0
    log /dev/log local1 notice
    chroot /var/lib/haproxy
    stats socket /run/haproxy/admin.sock mode 660 level admin expose-fd listeners
    stats timeout 30s
    user haproxy
    group haproxy
    daemon

    # TLS defaults
    ssl-default-bind-ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    ssl-default-bind-ciphersuites TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384
    ssl-default-bind-options ssl-min-ver TLSv1.2 no-tls-tickets"""

    def _defaults_section(self) -> str:
        return """defaults
    log     global
    mode    http
    option  httplog
    option  dontlognull
    timeout connect 5s
    timeout client  30s
    timeout server  30s
    errorfile 400 /etc/haproxy/errors/400.http
    errorfile 403 /etc/haproxy/errors/403.http
    errorfile 408 /etc/haproxy/errors/408.http
    errorfile 500 /etc/haproxy/errors/500.http
    errorfile 502 /etc/haproxy/errors/502.http
    errorfile 503 /etc/haproxy/errors/503.http
    errorfile 504 /etc/haproxy/errors/504.http"""

    def _stats_section(self, port: int, uri: str, user: str, password: str) -> str:
        return f"""frontend stats
    bind *:{port}
    mode http
    stats enable
    stats uri {uri}
    stats refresh 10s
    stats show-node
    stats show-legends
    stats auth {user}:{password}
    stats admin if TRUE"""

    def _frontend_section(self, cfg: HAProxyFrontendConfig) -> str:
        lines = [
            f"frontend {cfg.name}",
            f"    bind {cfg.bind_address}:{cfg.bind_port}",
            f"    mode {cfg.mode}",
            f"    timeout client {cfg.timeout_client}",
            "    option forwardfor",
            "    option http-server-close",
        ]
        for acl in cfg.acls:
            lines.append(f"    acl {acl}")
        for ub in cfg.use_backends:
            lines.append(f"    use_backend {ub}")
        lines.append(f"    default_backend {cfg.default_backend}")
        return "\n".join(lines)

    def _backend_section(self, cfg: HAProxyBackendConfig) -> str:
        lines = [
            f"backend {cfg.name}",
            f"    balance {cfg.balance}",
            f"    timeout connect {cfg.timeout_connect}",
            f"    timeout server {cfg.timeout_server}",
            f"    retries {cfg.retries}",
        ]
        if cfg.option_httpchk:
            lines.append(f"    option httpchk {cfg.option_httpchk}")
            lines.append("    http-check expect status 200")

        for srv in cfg.servers:
            check_opts = ""
            if srv.check:
                check_opts = (
                    f" check inter {srv.check_interval_ms}ms"
                    f" rise {srv.rise} fall {srv.fall}"
                )
            lines.append(
                f"    server {srv.name} {srv.host}:{srv.port}"
                f" weight {srv.weight}"
                f" maxconn {srv.maxconn}"
                f"{check_opts}"
            )
        return "\n".join(lines)

    def generate_default_config(
        self,
        api_servers: List[Dict],
        api_port: int = 8000,
        lb_port: int = 80,
    ) -> str:
        """Genera configuracion por defecto para AgenteDeVoz."""
        backend = HAProxyBackendConfig(
            name="agentevoz_backend",
            balance="leastconn",
            servers=[
                HAProxyServer(
                    name=f"api{i+1}",
                    host=srv["host"],
                    port=srv.get("port", api_port),
                    weight=srv.get("weight", 1),
                )
                for i, srv in enumerate(api_servers)
            ],
            option_httpchk="GET /health",
        )
        frontend = HAProxyFrontendConfig(
            name="agentevoz_frontend",
            bind_port=lb_port,
            default_backend="agentevoz_backend",
        )
        self.add_frontend(frontend)
        self.add_backend(backend)
        return self.generate_config()
