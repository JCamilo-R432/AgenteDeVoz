"""infrastructure - Auto-scaling y CDN para AgenteDeVoz"""
from .auto_scaler import AutoScaler, ScalingMetrics, ScalingDecision, ScaleDirection
from .kubernetes_hpa import KubernetesHPA, HPAConfig
from .cdn_manager import CDNManager, CDNProvider, CacheConfig
from .cloudflare_integration import CloudflareIntegration

__all__ = [
    "AutoScaler", "ScalingMetrics", "ScalingDecision", "ScaleDirection",
    "KubernetesHPA", "HPAConfig",
    "CDNManager", "CDNProvider", "CacheConfig",
    "CloudflareIntegration",
]
