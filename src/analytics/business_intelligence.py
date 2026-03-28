"""
Business Intelligence Analytics - AgenteDeVoz
Gap #30: KPIs, segmentacion, tendencias y reportes ejecutivos
"""
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum


class ReportType(Enum):
    EXECUTIVE = "executive"
    OPERATIONAL = "operational"
    TECHNICAL = "technical"


@dataclass
class KPI:
    name: str
    value: float
    unit: str
    target: float
    period: str
    trend: str  # "up", "down", "stable"
    status: str  # "green", "yellow", "red"

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "target": self.target,
            "period": self.period,
            "trend": self.trend,
            "status": self.status,
            "achievement_pct": round((self.value / self.target * 100) if self.target > 0 else 0, 1),
        }


class BusinessIntelligence:
    """
    Motor de Business Intelligence para AgenteDeVoz.
    Calcula KPIs, segmentacion de usuarios y tendencias.
    En produccion conectar a PostgreSQL para datos reales.
    """

    def __init__(self, db_connection=None):
        self._db = db_connection
        self._mock_data = self._generate_mock_data()

    def _generate_mock_data(self) -> Dict:
        """Datos de ejemplo para desarrollo/testing."""
        return {
            "total_calls": 1247,
            "resolved_first_contact": 892,
            "escalated": 287,
            "avg_handle_time_seconds": 245,
            "csat_scores": [4.2, 4.5, 4.8, 4.3, 4.6, 4.7, 4.4, 4.9, 4.5, 4.6],
            "tickets_created": 334,
            "tickets_resolved": 298,
            "channels": {"voice": 680, "whatsapp": 412, "web": 155},
            "intents": {
                "faq": 523,
                "ticket_create": 334,
                "ticket_status": 198,
                "escalate": 287,
                "complaint": 105,
            },
            "daily_calls": [45, 62, 58, 71, 83, 67, 89, 92, 78, 95, 88, 103, 97, 85],
        }

    def get_kpis(self, period_days: int = 7) -> Dict[str, KPI]:
        """
        Calcula KPIs principales del negocio.

        Returns:
            Dict con KPIs: fcr, escalation_rate, aht, csat, ticket_resolution
        """
        d = self._mock_data

        # First Contact Resolution
        fcr_value = (d["resolved_first_contact"] / d["total_calls"] * 100) if d["total_calls"] > 0 else 0
        fcr = KPI(
            name="First Contact Resolution (FCR)",
            value=round(fcr_value, 1),
            unit="%",
            target=70.0,
            period=f"ultimos {period_days} dias",
            trend="up" if fcr_value >= 70 else "down",
            status="green" if fcr_value >= 70 else ("yellow" if fcr_value >= 60 else "red"),
        )

        # Escalation Rate
        esc_rate = (d["escalated"] / d["total_calls"] * 100) if d["total_calls"] > 0 else 0
        escalation = KPI(
            name="Tasa de Escalacion",
            value=round(esc_rate, 1),
            unit="%",
            target=25.0,  # objetivo: <= 25%
            period=f"ultimos {period_days} dias",
            trend="down" if esc_rate <= 25 else "up",
            status="green" if esc_rate <= 25 else ("yellow" if esc_rate <= 35 else "red"),
        )

        # Average Handle Time
        aht_minutes = d["avg_handle_time_seconds"] / 60
        aht = KPI(
            name="Average Handle Time (AHT)",
            value=round(aht_minutes, 1),
            unit="minutos",
            target=5.0,
            period=f"ultimos {period_days} dias",
            trend="down" if aht_minutes <= 5 else "up",
            status="green" if aht_minutes <= 5 else ("yellow" if aht_minutes <= 7 else "red"),
        )

        # CSAT
        scores = d["csat_scores"]
        csat_avg = sum(scores) / len(scores) if scores else 0
        csat = KPI(
            name="Customer Satisfaction (CSAT)",
            value=round(csat_avg, 2),
            unit="/5",
            target=4.5,
            period=f"ultimos {period_days} dias",
            trend="up" if csat_avg >= 4.5 else "stable",
            status="green" if csat_avg >= 4.5 else ("yellow" if csat_avg >= 4.0 else "red"),
        )

        # Ticket Resolution Rate
        ticket_res = (d["tickets_resolved"] / d["tickets_created"] * 100) if d["tickets_created"] > 0 else 0
        ticket_kpi = KPI(
            name="Ticket Resolution Rate",
            value=round(ticket_res, 1),
            unit="%",
            target=85.0,
            period=f"ultimos {period_days} dias",
            trend="up" if ticket_res >= 85 else "stable",
            status="green" if ticket_res >= 85 else ("yellow" if ticket_res >= 70 else "red"),
        )

        return {
            "fcr": fcr,
            "escalation_rate": escalation,
            "aht": aht,
            "csat": csat,
            "ticket_resolution": ticket_kpi,
        }

    def get_user_segmentation(self) -> Dict[str, Any]:
        """Segmentacion de usuarios por canal, intencion y comportamiento."""
        d = self._mock_data
        total = d["total_calls"]

        return {
            "by_channel": {
                channel: {
                    "count": count,
                    "percentage": round(count / total * 100, 1) if total > 0 else 0,
                }
                for channel, count in d["channels"].items()
            },
            "by_intent": {
                intent: {
                    "count": count,
                    "percentage": round(count / total * 100, 1) if total > 0 else 0,
                }
                for intent, count in d["intents"].items()
            },
            "total_interactions": total,
            "period": "ultimos 30 dias",
        }

    def get_trend_analysis(self, metric: str = "calls", days: int = 30) -> Dict[str, Any]:
        """
        Analisis de tendencias para una metrica.

        Args:
            metric: "calls", "csat", "escalation"
            days: Numero de dias a analizar
        """
        daily_data = self._mock_data["daily_calls"][-min(days, len(self._mock_data["daily_calls"])):]

        if not daily_data:
            return {"error": "No hay datos disponibles"}

        avg = sum(daily_data) / len(daily_data)
        trend_direction = "estable"

        # Calcular tendencia simple: comparar primera mitad vs segunda mitad
        mid = len(daily_data) // 2
        if mid > 0:
            first_half_avg = sum(daily_data[:mid]) / mid
            second_half_avg = sum(daily_data[mid:]) / len(daily_data[mid:])
            pct_change = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0
            if pct_change > 5:
                trend_direction = "creciente"
            elif pct_change < -5:
                trend_direction = "decreciente"
        else:
            pct_change = 0

        return {
            "metric": metric,
            "period_days": len(daily_data),
            "data_points": daily_data,
            "average": round(avg, 2),
            "min": min(daily_data),
            "max": max(daily_data),
            "trend": trend_direction,
            "trend_pct": round(pct_change, 1),
            "generated_at": datetime.utcnow().isoformat(),
        }

    def generate_report(self, report_type: str = "executive") -> Dict[str, Any]:
        """
        Genera un reporte completo segun el tipo solicitado.

        Args:
            report_type: "executive", "operational", "technical"
        """
        kpis = self.get_kpis()
        segmentation = self.get_user_segmentation()
        trend = self.get_trend_analysis()

        base = {
            "report_type": report_type,
            "generated_at": datetime.utcnow().isoformat(),
            "period": "ultimos 7 dias",
        }

        if report_type == "executive":
            # Resumen ejecutivo: KPIs clave y ROI
            kpi_summary = {k: v.to_dict() for k, v in kpis.items()}
            green_kpis = sum(1 for kpi in kpis.values() if kpi.status == "green")
            return {
                **base,
                "headline": f"{green_kpis}/{len(kpis)} KPIs en objetivo",
                "kpis": kpi_summary,
                "trend": trend,
                "key_insights": self._generate_insights(kpis),
            }

        elif report_type == "operational":
            # Reporte operacional: detalle de segmentacion y canales
            return {
                **base,
                "kpis": {k: v.to_dict() for k, v in kpis.items()},
                "segmentation": segmentation,
                "trend": trend,
            }

        else:  # technical
            # Reporte tecnico: todas las metricas
            return {
                **base,
                "kpis": {k: v.to_dict() for k, v in kpis.items()},
                "segmentation": segmentation,
                "trends": {
                    "calls": self.get_trend_analysis("calls", 14),
                },
                "raw_data": self._mock_data,
            }

    def _generate_insights(self, kpis: Dict[str, KPI]) -> List[str]:
        """Genera insights automaticos basados en KPIs."""
        insights = []
        fcr = kpis.get("fcr")
        if fcr and fcr.status == "green":
            insights.append(f"FCR del {fcr.value}% supera el objetivo del {fcr.target}%")
        elif fcr and fcr.status == "red":
            insights.append(f"ATENCION: FCR del {fcr.value}% esta por debajo del objetivo")

        csat = kpis.get("csat")
        if csat and csat.value >= 4.5:
            insights.append(f"CSAT excelente: {csat.value}/5")

        esc = kpis.get("escalation_rate")
        if esc and esc.value > 25:
            insights.append(f"Tasa de escalacion alta ({esc.value}%) - revisar flujos de atencion")

        return insights

    def export_report(self, format: str = "json") -> str:
        """Exporta el reporte ejecutivo en el formato especificado."""
        report = self.generate_report("executive")
        if format == "json":
            return json.dumps(report, indent=2, ensure_ascii=False, default=str)
        elif format == "csv":
            lines = ["KPI,Valor,Unidad,Objetivo,Estado"]
            for key, kpi_data in report.get("kpis", {}).items():
                lines.append(
                    f"{kpi_data['name']},{kpi_data['value']},{kpi_data['unit']},"
                    f"{kpi_data['target']},{kpi_data['status']}"
                )
            return "\n".join(lines)
        return json.dumps(report, default=str)
