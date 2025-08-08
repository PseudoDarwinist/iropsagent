# Type Definitions for Bag Tracking System

from datetime import datetime
from typing import Optional, Dict, Any, List, Generic, TypeVar, Union
from enum import Enum
from dataclasses import dataclass


# Generic type for API responses
T = TypeVar('T')


# Enum Definitions

class BagStatus(Enum):
    """Bag status throughout its journey."""
    CHECKED_IN = "CHECKED_IN"               # Bag checked in at origin
    IN_TRANSIT = "IN_TRANSIT"               # Bag being transported between locations
    ARRIVED = "ARRIVED"                     # Bag has arrived at destination
    READY_FOR_PICKUP = "READY_FOR_PICKUP"   # Bag is on carousel or in claim area
    PICKED_UP = "PICKED_UP"                 # Bag has been collected by passenger
    DELAYED = "DELAYED"                     # Bag delayed due to missed connection or other issues
    MISHANDLED = "MISHANDLED"               # Bag lost, damaged, or improperly handled
    REROUTED = "REROUTED"                   # Bag rerouted due to flight changes
    PROCESSING = "PROCESSING"               # Bag being processed at a facility
    CONNECTING = "CONNECTING"               # Bag transferring between flights
    LOADED = "LOADED"                       # Bag loaded onto aircraft
    UNLOADED = "UNLOADED"                   # Bag unloaded from aircraft
    SECURITY_HOLD = "SECURITY_HOLD"         # Bag held for security screening
    CUSTOMS_HOLD = "CUSTOMS_HOLD"           # Bag held at customs
    RETURNED = "RETURNED"                   # Bag returned to origin
    UNKNOWN = "UNKNOWN"                     # Status cannot be determined


class AirlineCode(Enum):
    """IATA airline codes for supported airlines."""
    AMERICAN = "AA"
    DELTA = "DL"
    UNITED = "UA"
    LUFTHANSA = "LH"
    BRITISH_AIRWAYS = "BA"
    AIR_FRANCE = "AF"
    KLM = "KL"
    EMIRATES = "EK"
    QATAR = "QR"
    SINGAPORE = "SQ"
    CATHAY_PACIFIC = "CX"
    JAPAN_AIRLINES = "JL"
    ANA = "NH"
    TURKISH = "TK"
    SWISS = "LX"
    AUSTRIAN = "OS"
    SCANDINAVIAN = "SK"
    FINNISH = "AY"
    IBERIA = "IB"
    TAP = "TP"
    UNKNOWN = "XX"


class LocationCode(Enum):
    """IATA airport codes for major airports."""
    # US Airports
    JFK = "JFK"    # New York JFK
    LAX = "LAX"    # Los Angeles
    ORD = "ORD"    # Chicago O'Hare
    DFW = "DFW"    # Dallas/Fort Worth
    DEN = "DEN"    # Denver
    ATL = "ATL"    # Atlanta
    MIA = "MIA"    # Miami
    BOS = "BOS"    # Boston
    SEA = "SEA"    # Seattle
    SFO = "SFO"    # San Francisco
    
    # European Airports
    LHR = "LHR"    # London Heathrow
    CDG = "CDG"    # Paris Charles de Gaulle
    FRA = "FRA"    # Frankfurt
    AMS = "AMS"    # Amsterdam
    ZUR = "ZUR"    # Zurich
    MUC = "MUC"    # Munich
    CPH = "CPH"    # Copenhagen
    ARN = "ARN"    # Stockholm
    HEL = "HEL"    # Helsinki
    VIE = "VIE"    # Vienna
    
    # Asian Airports
    NRT = "NRT"    # Tokyo Narita
    HND = "HND"    # Tokyo Haneda
    ICN = "ICN"    # Seoul Incheon
    SIN = "SIN"    # Singapore
    HKG = "HKG"    # Hong Kong
    PEK = "PEK"    # Beijing Capital
    PVG = "PVG"    # Shanghai Pudong
    BKK = "BKK"    # Bangkok
    KUL = "KUL"    # Kuala Lumpur
    
    # Middle East & Africa
    DXB = "DXB"    # Dubai
    DOH = "DOH"    # Doha
    CAI = "CAI"    # Cairo
    JNB = "JNB"    # Johannesburg
    
    UNKNOWN = "XXX"


