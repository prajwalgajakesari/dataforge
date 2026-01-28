"""
Semantic type system for data classification.

This module provides a comprehensive type system for classifying database
columns by their semantic meaning. It includes semantic categories, specific
semantic types, database type mappings, and inference patterns.

The type system enables:
- Automatic column classification during schema analysis
- PII detection and data sensitivity classification
- Intelligent code generation based on data semantics
- Data quality rule inference
"""

import re
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Pattern, Set, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SemanticCategory(str, Enum):
    """
    High-level semantic categories for data classification.

    These categories group related semantic types for easier filtering
    and policy application (e.g., all PERSONAL data requires encryption).
    """

    IDENTIFIER = "identifier"
    PERSONAL = "personal"
    TEMPORAL = "temporal"
    FINANCIAL = "financial"
    GEOGRAPHIC = "geographic"
    STATUS = "status"
    MEASUREMENT = "measurement"
    TEXT = "text"
    BINARY = "binary"
    TECHNICAL = "technical"
    UNKNOWN = "unknown"


class SemanticType(str, Enum):
    """
    Specific semantic types for database columns.

    These types provide fine-grained classification of column data,
    enabling intelligent handling during analysis and generation.
    """

    # Identifiers
    PRIMARY_KEY = "primary_key"
    FOREIGN_KEY = "foreign_key"
    SURROGATE_KEY = "surrogate_key"
    NATURAL_KEY = "natural_key"
    UUID = "uuid"
    SLUG = "slug"
    CODE = "code"
    SKU = "sku"

    # Personal Information
    EMAIL = "email"
    PHONE = "phone"
    NAME = "name"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    FULL_NAME = "full_name"
    MIDDLE_NAME = "middle_name"
    USERNAME = "username"
    PASSWORD_HASH = "password_hash"
    SSN = "ssn"
    NATIONAL_ID = "national_id"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    DATE_OF_BIRTH = "date_of_birth"
    AGE = "age"
    GENDER = "gender"
    ETHNICITY = "ethnicity"
    RELIGION = "religion"
    POLITICAL_AFFILIATION = "political_affiliation"

    # Temporal
    DATE = "date"
    DATETIME = "datetime"
    TIMESTAMP = "timestamp"
    TIME = "time"
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    WEEK = "week"
    QUARTER = "quarter"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    DELETED_AT = "deleted_at"
    EXPIRED_AT = "expired_at"
    START_DATE = "start_date"
    END_DATE = "end_date"
    DURATION = "duration"
    TIMEZONE = "timezone"

    # Financial
    CURRENCY = "currency"
    CURRENCY_CODE = "currency_code"
    PRICE = "price"
    AMOUNT = "amount"
    COST = "cost"
    REVENUE = "revenue"
    PROFIT = "profit"
    TAX = "tax"
    DISCOUNT = "discount"
    QUANTITY = "quantity"
    PERCENTAGE = "percentage"
    RATE = "rate"
    CREDIT_CARD = "credit_card"
    BANK_ACCOUNT = "bank_account"
    ROUTING_NUMBER = "routing_number"
    IBAN = "iban"
    SWIFT_CODE = "swift_code"

    # Geographic
    ADDRESS = "address"
    ADDRESS_LINE_1 = "address_line_1"
    ADDRESS_LINE_2 = "address_line_2"
    STREET = "street"
    CITY = "city"
    STATE = "state"
    PROVINCE = "province"
    REGION = "region"
    COUNTRY = "country"
    COUNTRY_CODE = "country_code"
    ZIP_CODE = "zip_code"
    POSTAL_CODE = "postal_code"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    COORDINATES = "coordinates"
    IP_ADDRESS = "ip_address"
    MAC_ADDRESS = "mac_address"
    GEOHASH = "geohash"

    # Status and Flags
    STATUS = "status"
    WORKFLOW_STATE = "workflow_state"
    FLAG = "flag"
    BOOLEAN = "boolean"
    ENUM = "enum"
    TYPE = "type"
    CATEGORY = "category"
    PRIORITY = "priority"
    SEVERITY = "severity"
    IS_ACTIVE = "is_active"
    IS_DELETED = "is_deleted"
    IS_ENABLED = "is_enabled"
    IS_VERIFIED = "is_verified"

    # Measurement
    COUNT = "count"
    TOTAL = "total"
    AVERAGE = "average"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    WEIGHT = "weight"
    HEIGHT = "height"
    WIDTH = "width"
    LENGTH = "length"
    AREA = "area"
    VOLUME = "volume"
    TEMPERATURE = "temperature"
    SPEED = "speed"
    DISTANCE = "distance"
    SCORE = "score"
    RATING = "rating"
    RANK = "rank"
    SEQUENCE = "sequence"
    VERSION = "version"

    # Text Content
    TITLE = "title"
    DESCRIPTION = "description"
    SUMMARY = "summary"
    CONTENT = "content"
    BODY = "body"
    COMMENT = "comment"
    NOTE = "note"
    MESSAGE = "message"
    LABEL = "label"
    TAG = "tag"
    KEYWORD = "keyword"
    JSON = "json"
    XML = "xml"
    HTML = "html"
    MARKDOWN = "markdown"
    URL = "url"
    URI = "uri"
    PATH = "path"
    FILENAME = "filename"
    MIME_TYPE = "mime_type"

    # Binary
    BLOB = "blob"
    IMAGE = "image"
    PHOTO = "photo"
    AVATAR = "avatar"
    THUMBNAIL = "thumbnail"
    FILE = "file"
    DOCUMENT = "document"
    ATTACHMENT = "attachment"
    SIGNATURE = "signature"
    HASH = "hash"
    CHECKSUM = "checksum"

    # Technical
    API_KEY = "api_key"
    SECRET = "secret"
    TOKEN = "token"
    SESSION_ID = "session_id"
    CORRELATION_ID = "correlation_id"
    TRACE_ID = "trace_id"
    LOG_LEVEL = "log_level"
    ERROR_CODE = "error_code"
    STACK_TRACE = "stack_trace"
    USER_AGENT = "user_agent"
    REFERRER = "referrer"

    # Unknown
    UNKNOWN = "unknown"


