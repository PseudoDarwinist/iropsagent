# Bag Tracking Core Interfaces
# Abstract base classes defining the bag tracking system contracts

from .bag_tracker import BagTracker
from .airline_api_adapter import AirlineAPIAdapter
from .notification_manager import NotificationManager

__all__ = ["BagTracker", "AirlineAPIAdapter", "NotificationManager"]