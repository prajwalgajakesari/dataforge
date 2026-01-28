"""
Semantic type inference engine.

This module infers semantic types for columns using multiple signals:
- Column name patterns (e.g., "email", "phone", "_id")
- Database data types (e.g., UUID, TIMESTAMP)
- Detected patterns from values (e.g., email regex match)
- Statistical properties (e.g., uniqueness, cardinality)

The engine combines these signals with configurable weights to produce
confidence-scored type inferences with alternative suggestions.

Example:
    >>> from core.analysis.type_inference import TypeInferenceEngine
    >>> from core.models.analysis import ColumnStatistics
    >>>
    >>> engine = TypeInferenceEngine()
    >>> result = engine.infer_type(
    ...     column_name="customer_email",
    ...     data_type="varchar",
    ...     statistics=stats,
    ... )
    >>> print(result.inferred_type)  # SemanticType.EMAIL
    >>> print(result.confidence_score)  # 0.85
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from core.models.types import (
    SemanticType,
    SemanticCategory,
    PII_TYPES,
    SENSITIVE_TYPES,
    get_category,
)
from core.models.analysis import (
    PatternType,
    PatternMatch,
    ColumnStatistics,
    ConfidenceLevel,
)
from core.analysis.pattern_detector import PatternDetector


# =============================================================================
# Data Classes for Inference Results
# =============================================================================


@dataclass
class TypeSignal:
    """
    A signal contributing to type inference.

    Each signal represents evidence from a specific source (name pattern,
    data type, value pattern, or statistics) pointing to a semantic type.

    Attributes:
        source: Origin of the signal ("name", "data_type", "pattern", "statistics")
        semantic_type: The semantic type suggested by this signal
        confidence: Confidence score from 0.0 to 1.0
        reason: Human-readable explanation for this signal
    """

    source: str
    semantic_type: SemanticType
    confidence: float
    reason: str

    def __post_init__(self) -> None:
        """Validate confidence is within bounds."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class TypeInferenceResult:
    """
    Result of semantic type inference for a column.

    Contains the inferred type, confidence metrics, contributing signals,
    and alternative type suggestions.

    Attributes:
        column_name: Name of the analyzed column
        inferred_type: The primary inferred semantic type
        confidence: Qualitative confidence level (HIGH, MEDIUM, LOW)
        confidence_score: Numeric confidence from 0.0 to 1.0
        category: Semantic category of the inferred type
        signals: List of signals that contributed to the inference
        alternative_types: Other possible types with their scores
        is_pii: Whether the inferred type represents PII data
        is_sensitive: Whether the inferred type represents sensitive data
    """

    column_name: str
    inferred_type: SemanticType
    confidence: ConfidenceLevel
    confidence_score: float
    category: SemanticCategory
    signals: List[TypeSignal] = field(default_factory=list)
    alternative_types: List[Tuple[SemanticType, float]] = field(default_factory=list)

    @property
    def is_pii(self) -> bool:
        """Check if the inferred type represents PII."""
        return self.inferred_type in PII_TYPES

    @property
    def is_sensitive(self) -> bool:
        """Check if the inferred type represents sensitive data."""
        return self.inferred_type in SENSITIVE_TYPES

    def get_signals_by_source(self, source: str) -> List[TypeSignal]:
        """Get all signals from a specific source."""
        return [s for s in self.signals if s.source == source]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "column_name": self.column_name,
            "inferred_type": self.inferred_type.value,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence_score,
            "category": self.category.value,
            "is_pii": self.is_pii,
            "is_sensitive": self.is_sensitive,
            "signals": [
                {
                    "source": s.source,
                    "semantic_type": s.semantic_type.value,
                    "confidence": s.confidence,
                    "reason": s.reason,
                }
                for s in self.signals
            ],
            "alternative_types": [
                {"type": t.value, "score": s}
                for t, s in self.alternative_types
            ],
        }


# =============================================================================
# Mapping Definitions
# =============================================================================