# Map semantic types to their categories
SEMANTIC_TYPE_CATEGORIES: Dict[SemanticType, SemanticCategory] = {
    # Identifiers
    SemanticType.PRIMARY_KEY: SemanticCategory.IDENTIFIER,
    SemanticType.FOREIGN_KEY: SemanticCategory.IDENTIFIER,
    SemanticType.SURROGATE_KEY: SemanticCategory.IDENTIFIER,
    SemanticType.NATURAL_KEY: SemanticCategory.IDENTIFIER,
    SemanticType.UUID: SemanticCategory.IDENTIFIER,
    SemanticType.SLUG: SemanticCategory.IDENTIFIER,
    SemanticType.CODE: SemanticCategory.IDENTIFIER,
    SemanticType.SKU: SemanticCategory.IDENTIFIER,

    # Personal
    SemanticType.EMAIL: SemanticCategory.PERSONAL,
    SemanticType.PHONE: SemanticCategory.PERSONAL,
    SemanticType.NAME: SemanticCategory.PERSONAL,
    SemanticType.FIRST_NAME: SemanticCategory.PERSONAL,
    SemanticType.LAST_NAME: SemanticCategory.PERSONAL,
    SemanticType.FULL_NAME: SemanticCategory.PERSONAL,
    SemanticType.MIDDLE_NAME: SemanticCategory.PERSONAL,
    SemanticType.USERNAME: SemanticCategory.PERSONAL,
    SemanticType.PASSWORD_HASH: SemanticCategory.PERSONAL,
    SemanticType.SSN: SemanticCategory.PERSONAL,
    SemanticType.NATIONAL_ID: SemanticCategory.PERSONAL,
    SemanticType.PASSPORT: SemanticCategory.PERSONAL,
    SemanticType.DRIVERS_LICENSE: SemanticCategory.PERSONAL,
    SemanticType.DATE_OF_BIRTH: SemanticCategory.PERSONAL,
    SemanticType.AGE: SemanticCategory.PERSONAL,
    SemanticType.GENDER: SemanticCategory.PERSONAL,
    SemanticType.ETHNICITY: SemanticCategory.PERSONAL,
    SemanticType.RELIGION: SemanticCategory.PERSONAL,
    SemanticType.POLITICAL_AFFILIATION: SemanticCategory.PERSONAL,

    # Temporal
    SemanticType.DATE: SemanticCategory.TEMPORAL,
    SemanticType.DATETIME: SemanticCategory.TEMPORAL,
    SemanticType.TIMESTAMP: SemanticCategory.TEMPORAL,
    SemanticType.TIME: SemanticCategory.TEMPORAL,
    SemanticType.YEAR: SemanticCategory.TEMPORAL,
    SemanticType.MONTH: SemanticCategory.TEMPORAL,
    SemanticType.DAY: SemanticCategory.TEMPORAL,
    SemanticType.WEEK: SemanticCategory.TEMPORAL,
    SemanticType.QUARTER: SemanticCategory.TEMPORAL,
    SemanticType.CREATED_AT: SemanticCategory.TEMPORAL,
    SemanticType.UPDATED_AT: SemanticCategory.TEMPORAL,
    SemanticType.DELETED_AT: SemanticCategory.TEMPORAL,
    SemanticType.EXPIRED_AT: SemanticCategory.TEMPORAL,
    SemanticType.START_DATE: SemanticCategory.TEMPORAL,
    SemanticType.END_DATE: SemanticCategory.TEMPORAL,
    SemanticType.DURATION: SemanticCategory.TEMPORAL,
    SemanticType.TIMEZONE: SemanticCategory.TEMPORAL,

    # Financial
    SemanticType.CURRENCY: SemanticCategory.FINANCIAL,
    SemanticType.CURRENCY_CODE: SemanticCategory.FINANCIAL,
    SemanticType.PRICE: SemanticCategory.FINANCIAL,
    SemanticType.AMOUNT: SemanticCategory.FINANCIAL,
    SemanticType.COST: SemanticCategory.FINANCIAL,
    SemanticType.REVENUE: SemanticCategory.FINANCIAL,
    SemanticType.PROFIT: SemanticCategory.FINANCIAL,
    SemanticType.TAX: SemanticCategory.FINANCIAL,
    SemanticType.DISCOUNT: SemanticCategory.FINANCIAL,
    SemanticType.QUANTITY: SemanticCategory.FINANCIAL,
    SemanticType.PERCENTAGE: SemanticCategory.FINANCIAL,
    SemanticType.RATE: SemanticCategory.FINANCIAL,
    SemanticType.CREDIT_CARD: SemanticCategory.FINANCIAL,
    SemanticType.BANK_ACCOUNT: SemanticCategory.FINANCIAL,
    SemanticType.ROUTING_NUMBER: SemanticCategory.FINANCIAL,
    SemanticType.IBAN: SemanticCategory.FINANCIAL,
    SemanticType.SWIFT_CODE: SemanticCategory.FINANCIAL,

    # Geographic
    SemanticType.ADDRESS: SemanticCategory.GEOGRAPHIC,
    SemanticType.ADDRESS_LINE_1: SemanticCategory.GEOGRAPHIC,
    SemanticType.ADDRESS_LINE_2: SemanticCategory.GEOGRAPHIC,
    SemanticType.STREET: SemanticCategory.GEOGRAPHIC,
    SemanticType.CITY: SemanticCategory.GEOGRAPHIC,
    SemanticType.STATE: SemanticCategory.GEOGRAPHIC,
    SemanticType.PROVINCE: SemanticCategory.GEOGRAPHIC,
    SemanticType.REGION: SemanticCategory.GEOGRAPHIC,
    SemanticType.COUNTRY: SemanticCategory.GEOGRAPHIC,
    SemanticType.COUNTRY_CODE: SemanticCategory.GEOGRAPHIC,
    SemanticType.ZIP_CODE: SemanticCategory.GEOGRAPHIC,
    SemanticType.POSTAL_CODE: SemanticCategory.GEOGRAPHIC,
    SemanticType.LATITUDE: SemanticCategory.GEOGRAPHIC,
    SemanticType.LONGITUDE: SemanticCategory.GEOGRAPHIC,
    SemanticType.COORDINATES: SemanticCategory.GEOGRAPHIC,
    SemanticType.IP_ADDRESS: SemanticCategory.GEOGRAPHIC,
    SemanticType.MAC_ADDRESS: SemanticCategory.TECHNICAL,
    SemanticType.GEOHASH: SemanticCategory.GEOGRAPHIC,

    # Status
    SemanticType.STATUS: SemanticCategory.STATUS,
    SemanticType.WORKFLOW_STATE: SemanticCategory.STATUS,
    SemanticType.FLAG: SemanticCategory.STATUS,
    SemanticType.BOOLEAN: SemanticCategory.STATUS,
    SemanticType.ENUM: SemanticCategory.STATUS,
    SemanticType.TYPE: SemanticCategory.STATUS,
    SemanticType.CATEGORY: SemanticCategory.STATUS,
    SemanticType.PRIORITY: SemanticCategory.STATUS,
    SemanticType.SEVERITY: SemanticCategory.STATUS,
    SemanticType.IS_ACTIVE: SemanticCategory.STATUS,
    SemanticType.IS_DELETED: SemanticCategory.STATUS,
    SemanticType.IS_ENABLED: SemanticCategory.STATUS,
    SemanticType.IS_VERIFIED: SemanticCategory.STATUS,

    # Measurement
    SemanticType.COUNT: SemanticCategory.MEASUREMENT,
    SemanticType.TOTAL: SemanticCategory.MEASUREMENT,
    SemanticType.AVERAGE: SemanticCategory.MEASUREMENT,
    SemanticType.SUM: SemanticCategory.MEASUREMENT,
    SemanticType.MIN: SemanticCategory.MEASUREMENT,
    SemanticType.MAX: SemanticCategory.MEASUREMENT,
    SemanticType.WEIGHT: SemanticCategory.MEASUREMENT,
    SemanticType.HEIGHT: SemanticCategory.MEASUREMENT,
    SemanticType.WIDTH: SemanticCategory.MEASUREMENT,
    SemanticType.LENGTH: SemanticCategory.MEASUREMENT,
    SemanticType.AREA: SemanticCategory.MEASUREMENT,
    SemanticType.VOLUME: SemanticCategory.MEASUREMENT,
    SemanticType.TEMPERATURE: SemanticCategory.MEASUREMENT,
    SemanticType.SPEED: SemanticCategory.MEASUREMENT,
    SemanticType.DISTANCE: SemanticCategory.MEASUREMENT,
    SemanticType.SCORE: SemanticCategory.MEASUREMENT,
    SemanticType.RATING: SemanticCategory.MEASUREMENT,
    SemanticType.RANK: SemanticCategory.MEASUREMENT,
    SemanticType.SEQUENCE: SemanticCategory.MEASUREMENT,
    SemanticType.VERSION: SemanticCategory.MEASUREMENT,

    # Text
    SemanticType.TITLE: SemanticCategory.TEXT,
    SemanticType.DESCRIPTION: SemanticCategory.TEXT,
    SemanticType.SUMMARY: SemanticCategory.TEXT,
    SemanticType.CONTENT: SemanticCategory.TEXT,
    SemanticType.BODY: SemanticCategory.TEXT,
    SemanticType.COMMENT: SemanticCategory.TEXT,
    SemanticType.NOTE: SemanticCategory.TEXT,
    SemanticType.MESSAGE: SemanticCategory.TEXT,
    SemanticType.LABEL: SemanticCategory.TEXT,
    SemanticType.TAG: SemanticCategory.TEXT,
    SemanticType.KEYWORD: SemanticCategory.TEXT,
    SemanticType.JSON: SemanticCategory.TEXT,
    SemanticType.XML: SemanticCategory.TEXT,
    SemanticType.HTML: SemanticCategory.TEXT,
    SemanticType.MARKDOWN: SemanticCategory.TEXT,
    SemanticType.URL: SemanticCategory.TEXT,
    SemanticType.URI: SemanticCategory.TEXT,
    SemanticType.PATH: SemanticCategory.TEXT,
    SemanticType.FILENAME: SemanticCategory.TEXT,
    SemanticType.MIME_TYPE: SemanticCategory.TEXT,

    # Binary
    SemanticType.BLOB: SemanticCategory.BINARY,
    SemanticType.IMAGE: SemanticCategory.BINARY,
    SemanticType.PHOTO: SemanticCategory.BINARY,
    SemanticType.AVATAR: SemanticCategory.BINARY,
    SemanticType.THUMBNAIL: SemanticCategory.BINARY,
    SemanticType.FILE: SemanticCategory.BINARY,
    SemanticType.DOCUMENT: SemanticCategory.BINARY,
    SemanticType.ATTACHMENT: SemanticCategory.BINARY,
    SemanticType.SIGNATURE: SemanticCategory.BINARY,
    SemanticType.HASH: SemanticCategory.BINARY,
    SemanticType.CHECKSUM: SemanticCategory.BINARY,

    # Technical
    SemanticType.API_KEY: SemanticCategory.TECHNICAL,
    SemanticType.SECRET: SemanticCategory.TECHNICAL,
    SemanticType.TOKEN: SemanticCategory.TECHNICAL,
    SemanticType.SESSION_ID: SemanticCategory.TECHNICAL,
    SemanticType.CORRELATION_ID: SemanticCategory.TECHNICAL,
    SemanticType.TRACE_ID: SemanticCategory.TECHNICAL,
    SemanticType.LOG_LEVEL: SemanticCategory.TECHNICAL,
    SemanticType.ERROR_CODE: SemanticCategory.TECHNICAL,
    SemanticType.STACK_TRACE: SemanticCategory.TECHNICAL,
    SemanticType.USER_AGENT: SemanticCategory.TECHNICAL,
    SemanticType.REFERRER: SemanticCategory.TECHNICAL,

    # Unknown
    SemanticType.UNKNOWN: SemanticCategory.UNKNOWN,
}


