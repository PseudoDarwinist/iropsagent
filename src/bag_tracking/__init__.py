# Bag Tracking Module
# Integrated bag tracking system for IROPS Agent

"""
Bag Tracking Module

This module provides comprehensive bag tracking capabilities for the IROPS Agent system,
allowing passengers to monitor their checked baggage during flight disruptions and 
coordinate rebooking with bag location information.

Components:
- Core interfaces for bag tracking, airline integration, and notifications
- Type definitions for bag statuses, locations, and API responses
- Services for tracking bag movements and managing airline API connections
- API endpoints for bag tracking operations
- Utilities for bag tracking data processing
"""

__version__ = "1.0.0"
__author__ = "IROPS Agent Team"

# Import core interfaces
from .interfaces.bag_tracker import BagTracker
from .interfaces.airline_api_adapter import AirlineAPIAdapter
from .interfaces.notification_manager import NotificationManager

# Import type definitions
from .types import (
    BagStatus,
    BagLocation,
    BagTrackingRecord,
    APIResponse,
    AirlineCode,
    LocationCode
)

__all__ = [
    "BagTracker",
    "AirlineAPIAdapter", 
    "NotificationManager",
    "BagStatus",
    "BagLocation",
    "BagTrackingRecord",
    "APIResponse",
    "AirlineCode",
    "LocationCode"
]