# Name pattern mappings: column name substring -> (semantic type, confidence)
NAME_PATTERNS: Dict[str, Tuple[SemanticType, float]] = {
    # Identifiers
    "_id": (SemanticType.FOREIGN_KEY, 0.8),
    "id": (SemanticType.PRIMARY_KEY, 0.7),
    "_key": (SemanticType.FOREIGN_KEY, 0.8),
    "_fk": (SemanticType.FOREIGN_KEY, 0.9),
    "_pk": (SemanticType.PRIMARY_KEY, 0.9),
    "uuid": (SemanticType.UUID, 0.9),
    "guid": (SemanticType.UUID, 0.9),
    "slug": (SemanticType.SLUG, 0.85),
    "sku": (SemanticType.SKU, 0.9),

    # Personal Information
    "email": (SemanticType.EMAIL, 0.95),
    "e_mail": (SemanticType.EMAIL, 0.95),
    "phone": (SemanticType.PHONE, 0.9),
    "telephone": (SemanticType.PHONE, 0.9),
    "mobile": (SemanticType.PHONE, 0.85),
    "fax": (SemanticType.PHONE, 0.8),
    "first_name": (SemanticType.FIRST_NAME, 0.95),
    "firstname": (SemanticType.FIRST_NAME, 0.95),
    "fname": (SemanticType.FIRST_NAME, 0.9),
    "given_name": (SemanticType.FIRST_NAME, 0.9),
    "last_name": (SemanticType.LAST_NAME, 0.95),
    "lastname": (SemanticType.LAST_NAME, 0.95),
    "lname": (SemanticType.LAST_NAME, 0.9),
    "surname": (SemanticType.LAST_NAME, 0.9),
    "family_name": (SemanticType.LAST_NAME, 0.9),
    "full_name": (SemanticType.FULL_NAME, 0.9),
    "fullname": (SemanticType.FULL_NAME, 0.9),
    "display_name": (SemanticType.FULL_NAME, 0.85),
    "name": (SemanticType.NAME, 0.7),
    "username": (SemanticType.USERNAME, 0.9),
    "user_name": (SemanticType.USERNAME, 0.9),
    "login": (SemanticType.USERNAME, 0.85),
    "password": (SemanticType.PASSWORD_HASH, 0.8),
    "passwd": (SemanticType.PASSWORD_HASH, 0.8),
    "pass_hash": (SemanticType.PASSWORD_HASH, 0.9),
    "ssn": (SemanticType.SSN, 0.95),
    "social_security": (SemanticType.SSN, 0.95),
    "dob": (SemanticType.DATE_OF_BIRTH, 0.9),
    "birth_date": (SemanticType.DATE_OF_BIRTH, 0.9),
    "date_of_birth": (SemanticType.DATE_OF_BIRTH, 0.95),
    "birthday": (SemanticType.DATE_OF_BIRTH, 0.85),
    "age": (SemanticType.AGE, 0.85),
    "gender": (SemanticType.GENDER, 0.9),
    "sex": (SemanticType.GENDER, 0.85),

    # Temporal
    "created_at": (SemanticType.CREATED_AT, 0.95),
    "createdat": (SemanticType.CREATED_AT, 0.95),
    "created": (SemanticType.CREATED_AT, 0.8),
    "date_created": (SemanticType.CREATED_AT, 0.9),
    "insert_date": (SemanticType.CREATED_AT, 0.85),
    "updated_at": (SemanticType.UPDATED_AT, 0.95),
    "updatedat": (SemanticType.UPDATED_AT, 0.95),
    "modified_at": (SemanticType.UPDATED_AT, 0.9),
    "modified": (SemanticType.UPDATED_AT, 0.8),
    "last_modified": (SemanticType.UPDATED_AT, 0.9),
    "deleted_at": (SemanticType.DELETED_AT, 0.95),
    "deletedat": (SemanticType.DELETED_AT, 0.95),
    "removed_at": (SemanticType.DELETED_AT, 0.9),
    "expired_at": (SemanticType.EXPIRED_AT, 0.9),
    "expires": (SemanticType.EXPIRED_AT, 0.85),
    "valid_until": (SemanticType.EXPIRED_AT, 0.85),
    "start_date": (SemanticType.START_DATE, 0.9),
    "end_date": (SemanticType.END_DATE, 0.9),
    "date": (SemanticType.DATE, 0.7),
    "datetime": (SemanticType.DATETIME, 0.8),
    "timestamp": (SemanticType.TIMESTAMP, 0.85),
    "time": (SemanticType.TIME, 0.7),
    "year": (SemanticType.YEAR, 0.8),
    "month": (SemanticType.MONTH, 0.8),
    "day": (SemanticType.DAY, 0.75),
    "duration": (SemanticType.DURATION, 0.85),
    "timezone": (SemanticType.TIMEZONE, 0.9),

    # Financial
    "price": (SemanticType.PRICE, 0.9),
    "cost": (SemanticType.COST, 0.85),
    "amount": (SemanticType.AMOUNT, 0.85),
    "total": (SemanticType.TOTAL, 0.8),
    "subtotal": (SemanticType.AMOUNT, 0.85),
    "grand_total": (SemanticType.TOTAL, 0.9),
    "quantity": (SemanticType.QUANTITY, 0.9),
    "qty": (SemanticType.QUANTITY, 0.9),
    "count": (SemanticType.COUNT, 0.8),
    "currency": (SemanticType.CURRENCY, 0.9),
    "currency_code": (SemanticType.CURRENCY_CODE, 0.95),
    "ccy": (SemanticType.CURRENCY_CODE, 0.85),
    "credit_card": (SemanticType.CREDIT_CARD, 0.95),
    "card_number": (SemanticType.CREDIT_CARD, 0.9),
    "cc_number": (SemanticType.CREDIT_CARD, 0.9),
    "tax": (SemanticType.TAX, 0.85),
    "vat": (SemanticType.TAX, 0.85),
    "discount": (SemanticType.DISCOUNT, 0.85),
    "revenue": (SemanticType.REVENUE, 0.85),
    "profit": (SemanticType.PROFIT, 0.85),
    "percent": (SemanticType.PERCENTAGE, 0.85),
    "percentage": (SemanticType.PERCENTAGE, 0.9),
    "rate": (SemanticType.RATE, 0.8),

    # Geographic
    "address": (SemanticType.ADDRESS, 0.85),
    "street": (SemanticType.STREET, 0.8),
    "street_address": (SemanticType.ADDRESS, 0.9),
    "address_line_1": (SemanticType.ADDRESS_LINE_1, 0.95),
    "address_line_2": (SemanticType.ADDRESS_LINE_2, 0.95),
    "addr_1": (SemanticType.ADDRESS_LINE_1, 0.9),
    "addr_2": (SemanticType.ADDRESS_LINE_2, 0.9),
    "city": (SemanticType.CITY, 0.9),
    "town": (SemanticType.CITY, 0.85),
    "state": (SemanticType.STATE, 0.85),
    "province": (SemanticType.PROVINCE, 0.85),
    "region": (SemanticType.REGION, 0.8),
    "country": (SemanticType.COUNTRY, 0.9),
    "country_code": (SemanticType.COUNTRY_CODE, 0.95),
    "iso_country": (SemanticType.COUNTRY_CODE, 0.9),
    "zip": (SemanticType.ZIP_CODE, 0.9),
    "postal": (SemanticType.POSTAL_CODE, 0.9),
    "zipcode": (SemanticType.ZIP_CODE, 0.95),
    "zip_code": (SemanticType.ZIP_CODE, 0.95),
    "postal_code": (SemanticType.POSTAL_CODE, 0.95),
    "postcode": (SemanticType.POSTAL_CODE, 0.9),
    "latitude": (SemanticType.LATITUDE, 0.95),
    "lat": (SemanticType.LATITUDE, 0.85),
    "longitude": (SemanticType.LONGITUDE, 0.95),
    "lng": (SemanticType.LONGITUDE, 0.85),
    "lon": (SemanticType.LONGITUDE, 0.85),
    "ip_address": (SemanticType.IP_ADDRESS, 0.95),
    "ip": (SemanticType.IP_ADDRESS, 0.8),
    "client_ip": (SemanticType.IP_ADDRESS, 0.9),
    "remote_ip": (SemanticType.IP_ADDRESS, 0.9),
    "mac_address": (SemanticType.MAC_ADDRESS, 0.95),
    "geohash": (SemanticType.GEOHASH, 0.9),

    # Status and Flags
    "status": (SemanticType.STATUS, 0.9),
    "workflow_state": (SemanticType.WORKFLOW_STATE, 0.9),
    "type": (SemanticType.TYPE, 0.7),
    "category": (SemanticType.CATEGORY, 0.75),
    "flag": (SemanticType.FLAG, 0.85),
    "is_": (SemanticType.BOOLEAN, 0.9),
    "has_": (SemanticType.BOOLEAN, 0.9),
    "can_": (SemanticType.BOOLEAN, 0.9),
    "active": (SemanticType.IS_ACTIVE, 0.8),
    "is_active": (SemanticType.IS_ACTIVE, 0.95),
    "enabled": (SemanticType.IS_ENABLED, 0.8),
    "is_enabled": (SemanticType.IS_ENABLED, 0.95),
    "deleted": (SemanticType.IS_DELETED, 0.8),
    "is_deleted": (SemanticType.IS_DELETED, 0.95),
    "verified": (SemanticType.IS_VERIFIED, 0.8),
    "is_verified": (SemanticType.IS_VERIFIED, 0.95),
    "priority": (SemanticType.PRIORITY, 0.9),
    "severity": (SemanticType.SEVERITY, 0.9),

    # Measurement
    "score": (SemanticType.SCORE, 0.85),
    "points": (SemanticType.SCORE, 0.8),
    "rating": (SemanticType.RATING, 0.85),
    "stars": (SemanticType.RATING, 0.8),
    "rank": (SemanticType.RANK, 0.85),
    "weight": (SemanticType.WEIGHT, 0.85),
    "height": (SemanticType.HEIGHT, 0.85),
    "width": (SemanticType.WIDTH, 0.85),
    "length": (SemanticType.LENGTH, 0.85),
    "area": (SemanticType.AREA, 0.85),
    "volume": (SemanticType.VOLUME, 0.85),
    "temperature": (SemanticType.TEMPERATURE, 0.9),
    "speed": (SemanticType.SPEED, 0.85),
    "distance": (SemanticType.DISTANCE, 0.85),
    "sequence": (SemanticType.SEQUENCE, 0.8),
    "seq": (SemanticType.SEQUENCE, 0.75),
    "order": (SemanticType.SEQUENCE, 0.7),
    "sort_order": (SemanticType.SEQUENCE, 0.85),
    "version": (SemanticType.VERSION, 0.85),
    "revision": (SemanticType.VERSION, 0.8),

    # Text Content
    "title": (SemanticType.TITLE, 0.85),
    "headline": (SemanticType.TITLE, 0.85),
    "description": (SemanticType.DESCRIPTION, 0.9),
    "desc": (SemanticType.DESCRIPTION, 0.8),
    "summary": (SemanticType.SUMMARY, 0.85),
    "abstract": (SemanticType.SUMMARY, 0.85),
    "content": (SemanticType.CONTENT, 0.8),
    "body": (SemanticType.BODY, 0.8),
    "text": (SemanticType.CONTENT, 0.7),
    "comment": (SemanticType.COMMENT, 0.85),
    "note": (SemanticType.NOTE, 0.8),
    "notes": (SemanticType.NOTE, 0.8),
    "remark": (SemanticType.COMMENT, 0.8),
    "message": (SemanticType.MESSAGE, 0.85),
    "msg": (SemanticType.MESSAGE, 0.8),
    "label": (SemanticType.LABEL, 0.8),
    "tag": (SemanticType.TAG, 0.8),
    "tags": (SemanticType.TAG, 0.8),
    "keyword": (SemanticType.KEYWORD, 0.85),
    "keywords": (SemanticType.KEYWORD, 0.85),
    "url": (SemanticType.URL, 0.9),
    "link": (SemanticType.URL, 0.8),
    "href": (SemanticType.URL, 0.85),
    "website": (SemanticType.URL, 0.85),
    "endpoint": (SemanticType.URL, 0.8),
    "uri": (SemanticType.URI, 0.85),
    "path": (SemanticType.PATH, 0.8),
    "file_path": (SemanticType.PATH, 0.9),
    "filename": (SemanticType.FILENAME, 0.9),
    "file_name": (SemanticType.FILENAME, 0.9),
    "mime_type": (SemanticType.MIME_TYPE, 0.95),
    "content_type": (SemanticType.MIME_TYPE, 0.9),
    "media_type": (SemanticType.MIME_TYPE, 0.9),
    "json": (SemanticType.JSON, 0.9),
    "xml": (SemanticType.XML, 0.9),
    "html": (SemanticType.HTML, 0.9),
    "markdown": (SemanticType.MARKDOWN, 0.9),

    # Binary
    "image": (SemanticType.IMAGE, 0.85),
    "img": (SemanticType.IMAGE, 0.8),
    "photo": (SemanticType.PHOTO, 0.85),
    "picture": (SemanticType.IMAGE, 0.8),
    "avatar": (SemanticType.AVATAR, 0.9),
    "thumbnail": (SemanticType.THUMBNAIL, 0.9),
    "icon": (SemanticType.IMAGE, 0.8),
    "file": (SemanticType.FILE, 0.75),
    "document": (SemanticType.DOCUMENT, 0.8),
    "attachment": (SemanticType.ATTACHMENT, 0.85),
    "blob": (SemanticType.BLOB, 0.85),
    "hash": (SemanticType.HASH, 0.85),
    "checksum": (SemanticType.CHECKSUM, 0.9),
    "digest": (SemanticType.HASH, 0.85),
    "md5": (SemanticType.HASH, 0.9),
    "sha": (SemanticType.HASH, 0.9),
    "signature": (SemanticType.SIGNATURE, 0.85),

    # Technical
    "api_key": (SemanticType.API_KEY, 0.95),
    "access_key": (SemanticType.API_KEY, 0.9),
    "secret_key": (SemanticType.SECRET, 0.9),
    "secret": (SemanticType.SECRET, 0.85),
    "client_secret": (SemanticType.SECRET, 0.9),
    "token": (SemanticType.TOKEN, 0.85),
    "jwt": (SemanticType.TOKEN, 0.9),
    "bearer": (SemanticType.TOKEN, 0.85),
    "auth_token": (SemanticType.TOKEN, 0.9),
    "access_token": (SemanticType.TOKEN, 0.95),
    "refresh_token": (SemanticType.TOKEN, 0.95),
    "session_id": (SemanticType.SESSION_ID, 0.95),
    "sess_id": (SemanticType.SESSION_ID, 0.9),
    "correlation_id": (SemanticType.CORRELATION_ID, 0.95),
    "request_id": (SemanticType.CORRELATION_ID, 0.9),
    "trace_id": (SemanticType.TRACE_ID, 0.95),
    "span_id": (SemanticType.TRACE_ID, 0.9),
    "log_level": (SemanticType.LOG_LEVEL, 0.9),
    "error_code": (SemanticType.ERROR_CODE, 0.9),
    "stack_trace": (SemanticType.STACK_TRACE, 0.95),
    "user_agent": (SemanticType.USER_AGENT, 0.95),
    "referrer": (SemanticType.REFERRER, 0.9),
    "referer": (SemanticType.REFERRER, 0.9),
}