# PII (Personally Identifiable Information) types
PII_TYPES: FrozenSet[SemanticType] = frozenset({
    SemanticType.EMAIL,
    SemanticType.PHONE,
    SemanticType.NAME,
    SemanticType.FIRST_NAME,
    SemanticType.LAST_NAME,
    SemanticType.FULL_NAME,
    SemanticType.SSN,
    SemanticType.NATIONAL_ID,
    SemanticType.PASSPORT,
    SemanticType.DRIVERS_LICENSE,
    SemanticType.DATE_OF_BIRTH,
    SemanticType.CREDIT_CARD,
    SemanticType.BANK_ACCOUNT,
    SemanticType.ADDRESS,
    SemanticType.ADDRESS_LINE_1,
    SemanticType.ADDRESS_LINE_2,
    SemanticType.IP_ADDRESS,
})

# Sensitive data types (broader than PII)
SENSITIVE_TYPES: FrozenSet[SemanticType] = PII_TYPES | frozenset({
    SemanticType.PASSWORD_HASH,
    SemanticType.API_KEY,
    SemanticType.SECRET,
    SemanticType.TOKEN,
    SemanticType.GENDER,
    SemanticType.ETHNICITY,
    SemanticType.RELIGION,
    SemanticType.POLITICAL_AFFILIATION,
    SemanticType.ROUTING_NUMBER,
    SemanticType.IBAN,
    SemanticType.SWIFT_CODE,
})


