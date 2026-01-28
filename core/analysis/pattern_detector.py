"""
Pattern detector for identifying data patterns in column values.

This module provides comprehensive pattern detection for:
- Contact info: email, phone, URL
- Identifiers: UUID, SSN, credit card, IP address
- Dates: ISO, US, EU formats
- Codes: zip/postal, currency, percentage
- Technical: JSON, XML, slug, MAC address

Example usage:
    >>> detector = PatternDetector()
    >>> values = ["user@example.com", "admin@test.org", "info@company.io"]
    >>> matches = detector.detect_patterns(values)
    >>> print(matches[0].pattern_type)  # PatternType.EMAIL
    >>> print(matches[0].match_percentage)  # 100.0

    >>> best = detector.get_best_match(values)
    >>> print(best.pattern_type)  # PatternType.EMAIL
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from core.models.analysis import PatternType, PatternMatch, ConfidenceLevel


@dataclass
class PatternDefinition:
    """
    Definition of a pattern with its regex and metadata.

    Attributes:
        pattern_type: The type of pattern this definition describes.
        regex: Compiled regular expression for matching.
        description: Human-readable description of the pattern.
        examples: Example values that match this pattern.
        min_confidence_threshold: Minimum match percentage for confident detection.
        priority: Priority for pattern selection (lower = higher priority).
        is_sensitive: Whether this pattern may contain sensitive/PII data.
    """
    pattern_type: PatternType
    regex: re.Pattern
    description: str
    examples: List[str] = field(default_factory=list)
    min_confidence_threshold: float = 0.8
    priority: int = 100
    is_sensitive: bool = False


# Comprehensive pattern definitions (18+ patterns)
PATTERN_DEFINITIONS: Dict[PatternType, PatternDefinition] = {
    # Contact Information Patterns
    PatternType.EMAIL: PatternDefinition(
        pattern_type=PatternType.EMAIL,
        regex=re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        ),
        description="Email address (RFC 5322 simplified)",
        examples=["user@example.com", "name.last@domain.co.uk", "test+label@gmail.com"],
        min_confidence_threshold=0.8,
        priority=10,
        is_sensitive=True,
    ),
    PatternType.PHONE: PatternDefinition(
        pattern_type=PatternType.PHONE,
        regex=re.compile(
            r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]{6,}$'
        ),
        description="Phone number (international and domestic formats)",
        examples=[
            "+1-234-567-8900",
            "(123) 456-7890",
            "+44 20 7123 4567",
            "555.123.4567",
        ],
        min_confidence_threshold=0.75,
        priority=15,
        is_sensitive=True,
    ),
    PatternType.URL: PatternDefinition(
        pattern_type=PatternType.URL,
        regex=re.compile(
            r'^https?://[^\s/$.?#].[^\s]*$',
            re.IGNORECASE
        ),
        description="HTTP/HTTPS URL",
        examples=[
            "https://example.com",
            "http://sub.domain.org/path?q=1",
            "https://api.service.io/v2/resource",
        ],
        min_confidence_threshold=0.85,
        priority=20,
    ),

    # Identifier Patterns
    PatternType.UUID: PatternDefinition(
        pattern_type=PatternType.UUID,
        regex=re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
            re.IGNORECASE
        ),
        description="UUID (versions 1-5)",
        examples=[
            "550e8400-e29b-41d4-a716-446655440000",
            "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        ],
        min_confidence_threshold=0.9,
        priority=5,
    ),
    PatternType.IP_ADDRESS: PatternDefinition(
        pattern_type=PatternType.IP_ADDRESS,
        regex=re.compile(
            r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        ),
        description="IPv4 address",
        examples=["192.168.1.1", "10.0.0.255", "8.8.8.8"],
        min_confidence_threshold=0.9,
        priority=25,
    ),
    PatternType.MAC_ADDRESS: PatternDefinition(
        pattern_type=PatternType.MAC_ADDRESS,
        regex=re.compile(
            r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        ),
        description="MAC address (colon or hyphen separated)",
        examples=["00:1A:2B:3C:4D:5E", "00-1A-2B-3C-4D-5E"],
        min_confidence_threshold=0.9,
        priority=30,
    ),

    # Sensitive Data Patterns
    PatternType.CREDIT_CARD: PatternDefinition(
        pattern_type=PatternType.CREDIT_CARD,
        regex=re.compile(
            r'^(?:4[0-9]{12}(?:[0-9]{3})?'  # Visa
            r'|5[1-5][0-9]{14}'              # MasterCard
            r'|3[47][0-9]{13}'               # American Express
            r'|6(?:011|5[0-9]{2})[0-9]{12}'  # Discover
            r'|(?:2131|1800|35\d{3})\d{11})$'  # JCB
        ),
        description="Credit card number (Visa, MC, Amex, Discover, JCB)",
        examples=["4111111111111111", "5500000000000004", "378282246310005"],
        min_confidence_threshold=0.95,
        priority=1,
        is_sensitive=True,
    ),
    PatternType.SSN: PatternDefinition(
        pattern_type=PatternType.SSN,
        regex=re.compile(
            r'^(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}$'
        ),
        description="US Social Security Number (with validation rules)",
        examples=["123-45-6789", "078-05-1120"],
        min_confidence_threshold=0.95,
        priority=2,
        is_sensitive=True,
    ),

    # Date Patterns
    PatternType.DATE_ISO: PatternDefinition(
        pattern_type=PatternType.DATE_ISO,
        regex=re.compile(
            r'^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])$'
        ),
        description="ISO 8601 date (YYYY-MM-DD)",
        examples=["2024-01-15", "1999-12-31", "2000-02-29"],
        min_confidence_threshold=0.85,
        priority=35,
    ),
    PatternType.DATE_US: PatternDefinition(
        pattern_type=PatternType.DATE_US,
        regex=re.compile(
            r'^(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12][0-9]|3[01])/(?:\d{2}|\d{4})$'
        ),
        description="US date format (MM/DD/YYYY or MM/DD/YY)",
        examples=["01/15/2024", "12/31/99", "1/5/2024"],
        min_confidence_threshold=0.8,
        priority=40,
    ),
    PatternType.DATE_EU: PatternDefinition(
        pattern_type=PatternType.DATE_EU,
        regex=re.compile(
            r'^(?:0?[1-9]|[12][0-9]|3[01])/(?:0?[1-9]|1[0-2])/(?:\d{2}|\d{4})$'
        ),
        description="EU date format (DD/MM/YYYY or DD/MM/YY)",
        examples=["15/01/2024", "31/12/99", "5/1/2024"],
        min_confidence_threshold=0.8,
        priority=41,
    ),

    # Code Patterns
    PatternType.ZIP_CODE: PatternDefinition(
        pattern_type=PatternType.ZIP_CODE,
        regex=re.compile(
            r'^(?:\d{5}(?:-\d{4})?'  # US ZIP
            r'|[A-Z]\d[A-Z]\s?\d[A-Z]\d)$',  # Canadian postal
            re.IGNORECASE
        ),
        description="US ZIP code or Canadian postal code",
        examples=["12345", "12345-6789", "K1A 0B1", "M5V3L9"],
        min_confidence_threshold=0.85,
        priority=50,
    ),
    PatternType.CURRENCY: PatternDefinition(
        pattern_type=PatternType.CURRENCY,
        regex=re.compile(
            r'^(?:[$\u20AC\u00A3\u00A5]?\s*-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?'
            r'|-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?\s*[$\u20AC\u00A3\u00A5]?)$'
        ),
        description="Currency amount with optional symbol ($, EUR, GBP, JPY)",
        examples=["$1,234.56", "1234.56", "1,234", "$99.99", "-$50.00"],
        min_confidence_threshold=0.75,
        priority=55,
    ),
    PatternType.PERCENTAGE: PatternDefinition(
        pattern_type=PatternType.PERCENTAGE,
        regex=re.compile(
            r'^-?\d+(?:\.\d+)?%$'
        ),
        description="Percentage value",
        examples=["50%", "99.9%", "-5.5%", "100%", "0.01%"],
        min_confidence_threshold=0.9,
        priority=60,
    ),

    # Technical Patterns
    PatternType.JSON: PatternDefinition(
        pattern_type=PatternType.JSON,
        regex=re.compile(
            r'^[\[\{].*[\]\}]$',
            re.DOTALL
        ),
        description="JSON object or array",
        examples=['{"key": "value"}', '[1, 2, 3]', '{"nested": {"a": 1}}'],
        min_confidence_threshold=0.8,
        priority=70,
    ),
    PatternType.SLUG: PatternDefinition(
        pattern_type=PatternType.SLUG,
        regex=re.compile(
            r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
        ),
        description="URL slug (lowercase alphanumeric with hyphens)",
        examples=["hello-world", "my-blog-post", "product-123"],
        min_confidence_threshold=0.85,
        priority=75,
    ),

    # Identifier Patterns
    PatternType.NUMERIC_ID: PatternDefinition(
        pattern_type=PatternType.NUMERIC_ID,
        regex=re.compile(
            r'^\d+$'
        ),
        description="Numeric identifier (digits only)",
        examples=["12345", "1", "999999"],
        min_confidence_threshold=0.95,
        priority=80,
    ),
    PatternType.ALPHANUMERIC_CODE: PatternDefinition(
        pattern_type=PatternType.ALPHANUMERIC_CODE,
        regex=re.compile(
            r'^[A-Z0-9]{2,}(?:[-_][A-Z0-9]+)*$',
            re.IGNORECASE
        ),
        description="Alphanumeric code (SKU, product code, etc.)",
        examples=["ABC-123", "SKU_001", "PROD123", "A1B2C3"],
        min_confidence_threshold=0.85,
        priority=85,
    ),
}


# Additional pattern regexes that can be used for custom patterns
ADDITIONAL_PATTERNS = {
    "ipv6": re.compile(
        r'^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
        r'|^(?:[0-9a-fA-F]{1,4}:){1,7}:$'
        r'|^(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}$'
        r'|^::(?:ffff:)?(?:\d{1,3}\.){3}\d{1,3}$'
    ),
    "hex_color": re.compile(
        r'^#?([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
    ),
    "time_12h": re.compile(
        r'^(?:0?[1-9]|1[0-2]):[0-5][0-9](?::[0-5][0-9])?\s?(?:[AaPp][Mm])$'
    ),
    "time_24h": re.compile(
        r'^(?:[01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$'
    ),
    "iso_datetime": re.compile(
        r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$'
    ),
    "semantic_version": re.compile(
        r'^v?\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?(?:\+[a-zA-Z0-9.]+)?$'
    ),
    "vin": re.compile(
        r'^[A-HJ-NPR-Z0-9]{17}$'
    ),
    "isbn_10": re.compile(
        r'^(?:\d[- ]?){9}[\dXx]$'
    ),
    "isbn_13": re.compile(
        r'^(?:97[89][- ]?)?(?:\d[- ]?){9}\d$'
    ),
    "base64": re.compile(
        r'^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$'
    ),
    "md5_hash": re.compile(
        r'^[a-fA-F0-9]{32}$'
    ),
    "sha256_hash": re.compile(
        r'^[a-fA-F0-9]{64}$'
    ),
}


class PatternDetector:
    """
    Detects data patterns in column values.

    This class provides comprehensive pattern detection capabilities including:
    - Batch detection across multiple pattern types
    - Single value pattern checking
    - Best match selection with confidence thresholds
    - Support for custom patterns
    - Sensitive data detection

    Example usage:
        >>> detector = PatternDetector()
        >>>
        >>> # Detect all patterns in a list of values
        >>> values = ["user@example.com", "admin@test.org", None, "info@company.io"]
        >>> matches = detector.detect_patterns(values)
        >>> for match in matches:
        ...     print(f"{match.pattern_type}: {match.match_percentage}%")
        ...
        EMAIL: 100.0%

        >>> # Get the best matching pattern
        >>> best = detector.get_best_match(values)
        >>> print(best.pattern_type)
        EMAIL

        >>> # Check a single value
        >>> patterns = detector.detect_single_value("192.168.1.1")
        >>> print(patterns)
        [<PatternType.IP_ADDRESS: 'ip_address'>]

        >>> # Validate against a specific pattern
        >>> is_valid = detector.validate_pattern("test@example.com", PatternType.EMAIL)
        >>> print(is_valid)
        True

    Attributes:
        patterns: Dictionary of pattern definitions keyed by PatternType.
    """

    def __init__(
        self,
        custom_patterns: Optional[Dict[PatternType, PatternDefinition]] = None,
        exclude_patterns: Optional[List[PatternType]] = None,
    ):
        """
        Initialize the pattern detector.

        Args:
            custom_patterns: Additional custom pattern definitions to include.
                These will override built-in patterns if keys match.
            exclude_patterns: List of pattern types to exclude from detection.
                Useful for performance optimization when certain patterns
                are not relevant.

        Example:
            >>> # Use only specific patterns
            >>> detector = PatternDetector(
            ...     exclude_patterns=[PatternType.NUMERIC_ID, PatternType.JSON]
            ... )

            >>> # Add custom pattern
            >>> from dataclasses import dataclass
            >>> custom = {
            ...     PatternType.ALPHANUMERIC_CODE: PatternDefinition(
            ...         pattern_type=PatternType.ALPHANUMERIC_CODE,
            ...         regex=re.compile(r'^CUSTOM-[0-9]{4}$'),
            ...         description="Custom code format",
            ...         examples=["CUSTOM-0001"],
            ...     )
            ... }
            >>> detector = PatternDetector(custom_patterns=custom)
        """
        self.patterns = dict(PATTERN_DEFINITIONS)

        if custom_patterns:
            self.patterns.update(custom_patterns)

        if exclude_patterns:
            for pattern_type in exclude_patterns:
                self.patterns.pop(pattern_type, None)

    def detect_patterns(
        self,
        values: List[Any],
        min_match_percentage: float = 50.0,
        include_sensitive: bool = True,
    ) -> List[PatternMatch]:
        """
        Detect all matching patterns in a list of values.

        Analyzes the provided values against all configured patterns and
        returns matches that meet the minimum match percentage threshold.

        Args:
            values: List of values to analyze. None values and empty strings
                are automatically filtered out.
            min_match_percentage: Minimum percentage of values that must match
                a pattern for it to be included in results. Range: 0-100.
            include_sensitive: Whether to include sensitive patterns like
                SSN and credit card. Set to False to skip these for
                performance or compliance reasons.

        Returns:
            List of PatternMatch objects sorted by match percentage (descending).
            Each match includes:
            - pattern_type: The detected pattern type
            - match_count: Number of values matching the pattern
            - total_count: Total non-null values checked
            - match_percentage: Percentage of matches (0-100)
            - confidence: HIGH/MEDIUM/LOW based on match percentage
            - sample_matches: Up to 5 example matching values

        Example:
            >>> detector = PatternDetector()
            >>> values = [
            ...     "user@example.com",
            ...     "admin@test.org",
            ...     None,
            ...     "invalid-email",
            ...     "info@company.io"
            ... ]
            >>> matches = detector.detect_patterns(values, min_match_percentage=60)
            >>> print(len(matches))
            1
            >>> print(matches[0].pattern_type)
            PatternType.EMAIL
            >>> print(matches[0].match_percentage)
            75.0
        """
        if not values:
            return []

        # Filter out None/null values and empty strings
        non_null_values = [
            v for v in values
            if v is not None and str(v).strip()
        ]

        if not non_null_values:
            return []

        matches = []
        total = len(non_null_values)

        for pattern_type, definition in self.patterns.items():
            # Skip sensitive patterns if requested
            if not include_sensitive and definition.is_sensitive:
                continue

            match_count = 0
            sample_matches: List[str] = []

            for value in non_null_values:
                str_value = str(value).strip()
                if definition.regex.match(str_value):
                    match_count += 1
                    if len(sample_matches) < 5:
                        sample_matches.append(str_value)

            if match_count > 0:
                match_pct = (match_count / total) * 100

                if match_pct >= min_match_percentage:
                    confidence = self._calculate_confidence(match_pct, definition)

                    matches.append(PatternMatch(
                        pattern_type=pattern_type,
                        match_count=match_count,
                        total_count=total,
                        match_percentage=round(match_pct, 2),
                        confidence=confidence,
                        sample_matches=sample_matches,
                    ))

        # Sort by priority first (lower = higher priority), then by match percentage
        matches.sort(
            key=lambda m: (
                -m.match_percentage,
                self.patterns[m.pattern_type].priority
            )
        )

        return matches

    def get_best_match(
        self,
        values: List[Any],
        min_confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
        min_match_percentage: float = 50.0,
    ) -> Optional[PatternMatch]:
        """
        Get the best matching pattern for a list of values.

        Returns the highest-confidence pattern match that meets the
        specified thresholds, or None if no pattern qualifies.

        Args:
            values: List of values to analyze.
            min_confidence: Minimum confidence level required for a match.
                Patterns below this confidence are excluded.
            min_match_percentage: Minimum percentage of values that must match.

        Returns:
            The best PatternMatch object, or None if no confident match exists.

        Example:
            >>> detector = PatternDetector()
            >>> values = ["user@example.com", "admin@test.org", "info@company.io"]
            >>> best = detector.get_best_match(values, min_confidence=ConfidenceLevel.HIGH)
            >>> if best:
            ...     print(f"Best pattern: {best.pattern_type}")
            ...     print(f"Confidence: {best.confidence}")
            Best pattern: PatternType.EMAIL
            Confidence: ConfidenceLevel.HIGH
        """
        matches = self.detect_patterns(values, min_match_percentage=min_match_percentage)

        confidence_order = {
            ConfidenceLevel.HIGH: 3,
            ConfidenceLevel.MEDIUM: 2,
            ConfidenceLevel.LOW: 1,
        }
        min_level = confidence_order.get(min_confidence, 2)

        for match in matches:
            match_level = confidence_order.get(match.confidence, 0)
            if match_level >= min_level:
                return match

        return None

    def detect_single_value(self, value: Any) -> List[PatternType]:
        """
        Detect which patterns a single value matches.

        Useful for quick validation or classification of individual values
        without the overhead of batch processing.

        Args:
            value: Single value to check against all patterns.

        Returns:
            List of PatternTypes that match the value, sorted by priority.

        Example:
            >>> detector = PatternDetector()
            >>> patterns = detector.detect_single_value("550e8400-e29b-41d4-a716-446655440000")
            >>> print(patterns)
            [<PatternType.UUID: 'uuid'>]

            >>> patterns = detector.detect_single_value("12345")
            >>> print(patterns)
            [<PatternType.ZIP_CODE: 'zip_code'>, <PatternType.NUMERIC_ID: 'numeric_id'>]
        """
        if value is None:
            return []

        str_value = str(value).strip()
        if not str_value:
            return []

        matching_types = []
        for pattern_type, definition in self.patterns.items():
            if definition.regex.match(str_value):
                matching_types.append((pattern_type, definition.priority))

        # Sort by priority (lower = higher priority)
        matching_types.sort(key=lambda x: x[1])

        return [pt for pt, _ in matching_types]

    def detect_sensitive_data(self, values: List[Any]) -> List[PatternMatch]:
        """
        Detect only sensitive data patterns (PII, financial data).

        This is a convenience method for compliance and security scanning.
        It only checks patterns marked as sensitive (SSN, credit card, email, phone).

        Args:
            values: List of values to scan for sensitive data.

        Returns:
            List of PatternMatch objects for sensitive patterns found.

        Example:
            >>> detector = PatternDetector()
            >>> values = ["123-45-6789", "user@example.com", "regular text"]
            >>> sensitive = detector.detect_sensitive_data(values)
            >>> for match in sensitive:
            ...     print(f"ALERT: {match.pattern_type} detected!")
            ALERT: PatternType.SSN detected!
            ALERT: PatternType.EMAIL detected!
        """
        if not values:
            return []

        non_null_values = [
            v for v in values
            if v is not None and str(v).strip()
        ]

        if not non_null_values:
            return []

        matches = []
        total = len(non_null_values)

        # Only check sensitive patterns
        sensitive_patterns = {
            pt: defn for pt, defn in self.patterns.items()
            if defn.is_sensitive
        }

        for pattern_type, definition in sensitive_patterns.items():
            match_count = 0
            sample_matches: List[str] = []

            for value in non_null_values:
                str_value = str(value).strip()
                if definition.regex.match(str_value):
                    match_count += 1
                    if len(sample_matches) < 5:
                        # Mask sensitive samples
                        masked = self._mask_sensitive_value(str_value, pattern_type)
                        sample_matches.append(masked)

            if match_count > 0:
                match_pct = (match_count / total) * 100
                confidence = self._calculate_confidence(match_pct, definition)

                matches.append(PatternMatch(
                    pattern_type=pattern_type,
                    match_count=match_count,
                    total_count=total,
                    match_percentage=round(match_pct, 2),
                    confidence=confidence,
                    sample_matches=sample_matches,
                ))

        matches.sort(key=lambda m: -m.match_percentage)
        return matches

    def _mask_sensitive_value(self, value: str, pattern_type: PatternType) -> str:
        """Mask sensitive values for safe logging/display."""
        if pattern_type == PatternType.SSN:
            # Show only last 4 digits: ***-**-1234
            return f"***-**-{value[-4:]}"
        elif pattern_type == PatternType.CREDIT_CARD:
            # Show only last 4 digits: ************1234
            return f"{'*' * (len(value) - 4)}{value[-4:]}"
        elif pattern_type == PatternType.EMAIL:
            # Mask part of email: u***@example.com
            parts = value.split('@')
            if len(parts) == 2 and len(parts[0]) > 1:
                return f"{parts[0][0]}***@{parts[1]}"
            return value
        elif pattern_type == PatternType.PHONE:
            # Show only last 4 digits: ***-***-1234
            digits = ''.join(c for c in value if c.isdigit())
            if len(digits) >= 4:
                return f"***-***-{digits[-4:]}"
            return value
        return value

    def _calculate_confidence(
        self,
        match_percentage: float,
        definition: PatternDefinition,
    ) -> ConfidenceLevel:
        """
        Calculate confidence level based on match percentage and pattern threshold.

        The confidence calculation considers both the raw match percentage
        and the pattern-specific minimum threshold for confident detection.

        Args:
            match_percentage: Percentage of values matching (0-100).
            definition: Pattern definition with threshold configuration.

        Returns:
            ConfidenceLevel (HIGH, MEDIUM, or LOW).
        """
        threshold = definition.min_confidence_threshold * 100

        if match_percentage >= 95:
            return ConfidenceLevel.HIGH
        elif match_percentage >= threshold:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def validate_pattern(
        self,
        value: Any,
        pattern_type: PatternType,
    ) -> bool:
        """
        Check if a value matches a specific pattern.

        Use this for direct validation against a known expected pattern type.

        Args:
            value: Value to validate.
            pattern_type: Pattern to validate against.

        Returns:
            True if the value matches the pattern, False otherwise.

        Example:
            >>> detector = PatternDetector()
            >>> detector.validate_pattern("test@example.com", PatternType.EMAIL)
            True
            >>> detector.validate_pattern("not-an-email", PatternType.EMAIL)
            False
            >>> detector.validate_pattern("192.168.1.1", PatternType.IP_ADDRESS)
            True
        """
        if value is None:
            return False

        if pattern_type not in self.patterns:
            return False

        str_value = str(value).strip()
        if not str_value:
            return False

        return bool(self.patterns[pattern_type].regex.match(str_value))

    def get_pattern_info(self, pattern_type: PatternType) -> Optional[PatternDefinition]:
        """
        Get information about a specific pattern.

        Args:
            pattern_type: The pattern type to get info for.

        Returns:
            PatternDefinition with regex, description, examples, etc.
            None if pattern type is not configured.

        Example:
            >>> detector = PatternDetector()
            >>> info = detector.get_pattern_info(PatternType.EMAIL)
            >>> print(info.description)
            Email address (RFC 5322 simplified)
            >>> print(info.examples)
            ['user@example.com', 'name.last@domain.co.uk', 'test+label@gmail.com']
        """
        return self.patterns.get(pattern_type)

    def list_patterns(self, include_sensitive: bool = True) -> List[PatternDefinition]:
        """
        List all configured patterns.

        Args:
            include_sensitive: Whether to include sensitive patterns in the list.

        Returns:
            List of PatternDefinition objects sorted by priority.

        Example:
            >>> detector = PatternDetector()
            >>> patterns = detector.list_patterns()
            >>> for p in patterns[:3]:
            ...     print(f"{p.pattern_type.value}: {p.description}")
        """
        patterns = list(self.patterns.values())

        if not include_sensitive:
            patterns = [p for p in patterns if not p.is_sensitive]

        patterns.sort(key=lambda p: p.priority)
        return patterns


def detect_patterns(values: List[Any], min_match_percentage: float = 50.0) -> List[PatternMatch]:
    """
    Convenience function to detect patterns without instantiating the class.

    This is a simple wrapper around PatternDetector.detect_patterns() for
    quick one-off pattern detection.

    Args:
        values: List of values to analyze.
        min_match_percentage: Minimum match percentage threshold.

    Returns:
        List of PatternMatch objects.

    Example:
        >>> from core.analysis.pattern_detector import detect_patterns
        >>> matches = detect_patterns(["user@example.com", "admin@test.org"])
        >>> print(matches[0].pattern_type)
        PatternType.EMAIL
    """
    detector = PatternDetector()
    return detector.detect_patterns(values, min_match_percentage=min_match_percentage)


def get_best_pattern(
    values: List[Any],
    min_confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
) -> Optional[PatternMatch]:
    """
    Convenience function to get the best matching pattern.

    Args:
        values: List of values to analyze.
        min_confidence: Minimum confidence level required.

    Returns:
        Best PatternMatch or None.

    Example:
        >>> from core.analysis.pattern_detector import get_best_pattern
        >>> best = get_best_pattern(["192.168.1.1", "10.0.0.1", "8.8.8.8"])
        >>> print(best.pattern_type)
        PatternType.IP_ADDRESS
    """
    detector = PatternDetector()
    return detector.get_best_match(values, min_confidence=min_confidence)


def validate_value(value: Any, pattern_type: PatternType) -> bool:
    """
    Convenience function to validate a value against a pattern.

    Args:
        value: Value to validate.
        pattern_type: Pattern type to check against.

    Returns:
        True if value matches the pattern.

    Example:
        >>> from core.analysis.pattern_detector import validate_value
        >>> validate_value("550e8400-e29b-41d4-a716-446655440000", PatternType.UUID)
        True
    """
    detector = PatternDetector()
    return detector.validate_pattern(value, pattern_type)