# Database type mappings: db type -> (semantic type, confidence)
DB_TYPE_MAPPINGS: Dict[str, Tuple[SemanticType, float]] = {
    # UUID
    "uuid": (SemanticType.UUID, 0.95),

    # Temporal
    "timestamp": (SemanticType.TIMESTAMP, 0.9),
    "timestamptz": (SemanticType.TIMESTAMP, 0.9),
    "timestamp with time zone": (SemanticType.TIMESTAMP, 0.9),
    "timestamp without time zone": (SemanticType.TIMESTAMP, 0.85),
    "date": (SemanticType.DATE, 0.85),
    "time": (SemanticType.TIME, 0.85),
    "timetz": (SemanticType.TIME, 0.85),
    "time with time zone": (SemanticType.TIME, 0.85),
    "interval": (SemanticType.DURATION, 0.8),

    # Boolean
    "boolean": (SemanticType.BOOLEAN, 0.9),
    "bool": (SemanticType.BOOLEAN, 0.9),

    # JSON/XML
    "json": (SemanticType.JSON, 0.9),
    "jsonb": (SemanticType.JSON, 0.9),
    "xml": (SemanticType.XML, 0.9),

    # Network
    "inet": (SemanticType.IP_ADDRESS, 0.95),
    "cidr": (SemanticType.IP_ADDRESS, 0.9),
    "macaddr": (SemanticType.MAC_ADDRESS, 0.95),
    "macaddr8": (SemanticType.MAC_ADDRESS, 0.95),

    # Binary
    "bytea": (SemanticType.BLOB, 0.7),

    # Money
    "money": (SemanticType.AMOUNT, 0.85),
}