class DatabaseType(str, Enum):
    """
    Standard database column types (PostgreSQL-focused).

    These represent the canonical database types that can be mapped
    to semantic types during analysis.
    """

    # Numeric
    SMALLINT = "smallint"
    INTEGER = "integer"
    BIGINT = "bigint"
    DECIMAL = "decimal"
    NUMERIC = "numeric"
    REAL = "real"
    DOUBLE = "double precision"
    SERIAL = "serial"
    BIGSERIAL = "bigserial"
    SMALLSERIAL = "smallserial"
    MONEY = "money"

    # Character
    CHAR = "char"
    VARCHAR = "varchar"
    TEXT = "text"
    NAME = "name"
    CITEXT = "citext"

    # Binary
    BYTEA = "bytea"

    # Date/Time
    DATE = "date"
    TIME = "time"
    TIMETZ = "time with time zone"
    TIMESTAMP = "timestamp"
    TIMESTAMPTZ = "timestamp with time zone"
    INTERVAL = "interval"

    # Boolean
    BOOLEAN = "boolean"

    # UUID
    UUID = "uuid"

    # JSON
    JSON = "json"
    JSONB = "jsonb"

    # Array
    ARRAY = "array"

    # Network
    INET = "inet"
    CIDR = "cidr"
    MACADDR = "macaddr"
    MACADDR8 = "macaddr8"

    # Geometric
    POINT = "point"
    LINE = "line"
    LSEG = "lseg"
    BOX = "box"
    PATH = "path"
    POLYGON = "polygon"
    CIRCLE = "circle"

    # Other
    XML = "xml"
    TSVECTOR = "tsvector"
    TSQUERY = "tsquery"


