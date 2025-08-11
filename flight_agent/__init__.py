# IROPS Agent Package
# Import root_agent only when specifically needed to avoid dependency issues

# Core services
from .services.flight_monitoring_service import FlightMonitoringService, run_monitoring_service

__all__ = ["FlightMonitoringService", "run_monitoring_service"]