# Pattern type to semantic type mapping
PATTERN_TO_SEMANTIC: Dict[PatternType, SemanticType] = {
    PatternType.EMAIL: SemanticType.EMAIL,
    PatternType.PHONE: SemanticType.PHONE,
    PatternType.URL: SemanticType.URL,
    PatternType.UUID: SemanticType.UUID,
    PatternType.IP_ADDRESS: SemanticType.IP_ADDRESS,
    PatternType.DATE_ISO: SemanticType.DATE,
    PatternType.DATE_US: SemanticType.DATE,
    PatternType.DATE_EU: SemanticType.DATE,
    PatternType.CREDIT_CARD: SemanticType.CREDIT_CARD,
    PatternType.SSN: SemanticType.SSN,
    PatternType.ZIP_CODE: SemanticType.ZIP_CODE,
    PatternType.CURRENCY: SemanticType.CURRENCY,
    PatternType.PERCENTAGE: SemanticType.PERCENTAGE,
    PatternType.JSON: SemanticType.JSON,
    PatternType.MAC_ADDRESS: SemanticType.MAC_ADDRESS,
    PatternType.SLUG: SemanticType.SLUG,
}


# =============================================================================
# Type Inference Engine
# =============================================================================


class TypeInferenceEngine:
    """
    Infers semantic types using multiple signals with configurable weights.

    The engine combines four types of signals:
    1. Column name patterns (e.g., "email" suggests EMAIL type)
    2. Database data types (e.g., UUID type suggests UUID semantic)
    3. Value patterns (e.g., regex matching email format)
    4. Statistical properties (e.g., uniqueness suggesting primary key)

    Signals are weighted and combined to produce a confidence-scored result
    with alternative type suggestions.

    Attributes:
        weights: Dictionary of signal source weights
        pattern_detector: PatternDetector instance for value analysis

    Example:
        >>> engine = TypeInferenceEngine()
        >>> result = engine.infer_type(
        ...     column_name="customer_email",
        ...     data_type="varchar",
        ...     statistics=stats,
        ...     pattern_matches=patterns,
        ... )
        >>> print(f"{result.inferred_type}: {result.confidence_score}")
        email: 0.85

        >>> # Customize weights for different use cases
        >>> engine = TypeInferenceEngine(
        ...     name_weight=0.5,      # Prioritize name patterns
        ...     pattern_weight=0.4,   # Strong signal from value patterns
        ...     data_type_weight=0.1, # Less weight on DB types
        ... )
    """

    # Default signal weights
    DEFAULT_WEIGHTS = {
        "name": 0.4,
        "data_type": 0.2,
        "pattern": 0.3,
        "statistics": 0.1,
    }

    def __init__(
        self,
        name_weight: float = 0.4,
        data_type_weight: float = 0.2,
        pattern_weight: float = 0.3,
        stats_weight: float = 0.1,
        name_patterns: Optional[Dict[str, Tuple[SemanticType, float]]] = None,
        db_type_mappings: Optional[Dict[str, Tuple[SemanticType, float]]] = None,
    ):
        """
        Initialize the type inference engine.

        Args:
            name_weight: Weight for column name signals (default: 0.4)
            data_type_weight: Weight for database type signals (default: 0.2)
            pattern_weight: Weight for pattern detection signals (default: 0.3)
            stats_weight: Weight for statistical signals (default: 0.1)
            name_patterns: Custom name pattern mappings (uses defaults if None)
            db_type_mappings: Custom DB type mappings (uses defaults if None)
        """
        # Validate weights sum to approximately 1.0
        total_weight = name_weight + data_type_weight + pattern_weight + stats_weight
        if not 0.99 <= total_weight <= 1.01:
            raise ValueError(
                f"Weights should sum to 1.0, got {total_weight}. "
                f"Weights: name={name_weight}, data_type={data_type_weight}, "
                f"pattern={pattern_weight}, stats={stats_weight}"
            )

        self.weights = {
            "name": name_weight,
            "data_type": data_type_weight,
            "pattern": pattern_weight,
            "statistics": stats_weight,
        }

        self.name_patterns = name_patterns or NAME_PATTERNS
        self.db_type_mappings = db_type_mappings or DB_TYPE_MAPPINGS
        self.pattern_detector = PatternDetector()

    def infer_type(
        self,
        column_name: str,
        data_type: str,
        statistics: Optional[ColumnStatistics] = None,
        pattern_matches: Optional[List[PatternMatch]] = None,
        sample_values: Optional[List[Any]] = None,
    ) -> TypeInferenceResult:
        """
        Infer the semantic type of a column.

        Uses multiple signals (name patterns, data type, value patterns,
        statistics) to determine the most likely semantic type with
        a confidence score.

        Args:
            column_name: Name of the column
            data_type: Database data type (e.g., "varchar", "uuid", "timestamp")
            statistics: Column statistics including uniqueness, null percentage
            pattern_matches: Pre-computed pattern matches from profiling
            sample_values: Sample values for pattern detection (if no matches provided)

        Returns:
            TypeInferenceResult with inferred type, confidence, and alternatives

        Example:
            >>> result = engine.infer_type(
            ...     column_name="user_email",
            ...     data_type="varchar(255)",
            ...     statistics=ColumnStatistics(...),
            ... )
            >>> print(result.inferred_type)  # SemanticType.EMAIL
        """
        signals: List[TypeSignal] = []

        # 1. Collect name-based signals
        name_signals = self._get_name_signals(column_name)
        signals.extend(name_signals)

        # 2. Collect data type signals
        type_signals = self._get_data_type_signals(data_type)
        signals.extend(type_signals)

        # 3. Collect pattern signals
        if pattern_matches:
            pattern_signals = self._get_pattern_signals(pattern_matches)
            signals.extend(pattern_signals)
        elif sample_values:
            # Detect patterns from sample values
            detected_patterns = self.pattern_detector.detect_patterns(sample_values)
            pattern_signals = self._get_pattern_signals(detected_patterns)
            signals.extend(pattern_signals)

        # 4. Collect statistical signals
        if statistics:
            stat_signals = self._get_statistical_signals(column_name, statistics)
            signals.extend(stat_signals)

        # Handle case with no signals
        if not signals:
            return TypeInferenceResult(
                column_name=column_name,
                inferred_type=SemanticType.UNKNOWN,
                confidence=ConfidenceLevel.LOW,
                confidence_score=0.0,
                category=SemanticCategory.UNKNOWN,
                signals=[],
                alternative_types=[],
            )

        # Calculate weighted scores for each semantic type
        type_scores: Dict[SemanticType, float] = {}
        for signal in signals:
            weight = self.weights.get(signal.source, 0.1)
            weighted_score = signal.confidence * weight

            if signal.semantic_type not in type_scores:
                type_scores[signal.semantic_type] = 0.0
            type_scores[signal.semantic_type] += weighted_score

        # Sort types by score descending
        sorted_types = sorted(
            type_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # Get best type and score
        best_type, best_score = sorted_types[0]

        # Normalize score to 0-1 range
        max_possible = sum(self.weights.values())
        normalized_score = min(best_score / max_possible, 1.0)

        # Determine confidence level
        confidence = self._score_to_confidence(normalized_score)

        # Get alternative types (top 3 after best, with minimum score threshold)
        alternatives = [
            (t, round(s / max_possible, 3))
            for t, s in sorted_types[1:4]
            if s / max_possible > 0.1
        ]

        return TypeInferenceResult(
            column_name=column_name,
            inferred_type=best_type,
            confidence=confidence,
            confidence_score=round(normalized_score, 3),
            category=get_category(best_type),
            signals=signals,
            alternative_types=alternatives,
        )

    def infer_types_batch(
        self,
        columns: List[Dict[str, Any]],
    ) -> List[TypeInferenceResult]:
        """
        Infer types for multiple columns efficiently.

        Args:
            columns: List of column dictionaries, each containing:
                - name: Column name (required)
                - data_type: Database type (required)
                - statistics: ColumnStatistics object (optional)
                - patterns: List of PatternMatch (optional)
                - sample_values: List of sample values (optional)

        Returns:
            List of TypeInferenceResult for each column

        Example:
            >>> columns = [
            ...     {"name": "email", "data_type": "varchar"},
            ...     {"name": "created_at", "data_type": "timestamp"},
            ... ]
            >>> results = engine.infer_types_batch(columns)
            >>> for r in results:
            ...     print(f"{r.column_name}: {r.inferred_type.value}")
        """
        results = []
        for col in columns:
            result = self.infer_type(
                column_name=col.get("name", ""),
                data_type=col.get("data_type", ""),
                statistics=col.get("statistics"),
                pattern_matches=col.get("patterns"),
                sample_values=col.get("sample_values"),
            )
            results.append(result)
        return results

    def _get_name_signals(self, column_name: str) -> List[TypeSignal]:
        """
        Extract signals from column name patterns.

        Checks the column name against known patterns (substrings, prefixes,
        suffixes) that suggest specific semantic types.

        Args:
            column_name: Name of the column to analyze

        Returns:
            List of TypeSignal objects from name matching
        """
        signals = []
        name_lower = column_name.lower()

        # Check each pattern against the column name
        for pattern, (semantic_type, confidence) in self.name_patterns.items():
            # Handle prefix patterns (e.g., "is_", "has_")
            if pattern.endswith("_"):
                if name_lower.startswith(pattern):
                    signals.append(TypeSignal(
                        source="name",
                        semantic_type=semantic_type,
                        confidence=confidence,
                        reason=f"Column name starts with '{pattern}'",
                    ))
            # Handle suffix patterns (e.g., "_id", "_at")
            elif pattern.startswith("_"):
                if name_lower.endswith(pattern):
                    signals.append(TypeSignal(
                        source="name",
                        semantic_type=semantic_type,
                        confidence=confidence,
                        reason=f"Column name ends with '{pattern}'",
                    ))
            # Handle exact and substring matches
            elif pattern in name_lower:
                # Boost confidence for exact matches
                adjusted_confidence = confidence
                if name_lower == pattern:
                    adjusted_confidence = min(confidence + 0.05, 1.0)

                signals.append(TypeSignal(
                    source="name",
                    semantic_type=semantic_type,
                    confidence=adjusted_confidence,
                    reason=f"Column name contains '{pattern}'",
                ))

        return signals

    def _get_data_type_signals(self, data_type: str) -> List[TypeSignal]:
        """
        Extract signals from database data type.

        Maps database types (like UUID, TIMESTAMP, BOOLEAN) to corresponding
        semantic types with appropriate confidence levels.

        Args:
            data_type: Database data type string

        Returns:
            List of TypeSignal objects from data type mapping
        """
        signals = []

        # Normalize data type: lowercase and remove size specifier
        type_lower = data_type.lower().split("(")[0].strip()

        # Also try without precision for types like "numeric(10,2)"
        type_base = type_lower.split(",")[0].strip()

        # Check direct mapping
        if type_lower in self.db_type_mappings:
            semantic_type, confidence = self.db_type_mappings[type_lower]
            signals.append(TypeSignal(
                source="data_type",
                semantic_type=semantic_type,
                confidence=confidence,
                reason=f"Database type '{data_type}' maps to {semantic_type.value}",
            ))
        elif type_base in self.db_type_mappings:
            semantic_type, confidence = self.db_type_mappings[type_base]
            signals.append(TypeSignal(
                source="data_type",
                semantic_type=semantic_type,
                confidence=confidence * 0.9,  # Slightly lower confidence for partial match
                reason=f"Database type '{data_type}' maps to {semantic_type.value}",
            ))

        return signals

    def _get_pattern_signals(self, patterns: List[PatternMatch]) -> List[TypeSignal]:
        """
        Extract signals from detected value patterns.

        Converts PatternMatch objects (from regex detection on values) into
        TypeSignal objects with appropriate semantic type mapping.

        Args:
            patterns: List of pattern matches from value analysis

        Returns:
            List of TypeSignal objects from pattern detection
        """
        signals = []

        for pattern in patterns:
            if pattern.pattern_type in PATTERN_TO_SEMANTIC:
                semantic_type = PATTERN_TO_SEMANTIC[pattern.pattern_type]

                # Convert confidence level to numeric score
                confidence_map = {
                    ConfidenceLevel.HIGH: 0.95,
                    ConfidenceLevel.MEDIUM: 0.75,
                    ConfidenceLevel.LOW: 0.5,
                }
                confidence = confidence_map.get(pattern.confidence, 0.5)

                signals.append(TypeSignal(
                    source="pattern",
                    semantic_type=semantic_type,
                    confidence=confidence,
                    reason=(
                        f"Pattern '{pattern.pattern_type.value}' matches "
                        f"{pattern.match_percentage:.1f}% of values"
                    ),
                ))

        return signals

    def _get_statistical_signals(
        self,
        column_name: str,
        stats: ColumnStatistics,
    ) -> List[TypeSignal]:
        """
        Extract signals from column statistics.

        Uses statistical properties like uniqueness, cardinality, and null
        percentage to infer semantic types (e.g., unique non-null suggests
        primary key).

        Args:
            column_name: Name of the column (for context)
            stats: ColumnStatistics with uniqueness, null percentage, etc.

        Returns:
            List of TypeSignal objects from statistical analysis
        """
        signals = []
        name_lower = column_name.lower()

        # Unique, non-null column with 'id' in name suggests primary key
        if stats.is_unique and stats.null_percentage == 0:
            if "id" in name_lower or name_lower.endswith("_id"):
                signals.append(TypeSignal(
                    source="statistics",
                    semantic_type=SemanticType.PRIMARY_KEY,
                    confidence=0.85,
                    reason="Column is unique and non-null with 'id' in name",
                ))
            elif "uuid" in name_lower or "guid" in name_lower:
                signals.append(TypeSignal(
                    source="statistics",
                    semantic_type=SemanticType.UUID,
                    confidence=0.75,
                    reason="Column is unique with UUID-like name",
                ))

        # Low cardinality suggests enum/status
        if stats.distinct_count and stats.total_count:
            cardinality_ratio = stats.distinct_count / stats.total_count

            # Very low cardinality (< 1%) with few distinct values
            if cardinality_ratio < 0.01 and stats.distinct_count < 20:
                signals.append(TypeSignal(
                    source="statistics",
                    semantic_type=SemanticType.ENUM,
                    confidence=0.7,
                    reason=(
                        f"Low cardinality: {stats.distinct_count} distinct values "
                        f"({cardinality_ratio*100:.2f}% of total)"
                    ),
                ))

            # Moderate cardinality with name hints
            if cardinality_ratio < 0.05 and stats.distinct_count < 50:
                if "status" in name_lower or "state" in name_lower:
                    signals.append(TypeSignal(
                        source="statistics",
                        semantic_type=SemanticType.STATUS,
                        confidence=0.65,
                        reason=f"Low cardinality ({stats.distinct_count} values) with status-like name",
                    ))
                elif "type" in name_lower or "category" in name_lower:
                    signals.append(TypeSignal(
                        source="statistics",
                        semantic_type=SemanticType.CATEGORY,
                        confidence=0.65,
                        reason=f"Low cardinality ({stats.distinct_count} values) with category-like name",
                    ))

        # Exactly 2 distinct values suggests boolean
        if stats.distinct_count == 2:
            signals.append(TypeSignal(
                source="statistics",
                semantic_type=SemanticType.BOOLEAN,
                confidence=0.6,
                reason="Exactly 2 distinct values (binary/boolean)",
            ))

        # High null percentage with 'deleted' in name suggests soft delete flag
        if stats.null_percentage > 90 and ("deleted" in name_lower or "removed" in name_lower):
            signals.append(TypeSignal(
                source="statistics",
                semantic_type=SemanticType.DELETED_AT,
                confidence=0.7,
                reason=f"Mostly null ({stats.null_percentage:.1f}%) with deletion-related name",
            ))

        return signals

    def _score_to_confidence(self, score: float) -> ConfidenceLevel:
        """
        Convert numeric score to confidence level.

        Args:
            score: Normalized score from 0.0 to 1.0

        Returns:
            ConfidenceLevel enum value
        """
        if score >= 0.8:
            return ConfidenceLevel.HIGH
        elif score >= 0.5:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def get_pii_types(self, results: List[TypeInferenceResult]) -> List[TypeInferenceResult]:
        """
        Filter results to only PII types.

        Args:
            results: List of inference results

        Returns:
            List of results where inferred type is PII
        """
        return [r for r in results if r.is_pii]

    def get_sensitive_types(self, results: List[TypeInferenceResult]) -> List[TypeInferenceResult]:
        """
        Filter results to only sensitive types.

        Args:
            results: List of inference results

        Returns:
            List of results where inferred type is sensitive
        """
        return [r for r in results if r.is_sensitive]

    def summarize_by_category(
        self,
        results: List[TypeInferenceResult],
    ) -> Dict[SemanticCategory, List[TypeInferenceResult]]:
        """
        Group inference results by semantic category.

        Args:
            results: List of inference results

        Returns:
            Dictionary mapping categories to their results
        """
        summary: Dict[SemanticCategory, List[TypeInferenceResult]] = {}
        for result in results:
            if result.category not in summary:
                summary[result.category] = []
            summary[result.category].append(result)
        return summary