class TypeMapping(BaseModel):
    """
    Mapping between database types and semantic types.

    Used to suggest possible semantic types based on database type,
    with associated confidence scores.

    Attributes:
        database_type: The database column type.
        semantic_types: List of possible semantic types.
        confidence: Base confidence for this mapping (0.0 to 1.0).
        requires_name_match: Whether name patterns increase confidence.
    """

    model_config = ConfigDict(frozen=True)

    database_type: str = Field(..., description="Database column type")
    semantic_types: List[SemanticType] = Field(
        ...,
        min_length=1,
        description="Possible semantic types"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Base confidence score"
    )
    requires_name_match: bool = Field(
        default=False,
        description="Requires column name pattern match"
    )


class NamePattern(BaseModel):
    """
    Column name pattern for semantic type inference.

    Defines regex patterns that match column names to suggest
    semantic types with associated confidence adjustments.

    Attributes:
        pattern: Regex pattern to match column names.
        semantic_type: Semantic type to assign on match.
        confidence_boost: Confidence increase on pattern match.
        case_sensitive: Whether pattern matching is case-sensitive.
    """

    model_config = ConfigDict(frozen=True)

    pattern: str = Field(..., description="Regex pattern for column name")
    semantic_type: SemanticType = Field(
        ...,
        description="Semantic type to assign"
    )
    confidence_boost: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Confidence boost on match"
    )
    case_sensitive: bool = Field(
        default=False,
        description="Case-sensitive matching"
    )

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: str) -> str:
        """Validate regex pattern is valid."""
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
        return v

    def matches(self, column_name: str) -> bool:
        """Check if column name matches the pattern."""
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return bool(re.search(self.pattern, column_name, flags))


