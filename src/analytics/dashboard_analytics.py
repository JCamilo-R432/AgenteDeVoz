"""
Dashboard Analytics - Metricas especificas para el dashboard web
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any


class DashboardAnalytics:
    """
    Prepara datos para el dashboard de monitoreo en tiempo real.
    Formatea metricas para consumo por el frontend JavaScript.
    """

    def __init__(self, metrics_collector=None, bi_engine=None):
        self._metrics = metrics_collector
        self._bi = bi_engine

    def get_realtime_stats(self) -> Dict[str, Any]:
        """Stats para el panel superior del dashboard (actualizado cada 30s)."""
        if self._metrics:
            counters = self._metrics.get_counters()
            latency = self._metrics.get_latency_stats()
        else:
            counters = {"total_requests": 0, "errors": 0, "active_calls": 0}
            latency = {"p95": 0, "avg": 0}

        return {
            "active_calls": counters.get("active_calls", 0),
            "calls_today": counters.get("calls_today", 0),
            "error_rate": self._calc_error_rate(counters),
            "latency_p95_ms": latency.get("p95", 0),
            "updated_at": datetime.utcnow().isoformat(),
        }

    def get_chart_data(self, chart_type: str, hours: int = 24) -> Dict[str, Any]:
        """
        Datos formateados para graficos del dashboard.

        Args:
            chart_type: "calls_over_time", "intent_distribution", "channel_mix"
            hours: Ventana temporal en horas
        """
        now = datetime.utcnow()

        if chart_type == "calls_over_time":
            # Generar datos de ejemplo para las ultimas N horas
            labels = [
                (now - timedelta(hours=hours - i)).strftime("%H:%M")
                for i in range(0, hours, max(1, hours // 12))
            ]
            values = [max(0, 20 + (i % 7) * 5 - (i % 3) * 2) for i in range(len(labels))]
            return {
                "type": "line",
                "labels": labels,
                "datasets": [{"label": "Llamadas", "data": values, "color": "#4CAF50"}],
            }

        elif chart_type == "intent_distribution":
            return {
                "type": "pie",
                "labels": ["FAQ", "Ticket", "Estado", "Escalacion", "Queja"],
                "datasets": [{"data": [42, 27, 16, 9, 6], "colors": [
                    "#2196F3", "#4CAF50", "#FF9800", "#F44336", "#9C27B0"
                ]}],
            }

        elif chart_type == "channel_mix":
            return {
                "type": "donut",
                "labels": ["Voz", "WhatsApp", "Web"],
                "datasets": [{"data": [55, 33, 12], "colors": ["#2196F3", "#25D366", "#FF5722"]}],
            }

        return {"error": f"chart_type '{chart_type}' no reconocido"}

    def _calc_error_rate(self, counters: Dict) -> float:
        """Calcula tasa de error como porcentaje."""
        total = counters.get("total_requests", 0)
        errors = counters.get("errors", 0)
        if total == 0:
            return 0.0
        return round(errors / total * 100, 2)

    def get_alerts_summary(self) -> List[Dict]:
        """Resumen de alertas activas para el panel de alertas."""
        # En produccion leer de AlertManager API
        return [
            {
                "severity": "warning",
                "message": "Latencia P95 > 2s en los ultimos 10 minutos",
                "timestamp": datetime.utcnow().isoformat(),
                "resolved": False,
            }
        ]