class NotificationChannel(Enum):
    """Available notification channels."""
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"
    WEBHOOK = "WEBHOOK"


class NotificationPriority(Enum):
    """Priority levels for notifications."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class APIResponseStatus(Enum):
    """API response status codes."""
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    RATE_LIMITED = "RATE_LIMITED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"


class FacilityType(Enum):
    """Types of facilities where bags can be located."""
    CHECK_IN = "CHECK_IN"
    SECURITY = "SECURITY"
    SORTING = "SORTING"
    LOADING = "LOADING"
    AIRCRAFT = "AIRCRAFT"
    UNLOADING = "UNLOADING"
    CAROUSEL = "CAROUSEL"
    CUSTOMS = "CUSTOMS"
    CLAIM_OFFICE = "CLAIM_OFFICE"
    STORAGE = "STORAGE"
    TRANSFER = "TRANSFER"
    UNKNOWN = "UNKNOWN"


# Data Classes

@dataclass
class BagLocation:
    """Represents a bag's location at a specific point in time."""
    airport_code: LocationCode
    facility_type: FacilityType
    facility_name: str
    timestamp: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    terminal: Optional[str] = None
    gate: Optional[str] = None
    carousel: Optional[str] = None
    notes: Optional[str] = None
    
    def __post_init__(self):
        """Validate location data after initialization."""
        if self.airport_code == LocationCode.UNKNOWN and not self.facility_name:
            raise ValueError("Either airport_code must be known or facility_name must be provided")


@dataclass
class BagTrackingRecord:
    """Complete tracking record for a bag."""
    bag_tag: str
    airline_code: AirlineCode
    current_status: BagStatus
    current_location: BagLocation
    last_updated: datetime
    passenger_name: Optional[str] = None
    flight_number: Optional[str] = None
    origin_airport: Optional[LocationCode] = None
    destination_airport: Optional[LocationCode] = None
    location_history: List[BagLocation] = None
    status_history: List[Dict[str, Any]] = None
    estimated_arrival: Optional[datetime] = None
    is_delayed: bool = False
    delay_reason: Optional[str] = None
    
    def __post_init__(self):
        """Initialize empty lists if not provided."""
        if self.location_history is None:
            self.location_history = []
        if self.status_history is None:
            self.status_history = []


@dataclass
class APIResponse(Generic[T]):
    """Generic API response wrapper."""
    status: APIResponseStatus
    data: Optional[T] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: datetime = None
    request_id: Optional[str] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[datetime] = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    @property
    def is_success(self) -> bool:
        """Check if the response indicates success."""
        return self.status == APIResponseStatus.SUCCESS
    
    @property
    def is_error(self) -> bool:
        """Check if the response indicates an error."""
        return self.status in [
            APIResponseStatus.ERROR,
            APIResponseStatus.NOT_FOUND,
            APIResponseStatus.UNAUTHORIZED,
            APIResponseStatus.TIMEOUT
        ]
    
    @property
    def is_rate_limited(self) -> bool:
        """Check if the response indicates rate limiting."""
        return self.status == APIResponseStatus.RATE_LIMITED


@dataclass
class BagOwner:
    """Information about the bag owner."""
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    loyalty_number: Optional[str] = None
    notification_preferences: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize empty preferences if not provided."""
        if self.notification_preferences is None:
            self.notification_preferences = {}
    
    @property
    def full_name(self) -> str:
        """Get full name of the bag owner."""
        return f"{self.first_name} {self.last_name}"


@dataclass
class BagTrackingEvent:
    """Represents a single bag tracking event."""
    event_id: str
    bag_tag: str
    event_type: str
    timestamp: datetime
    location: BagLocation
    status_before: Optional[BagStatus] = None
    status_after: Optional[BagStatus] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize empty metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}


@dataclass
class NotificationRequest:
    """Request to send a notification."""
    recipient_email: str
    subject: str
    message: str
    channels: List[NotificationChannel]
    priority: NotificationPriority = NotificationPriority.NORMAL
    bag_tag: Optional[str] = None
    flight_number: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    template_data: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize empty template data if not provided."""
        if self.template_data is None:
            self.template_data = {}