# Default name patterns for semantic type inference
DEFAULT_NAME_PATTERNS: List[NamePattern] = [
    # Identifiers
    NamePattern(
        pattern=r"^(id|pk|key)$",
        semantic_type=SemanticType.PRIMARY_KEY,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"_id$|_pk$|_key$",
        semantic_type=SemanticType.FOREIGN_KEY,
        confidence_boost=0.3,
    ),
    NamePattern(
        pattern=r"uuid|guid",
        semantic_type=SemanticType.UUID,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^slug$|_slug$",
        semantic_type=SemanticType.SLUG,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^sku$|_sku$|^product_code",
        semantic_type=SemanticType.SKU,
        confidence_boost=0.5,
    ),

    # Personal
    NamePattern(
        pattern=r"email|e_mail|mail_address",
        semantic_type=SemanticType.EMAIL,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"phone|mobile|cell|telephone|fax",
        semantic_type=SemanticType.PHONE,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^first_?name$|^fname$|^given_?name$",
        semantic_type=SemanticType.FIRST_NAME,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^last_?name$|^lname$|^surname$|^family_?name$",
        semantic_type=SemanticType.LAST_NAME,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^full_?name$|^display_?name$",
        semantic_type=SemanticType.FULL_NAME,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^name$",
        semantic_type=SemanticType.NAME,
        confidence_boost=0.3,
    ),
    NamePattern(
        pattern=r"user_?name|login|handle",
        semantic_type=SemanticType.USERNAME,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"password|passwd|pwd|pass_hash|password_hash",
        semantic_type=SemanticType.PASSWORD_HASH,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"ssn|social_security|sin$",
        semantic_type=SemanticType.SSN,
        confidence_boost=0.6,
    ),
    NamePattern(
        pattern=r"dob|birth_?date|date_?of_?birth|birthday",
        semantic_type=SemanticType.DATE_OF_BIRTH,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^age$|^user_age$",
        semantic_type=SemanticType.AGE,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^gender$|^sex$",
        semantic_type=SemanticType.GENDER,
        confidence_boost=0.5,
    ),

    # Temporal
    NamePattern(
        pattern=r"created_?(at|on|date|time)|date_?created|insert_?(date|time)",
        semantic_type=SemanticType.CREATED_AT,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"updated_?(at|on|date|time)|modified_?(at|on|date|time)|last_?update",
        semantic_type=SemanticType.UPDATED_AT,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"deleted_?(at|on|date|time)|removed_?(at|on)",
        semantic_type=SemanticType.DELETED_AT,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"expir(es?|ed|ation)|valid_?until",
        semantic_type=SemanticType.EXPIRED_AT,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"start_?(date|time)|begin_?(date|time)|from_?(date|time)",
        semantic_type=SemanticType.START_DATE,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"end_?(date|time)|finish_?(date|time)|to_?(date|time)",
        semantic_type=SemanticType.END_DATE,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"^year$|_year$",
        semantic_type=SemanticType.YEAR,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"^month$|_month$",
        semantic_type=SemanticType.MONTH,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"^day$|_day$|day_of_",
        semantic_type=SemanticType.DAY,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"duration|elapsed|time_spent",
        semantic_type=SemanticType.DURATION,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"timezone|tz$|time_zone",
        semantic_type=SemanticType.TIMEZONE,
        confidence_boost=0.5,
    ),

    # Financial
    NamePattern(
        pattern=r"price|cost|amount|fee|charge|total|subtotal",
        semantic_type=SemanticType.PRICE,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"currency|ccy",
        semantic_type=SemanticType.CURRENCY_CODE,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"quantity|qty|count|num_",
        semantic_type=SemanticType.QUANTITY,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"percent|pct|rate",
        semantic_type=SemanticType.PERCENTAGE,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"credit_?card|cc_?num|card_?number",
        semantic_type=SemanticType.CREDIT_CARD,
        confidence_boost=0.6,
    ),
    NamePattern(
        pattern=r"tax|vat|gst",
        semantic_type=SemanticType.TAX,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"discount|promo",
        semantic_type=SemanticType.DISCOUNT,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"revenue|sales|income",
        semantic_type=SemanticType.REVENUE,
        confidence_boost=0.4,
    ),

    # Geographic
    NamePattern(
        pattern=r"address|addr$|street_?address",
        semantic_type=SemanticType.ADDRESS,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"address_?1|addr_?1|street_?1|line_?1",
        semantic_type=SemanticType.ADDRESS_LINE_1,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"address_?2|addr_?2|street_?2|line_?2|apt|suite|unit",
        semantic_type=SemanticType.ADDRESS_LINE_2,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^city$|_city$|town",
        semantic_type=SemanticType.CITY,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^state$|_state$|province|region",
        semantic_type=SemanticType.STATE,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"country(?!_code)|nation",
        semantic_type=SemanticType.COUNTRY,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"country_?code|iso_?country",
        semantic_type=SemanticType.COUNTRY_CODE,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"zip|zip_?code|postal|postcode",
        semantic_type=SemanticType.ZIP_CODE,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"lat(?:itude)?$|^lat$|_lat$",
        semantic_type=SemanticType.LATITUDE,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"lon(?:gitude)?$|lng$|^lon$|_lon$|_lng$",
        semantic_type=SemanticType.LONGITUDE,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"ip_?addr|ip_?address|client_?ip|remote_?ip",
        semantic_type=SemanticType.IP_ADDRESS,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"mac_?addr|mac_?address|hardware_?addr",
        semantic_type=SemanticType.MAC_ADDRESS,
        confidence_boost=0.5,
    ),

    # Status
    NamePattern(
        pattern=r"^status$|_status$|state$",
        semantic_type=SemanticType.STATUS,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"^type$|_type$|^kind$|_kind$",
        semantic_type=SemanticType.TYPE,
        confidence_boost=0.3,
    ),
    NamePattern(
        pattern=r"category|cat$|_cat$",
        semantic_type=SemanticType.CATEGORY,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"priority|prio$",
        semantic_type=SemanticType.PRIORITY,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^is_|^has_|^can_|^should_|^was_|^did_",
        semantic_type=SemanticType.BOOLEAN,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"is_?active|active$|enabled$",
        semantic_type=SemanticType.IS_ACTIVE,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"is_?deleted|deleted$|removed$",
        semantic_type=SemanticType.IS_DELETED,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"is_?verified|verified$|confirmed$",
        semantic_type=SemanticType.IS_VERIFIED,
        confidence_boost=0.5,
    ),

    # Measurement
    NamePattern(
        pattern=r"^count$|_count$|num_|number_of",
        semantic_type=SemanticType.COUNT,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"^total$|_total$|sum_|grand_",
        semantic_type=SemanticType.TOTAL,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"^avg$|average|mean$",
        semantic_type=SemanticType.AVERAGE,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"weight|^wt$|_wt$|^mass$",
        semantic_type=SemanticType.WEIGHT,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"height|^ht$|_ht$",
        semantic_type=SemanticType.HEIGHT,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"score|points|grade",
        semantic_type=SemanticType.SCORE,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"rating|stars|rank",
        semantic_type=SemanticType.RATING,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"version|ver$|_ver$|revision",
        semantic_type=SemanticType.VERSION,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"sequence|seq$|_seq$|order$|sort_?order",
        semantic_type=SemanticType.SEQUENCE,
        confidence_boost=0.4,
    ),

    # Text
    NamePattern(
        pattern=r"^title$|_title$|headline",
        semantic_type=SemanticType.TITLE,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"description|desc$|_desc$",
        semantic_type=SemanticType.DESCRIPTION,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"summary|abstract|overview",
        semantic_type=SemanticType.SUMMARY,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"content|body|text$|_text$",
        semantic_type=SemanticType.CONTENT,
        confidence_boost=0.3,
    ),
    NamePattern(
        pattern=r"comment|note|remark|memo",
        semantic_type=SemanticType.COMMENT,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"message|msg$",
        semantic_type=SemanticType.MESSAGE,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"^url$|_url$|link|href|endpoint",
        semantic_type=SemanticType.URL,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^path$|_path$|file_?path|dir_?path",
        semantic_type=SemanticType.PATH,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"filename|file_?name|original_?name",
        semantic_type=SemanticType.FILENAME,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"mime|content_?type|media_?type",
        semantic_type=SemanticType.MIME_TYPE,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^tags?$|_tags?$|keywords?$",
        semantic_type=SemanticType.TAG,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"label|badge",
        semantic_type=SemanticType.LABEL,
        confidence_boost=0.4,
    ),

    # Binary
    NamePattern(
        pattern=r"image|img$|photo|picture|avatar|thumbnail|icon",
        semantic_type=SemanticType.IMAGE,
        confidence_boost=0.4,
    ),
    NamePattern(
        pattern=r"file|document|attachment|blob$",
        semantic_type=SemanticType.FILE,
        confidence_boost=0.3,
    ),
    NamePattern(
        pattern=r"^hash$|_hash$|checksum|digest|md5|sha",
        semantic_type=SemanticType.HASH,
        confidence_boost=0.5,
    ),

    # Technical
    NamePattern(
        pattern=r"api_?key|access_?key|secret_?key",
        semantic_type=SemanticType.API_KEY,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"^secret$|_secret$|client_?secret",
        semantic_type=SemanticType.SECRET,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"token|jwt|bearer|auth_?token|access_?token|refresh_?token",
        semantic_type=SemanticType.TOKEN,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"session_?id|sess_?id",
        semantic_type=SemanticType.SESSION_ID,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"correlation_?id|corr_?id|request_?id|req_?id",
        semantic_type=SemanticType.CORRELATION_ID,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"trace_?id|span_?id",
        semantic_type=SemanticType.TRACE_ID,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"user_?agent|ua$",
        semantic_type=SemanticType.USER_AGENT,
        confidence_boost=0.5,
    ),
    NamePattern(
        pattern=r"referrer|referer",
        semantic_type=SemanticType.REFERRER,
        confidence_boost=0.5,
    ),
]


