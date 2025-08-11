"""
Flight Data Provider interfaces and implementations.

This module provides:
- FlightDataProvider interface for external APIs
- Mock provider for testing and development
- Failover logic between primary and secondary sources

Implements:
- REQ-7.1: Flight Data Provider Interface
- REQ-7.2: Failover Logic Implementation
"""

from .interfaces import FlightDataProvider, ProviderStatus, FlightStatusData
from .flightaware_provider import FlightAwareProvider
from .mock_provider import MockFlightDataProvider
from .failover_manager import FailoverManager, FailoverConfig

__all__ = [
    'FlightDataProvider',
    'ProviderStatus',
    'FlightStatusData',
    'FlightAwareProvider',
    'MockFlightDataProvider',
    'FailoverManager',
    'FailoverConfig'
]