@dataclass
class AirlineAPICredentials:
    """Credentials for airline API access."""
    airline_code: AirlineCode
    api_key: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    base_url: Optional[str] = None
    
    @property
    def is_token_expired(self) -> bool:
        """Check if the access token has expired."""
        if self.token_expires_at is None:
            return False
        return datetime.utcnow() >= self.token_expires_at


# Type Aliases

BagTagId = str
FlightNumber = str
PassengerEmail = str
WebhookId = str
NotificationId = str

# Union types for flexible parameter passing
LocationIdentifier = Union[LocationCode, str]
AirlineIdentifier = Union[AirlineCode, str]
StatusUpdate = Dict[str, Union[BagStatus, BagLocation, datetime, str]]

# Complex types for API responses
BagSearchResult = List[BagTrackingRecord]
LocationHistory = List[BagLocation]
NotificationHistory = List[Dict[str, Any]]
RateLimitInfo = Dict[str, Union[int, datetime]]


# Exception types (for reference, actual implementations would be in separate files)

class BagTrackingException(Exception):
    """Base exception for bag tracking operations."""
    pass


class BagNotFoundException(BagTrackingException):
    """Raised when a bag tag is not found."""
    pass


class AirlineAPIException(BagTrackingException):
    """Raised when airline API operations fail."""
    pass


class AuthenticationException(BagTrackingException):
    """Raised when API authentication fails."""
    pass


class APIConnectionException(BagTrackingException):
    """Raised when unable to connect to external APIs."""
    pass


class NotificationException(BagTrackingException):
    """Raised when notification delivery fails."""
    pass


class ValidationException(BagTrackingException):
    """Raised when input validation fails."""
    pass


class LocationUnavailableException(BagTrackingException):
    """Raised when location data is not available."""
    pass


class FlightNotFoundException(BagTrackingException):
    """Raised when a flight is not found."""
    pass


class WebhookRegistrationException(BagTrackingException):
    """Raised when webhook registration fails."""
    pass


class NotificationNotFoundException(BagTrackingException):
    """Raised when a notification is not found."""
    pass


# Utility functions for type conversion and validation

def parse_bag_tag(bag_tag: str) -> str:
    """
    Parse and validate bag tag format.
    
    Args:
        bag_tag: Raw bag tag string
        
    Returns:
        Normalized bag tag
        
    Raises:
        ValidationException: If bag tag format is invalid
    """
    # Remove any spaces and convert to uppercase
    normalized = bag_tag.strip().upper()
    
    # Basic validation - bag tags are typically 10-13 characters
    if not normalized or len(normalized) < 8 or len(normalized) > 15:
        raise ValidationException(f"Invalid bag tag format: {bag_tag}")
    
    return normalized


def parse_airline_code(code: str) -> AirlineCode:
    """
    Parse airline code string to AirlineCode enum.
    
    Args:
        code: Airline code string
        
    Returns:
        AirlineCode enum value
        
    Raises:
        ValidationException: If airline code is not supported
    """
    try:
        return AirlineCode(code.upper())
    except ValueError:
        return AirlineCode.UNKNOWN


def parse_airport_code(code: str) -> LocationCode:
    """
    Parse airport code string to LocationCode enum.
    
    Args:
        code: Airport code string
        
    Returns:
        LocationCode enum value
    """
    try:
        return LocationCode(code.upper())
    except ValueError:
        return LocationCode.UNKNOWN


def is_valid_email(email: str) -> bool:
    """
    Basic email validation.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if email format is valid, False otherwise
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def is_valid_phone(phone: str) -> bool:
    """
    Basic phone number validation.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if phone format is valid, False otherwise
    """
    import re
    # Simple pattern for international phone numbers
    pattern = r'^\+?[\d\s\-\(\)]{10,15}$'
    return bool(re.match(pattern, phone.strip()))