class DataSensitivity(str, Enum):
    """Data sensitivity classification levels."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class TypeInferenceResult(BaseModel):
    """
    Result of semantic type inference for a column.

    Attributes:
        semantic_type: The inferred semantic type.
        category: The semantic category.
        confidence: Confidence score (0.0 to 1.0).
        is_pii: Whether this is PII data.
        is_sensitive: Whether this is sensitive data.
        sensitivity_level: Data sensitivity classification.
        matched_patterns: Patterns that contributed to inference.
        inference_method: How the type was inferred.
    """

    model_config = ConfigDict(frozen=True)

    semantic_type: SemanticType = Field(
        ...,
        description="Inferred semantic type"
    )
    category: SemanticCategory = Field(
        ...,
        description="Semantic category"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score"
    )
    is_pii: bool = Field(
        default=False,
        description="Is personally identifiable information"
    )
    is_sensitive: bool = Field(
        default=False,
        description="Is sensitive data"
    )
    sensitivity_level: DataSensitivity = Field(
        default=DataSensitivity.INTERNAL,
        description="Data sensitivity level"
    )
    matched_patterns: List[str] = Field(
        default_factory=list,
        description="Patterns that matched"
    )
    inference_method: str = Field(
        default="unknown",
        description="Method used for inference"
    )


def get_category(semantic_type: SemanticType) -> SemanticCategory:
    """
    Get the category for a semantic type.

    Args:
        semantic_type: The semantic type to categorize.

    Returns:
        The corresponding semantic category.
    """
    return SEMANTIC_TYPE_CATEGORIES.get(semantic_type, SemanticCategory.UNKNOWN)


def is_pii(semantic_type: SemanticType) -> bool:
    """
    Check if a semantic type represents PII.

    Args:
        semantic_type: The semantic type to check.

    Returns:
        True if the type represents PII.
    """
    return semantic_type in PII_TYPES


def is_sensitive(semantic_type: SemanticType) -> bool:
    """
    Check if a semantic type represents sensitive data.

    Args:
        semantic_type: The semantic type to check.

    Returns:
        True if the type represents sensitive data.
    """
    return semantic_type in SENSITIVE_TYPES


def get_sensitivity_level(semantic_type: SemanticType) -> DataSensitivity:
    """
    Get the sensitivity level for a semantic type.

    Args:
        semantic_type: The semantic type to evaluate.

    Returns:
        The data sensitivity level.
    """
    if semantic_type in {
        SemanticType.SSN,
        SemanticType.CREDIT_CARD,
        SemanticType.PASSWORD_HASH,
        SemanticType.API_KEY,
        SemanticType.SECRET,
    }:
        return DataSensitivity.RESTRICTED

    if semantic_type in PII_TYPES:
        return DataSensitivity.CONFIDENTIAL

    if semantic_type in SENSITIVE_TYPES:
        return DataSensitivity.CONFIDENTIAL

    if semantic_type in {
        SemanticType.TOKEN,
        SemanticType.SESSION_ID,
        SemanticType.IP_ADDRESS,
    }:
        return DataSensitivity.INTERNAL

    return DataSensitivity.PUBLIC


def infer_semantic_type(
    column_name: str,
    database_type: str,
    is_primary_key: bool = False,
    is_foreign_key: bool = False,
    sample_values: Optional[List[str]] = None,
    patterns: Optional[List[NamePattern]] = None,
) -> TypeInferenceResult:
    """
    Infer the semantic type of a column.

    Uses column name patterns, database type, constraint information,
    and optionally sample values to infer the semantic type.

    Args:
        column_name: Name of the column.
        database_type: Database type of the column.
        is_primary_key: Whether column is a primary key.
        is_foreign_key: Whether column is a foreign key.
        sample_values: Optional sample values for validation.
        patterns: Optional custom patterns (uses defaults if not provided).

    Returns:
        TypeInferenceResult with inferred type and metadata.
    """
    patterns = patterns or DEFAULT_NAME_PATTERNS

    # Start with default
    best_type = SemanticType.UNKNOWN
    best_confidence = 0.0
    matched = []
    method = "default"

    # Check for PK/FK first
    if is_primary_key:
        best_type = SemanticType.PRIMARY_KEY
        best_confidence = 0.9
        method = "constraint"
    elif is_foreign_key:
        best_type = SemanticType.FOREIGN_KEY
        best_confidence = 0.9
        method = "constraint"

    # Apply name patterns
    for pattern in patterns:
        if pattern.matches(column_name):
            new_confidence = min(1.0, best_confidence + pattern.confidence_boost)
            # Prefer higher confidence or non-generic types
            if (
                new_confidence > best_confidence
                or (best_type in {SemanticType.PRIMARY_KEY, SemanticType.FOREIGN_KEY}
                    and pattern.semantic_type not in {SemanticType.PRIMARY_KEY, SemanticType.FOREIGN_KEY})
            ):
                # Don't override PK/FK with lower confidence matches
                if not (is_primary_key or is_foreign_key) or new_confidence > 0.7:
                    best_type = pattern.semantic_type
                    best_confidence = new_confidence
                    method = "name_pattern"
            matched.append(pattern.pattern)

    # Apply database type inference if still unknown
    if best_type == SemanticType.UNKNOWN:
        base_type = database_type.lower().split("(")[0].strip()

        if base_type in {"boolean", "bool"}:
            best_type = SemanticType.BOOLEAN
            best_confidence = 0.7
            method = "database_type"
        elif base_type == "uuid":
            best_type = SemanticType.UUID
            best_confidence = 0.8
            method = "database_type"
        elif base_type in {"json", "jsonb"}:
            best_type = SemanticType.JSON
            best_confidence = 0.8
            method = "database_type"
        elif base_type == "xml":
            best_type = SemanticType.XML
            best_confidence = 0.8
            method = "database_type"
        elif base_type in {"bytea"}:
            best_type = SemanticType.BLOB
            best_confidence = 0.6
            method = "database_type"
        elif base_type in {"inet", "cidr"}:
            best_type = SemanticType.IP_ADDRESS
            best_confidence = 0.8
            method = "database_type"
        elif base_type in {"macaddr", "macaddr8"}:
            best_type = SemanticType.MAC_ADDRESS
            best_confidence = 0.9
            method = "database_type"
        elif base_type in {"timestamp", "timestamptz"}:
            best_type = SemanticType.TIMESTAMP
            best_confidence = 0.6
            method = "database_type"
        elif base_type == "date":
            best_type = SemanticType.DATE
            best_confidence = 0.6
            method = "database_type"
        elif base_type in {"time", "timetz"}:
            best_type = SemanticType.TIME
            best_confidence = 0.6
            method = "database_type"
        elif base_type == "interval":
            best_type = SemanticType.DURATION
            best_confidence = 0.6
            method = "database_type"

    # Determine category and sensitivity
    category = get_category(best_type)
    pii = is_pii(best_type)
    sensitive = is_sensitive(best_type)
    sensitivity = get_sensitivity_level(best_type)

    return TypeInferenceResult(
        semantic_type=best_type,
        category=category,
        confidence=best_confidence,
        is_pii=pii,
        is_sensitive=sensitive,
        sensitivity_level=sensitivity,
        matched_patterns=matched,
        inference_method=method,
    )
