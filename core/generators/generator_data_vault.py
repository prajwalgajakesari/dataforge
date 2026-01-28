"""
Data Vault 2.0 Code Generator for DataForge.

This module generates Data Vault 2.0 schema components including:
- Hubs: Business key storage with hash keys
- Links: Relationships between business entities
- Satellites: Descriptive attributes with change tracking

Supports both raw DDL and dbt model generation using dbtvault/datavault4dbt macros.

Data Vault 2.0 Best Practices implemented:
- Hash keys for performance and distribution
- Load timestamps (LOAD_DTS) on all Raw Vault objects
- Record source (RECORD_SOURCE) for data lineage
- Hash diff (HASHDIFF) on satellites for change detection
- Ghost records for referential integrity
- Consistent naming conventions (HUB_, LNK_, SAT_ prefixes)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from core.models.schema import Table, Column, ForeignKeyRelationship
from core.models.design import ModelDesign, DesignedTable, DesignedColumn, TableRole, ColumnRole


class HashAlgorithm(str, Enum):
    """Supported hash algorithms for Data Vault hash keys."""
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"


class DataVaultLayer(str, Enum):
    """Data Vault architectural layers."""
    STAGING = "staging"
    RAW_VAULT = "raw_vault"
    BUSINESS_VAULT = "business_vault"
    INFORMATION_MART = "information_mart"


@dataclass
class Hub:
    """
    Data Vault Hub - stores unique business keys.

    Hubs are the core business entities in a Data Vault model.
    They contain the business key(s) that uniquely identify
    a business concept, along with metadata columns.

    Attributes:
        name: Hub table name (e.g., HUB_CUSTOMER).
        business_key_columns: Columns that form the business key.
        hash_key_name: Name of the hash key column (e.g., HK_CUSTOMER).
        load_timestamp_name: Name of the load timestamp column.
        record_source_name: Name of the record source column.
        source_table: Original source table name.
        description: Human-readable description.
    """
    name: str
    business_key_columns: List[Column]
    hash_key_name: str
    load_timestamp_name: str = "LOAD_DTS"
    record_source_name: str = "RECORD_SOURCE"
    source_table: Optional[str] = None
    description: Optional[str] = None

    def get_business_key_names(self) -> List[str]:
        """Return list of business key column names."""
        return [col.name for col in self.business_key_columns]


@dataclass
class Link:
    """
    Data Vault Link - represents relationships between Hubs.

    Links capture the relationships and transactions between
    business entities (Hubs). They contain hash keys from
    all connected Hubs.

    Attributes:
        name: Link table name (e.g., LNK_ORDER_CUSTOMER).
        hash_key_name: Name of the link's own hash key.
        hub_references: List of (hub_name, hub_hash_key_name) tuples.
        load_timestamp_name: Name of the load timestamp column.
        record_source_name: Name of the record source column.
        source_table: Original source table name.
        description: Human-readable description.
        is_same_as_link: Whether this is a same-as link for data quality.
        is_hierarchical: Whether this link represents a hierarchy.
    """
    name: str
    hash_key_name: str
    hub_references: List[Tuple[str, str]]  # List of (hub_name, hub_hash_key_name)
    load_timestamp_name: str = "LOAD_DTS"
    record_source_name: str = "RECORD_SOURCE"
    source_table: Optional[str] = None
    description: Optional[str] = None
    is_same_as_link: bool = False
    is_hierarchical: bool = False

    def get_hub_hash_key_names(self) -> List[str]:
        """Return list of hub hash key column names."""
        return [ref[1] for ref in self.hub_references]


@dataclass
class Satellite:
    """
    Data Vault Satellite - stores descriptive attributes.

    Satellites capture the descriptive attributes (context)
    about Hubs or Links. They track changes over time using
    HASHDIFF for change detection.

    Attributes:
        name: Satellite table name (e.g., SAT_CUSTOMER_DETAILS).
        parent_name: Name of the parent Hub or Link.
        parent_hash_key_name: Hash key column name of the parent.
        descriptive_attributes: Columns containing descriptive data.
        hashdiff_name: Name of the hash diff column.
        load_timestamp_name: Name of the load timestamp column.
        record_source_name: Name of the record source column.
        load_end_timestamp_name: Optional end date for satellite records.
        source_table: Original source table name.
        description: Human-readable description.
        is_effectivity_satellite: Whether this tracks relationship effectivity.
        is_multi_active: Whether multiple active records are allowed.
    """
    name: str
    parent_name: str
    parent_hash_key_name: str
    descriptive_attributes: List[Column]
    hashdiff_name: str = "HASHDIFF"
    load_timestamp_name: str = "LOAD_DTS"
    record_source_name: str = "RECORD_SOURCE"
    load_end_timestamp_name: Optional[str] = None
    source_table: Optional[str] = None
    description: Optional[str] = None
    is_effectivity_satellite: bool = False
    is_multi_active: bool = False

    def get_attribute_names(self) -> List[str]:
        """Return list of descriptive attribute column names."""
        return [col.name for col in self.descriptive_attributes]


@dataclass
class PointInTimeTable:
    """
    Point-in-Time (PIT) table for efficient satellite queries.

    PIT tables pre-join satellites to their parent hub/link
    at specific points in time, enabling efficient queries
    without complex temporal joins.

    Attributes:
        name: PIT table name.
        parent_hub_name: Name of the parent Hub.
        parent_hash_key_name: Hash key of the parent Hub.
        satellite_references: List of satellites included in the PIT.
        snapshot_date_name: Column name for snapshot dates.
    """
    name: str
    parent_hub_name: str
    parent_hash_key_name: str
    satellite_references: List[str]
    snapshot_date_name: str = "SNAPSHOT_DTS"


@dataclass
class BridgeTable:
    """
    Bridge table for optimized link traversal.

    Bridge tables materialize paths through multiple links
    for improved query performance in complex relationships.

    Attributes:
        name: Bridge table name.
        link_references: Links included in the bridge.
        hub_references: Hubs connected by the bridge.
    """
    name: str
    link_references: List[str]
    hub_references: List[str]


@dataclass
class DataVaultModel:
    """
    Complete Data Vault model containing all components.

    Attributes:
        hubs: All Hub tables in the model.
        links: All Link tables in the model.
        satellites: All Satellite tables in the model.
        pit_tables: Optional Point-in-Time tables.
        bridge_tables: Optional Bridge tables.
        staging_tables: Staging table definitions.
    """
    hubs: List[Hub] = field(default_factory=list)
    links: List[Link] = field(default_factory=list)
    satellites: List[Satellite] = field(default_factory=list)
    pit_tables: List[PointInTimeTable] = field(default_factory=list)
    bridge_tables: List[BridgeTable] = field(default_factory=list)
    staging_tables: List[str] = field(default_factory=list)


class GeneratorDataVault:
    """
    Data Vault 2.0 code generator.

    Generates DDL and dbt models for Data Vault 2.0 schemas
    following best practices from Dan Linstedt and other
    Data Vault practitioners.

    Supports:
    - Raw DDL generation for direct database deployment
    - dbt model generation using dbtvault macros
    - Ghost record generation for referential integrity
    - Point-in-Time (PIT) table generation

    Attributes:
        hash_algorithm: Algorithm for hash key generation.
        include_pit: Whether to generate PIT tables.
        hash_concatenator: Delimiter for concatenating hash inputs.
        null_placeholder: Value to use for NULL in hash calculations.
        record_source_default: Default record source value.
    """

    def __init__(
        self,
        hash_algorithm: str = "md5",
        include_pit: bool = False,
        hash_concatenator: str = "||'|'||",
        null_placeholder: str = "^^",
        record_source_default: str = "SYSTEM"
    ):
        """
        Initialize the Data Vault generator.

        Args:
            hash_algorithm: Hash algorithm to use (md5, sha1, sha256).
            include_pit: Whether to generate Point-in-Time tables.
            hash_concatenator: Delimiter between hash input values.
            null_placeholder: Placeholder for NULL values in hashing.
            record_source_default: Default value for RECORD_SOURCE.
        """
        self.hash_algorithm = HashAlgorithm(hash_algorithm.lower())
        self.include_pit = include_pit
        self.hash_concatenator = hash_concatenator
        self.null_placeholder = null_placeholder
        self.record_source_default = record_source_default

        # Storage for generated components
        self._generated_model: Optional[DataVaultModel] = None

    def generate(self, design: ModelDesign) -> Dict[str, str]:
        """
        Generate Data Vault 2.0 schema from a model design.

        This is the main entry point for generation. It analyzes
        the design, classifies tables, and generates all Data Vault
        components.

        Args:
            design: The model design specification.

        Returns:
            Dictionary mapping file paths to generated content.
        """
        generated_files: Dict[str, str] = {}

        # Classify tables into Data Vault components
        classification = self._classify_tables(design.tables)

        # Build the Data Vault model
        self._generated_model = DataVaultModel()

        # Generate Hubs from entities/dimensions
        for table in classification.get("hubs", []):
            hub = self._create_hub_from_table(table)
            self._generated_model.hubs.append(hub)

            # Generate Hub DDL
            hub_ddl = self._generate_hub(table)
            generated_files[f"raw_vault/hubs/{hub.name.lower()}.sql"] = hub_ddl

        # Generate Links from relationships/facts
        for table in classification.get("links", []):
            link = self._create_link_from_table(table, classification.get("hubs", []))
            self._generated_model.links.append(link)

            # Generate Link DDL
            link_ddl = self._generate_link(
                table,
                classification.get("hubs", [])
            )
            generated_files[f"raw_vault/links/{link.name.lower()}.sql"] = link_ddl

        # Generate Satellites from descriptive attributes
        for hub_table in classification.get("hubs", []):
            descriptive_attrs = self._get_descriptive_attributes(hub_table)
            if descriptive_attrs:
                hub_name = self._get_hub_name(hub_table.name)
                satellite = self._create_satellite_from_table(hub_table, hub_name, descriptive_attrs)
                self._generated_model.satellites.append(satellite)

                # Generate Satellite DDL
                sat_ddl = self._generate_satellite(hub_table, descriptive_attrs)
                generated_files[f"raw_vault/satellites/{satellite.name.lower()}.sql"] = sat_ddl

        # Generate Satellites for Links if they have descriptive attributes
        for link_table in classification.get("links", []):
            descriptive_attrs = self._get_link_descriptive_attributes(link_table)
            if descriptive_attrs:
                link_name = self._get_link_name(link_table.name)
                satellite = self._create_link_satellite(link_table, link_name, descriptive_attrs)
                self._generated_model.satellites.append(satellite)

                sat_ddl = self._generate_satellite(link_table, descriptive_attrs)
                generated_files[f"raw_vault/satellites/{satellite.name.lower()}.sql"] = sat_ddl

        # Generate PIT tables if requested
        if self.include_pit:
            pit_ddl = self._generate_pit_tables()
            for pit_name, ddl in pit_ddl.items():
                generated_files[f"business_vault/pit/{pit_name.lower()}.sql"] = ddl

        # Generate staging models
        staging_models = self._generate_staging_layer(design)
        for name, content in staging_models.items():
            generated_files[f"staging/{name}"] = content

        # Generate ghost records
        ghost_records = self._generate_ghost_records()
        generated_files["raw_vault/setup/ghost_records.sql"] = ghost_records

        # Generate dbt schema.yml files
        schema_files = self._generate_dbt_schema_files()
        for path, content in schema_files.items():
            generated_files[path] = content

        return generated_files

    def _generate_hub(self, table: DesignedTable) -> str:
        """
        Generate Hub DDL with hash key from business keys.

        Creates a Hub table following Data Vault 2.0 standards:
        - Hash key (HK_*) as primary key
        - Business key column(s)
        - Load timestamp (LOAD_DTS)
        - Record source (RECORD_SOURCE)

        Args:
            table: The designed table to generate a Hub from.

        Returns:
            SQL DDL for the Hub table.
        """
        hub_name = self._get_hub_name(table.name)
        business_keys = self._get_business_keys(table)
        bk_names = [col.name for col in business_keys]
        hash_key = self._generate_hash_key(bk_names, f"HK_{table.name.upper()}")

        # Build column definitions
        columns = []

        # Hash key (primary key)
        columns.append(f"    {hash_key} CHAR(32) NOT NULL")

        # Business key columns
        for col in business_keys:
            null_clause = "NOT NULL" if not col.is_nullable else ""
            columns.append(f"    {col.name} {col.data_type} {null_clause}".strip())

        # Standard metadata columns
        columns.append("    LOAD_DTS TIMESTAMP NOT NULL")
        columns.append("    RECORD_SOURCE VARCHAR(256) NOT NULL")

        # Build the DDL
        ddl = f"""-- Hub: {hub_name}
-- Source: {table.source_tables[0] if table.source_tables else 'Unknown'}
-- Business Keys: {', '.join(bk_names)}
-- Generated by DataForge Data Vault Generator on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

CREATE TABLE IF NOT EXISTS raw_vault.{hub_name} (
{','.join(chr(10).join([''] + columns) for _ in [1])[1:]},

    -- Primary Key
    CONSTRAINT pk_{hub_name.lower()} PRIMARY KEY ({hash_key}),

    -- Unique constraint on business key(s)
    CONSTRAINT uk_{hub_name.lower()}_bk UNIQUE ({', '.join(bk_names)})
);

-- Index for business key lookup
CREATE INDEX IF NOT EXISTS idx_{hub_name.lower()}_bk
ON raw_vault.{hub_name} ({', '.join(bk_names)});

-- Index for load timestamp (for incremental loads)
CREATE INDEX IF NOT EXISTS idx_{hub_name.lower()}_load_dts
ON raw_vault.{hub_name} (LOAD_DTS);
"""
        return ddl

    def _generate_link(
        self,
        fact_table: DesignedTable,
        dimensions: List[DesignedTable]
    ) -> str:
        """
        Generate Link DDL connecting Hubs.

        Creates a Link table following Data Vault 2.0 standards:
        - Link hash key (LK_*) as primary key
        - Foreign hash keys to connected Hubs
        - Load timestamp (LOAD_DTS)
        - Record source (RECORD_SOURCE)

        Args:
            fact_table: The fact/relationship table.
            dimensions: List of dimension tables (Hubs) this link connects.

        Returns:
            SQL DDL for the Link table.
        """
        link_name = self._get_link_name(fact_table.name)

        # Identify connected hubs from foreign keys
        hub_references = self._get_link_hub_references(fact_table, dimensions)
        all_hub_hash_keys = [f"HK_{ref.upper()}" for ref in hub_references]

        # Generate the link's own hash key from all hub keys
        link_hash_key = self._generate_hash_key(
            all_hub_hash_keys,
            f"LK_{fact_table.name.upper()}"
        )

        # Build column definitions
        columns = []

        # Link hash key (primary key)
        columns.append(f"    {link_hash_key} CHAR(32) NOT NULL")

        # Hub hash key foreign keys
        for hub_name in hub_references:
            hub_hash_key = f"HK_{hub_name.upper()}"
            columns.append(f"    {hub_hash_key} CHAR(32) NOT NULL")

        # Standard metadata columns
        columns.append("    LOAD_DTS TIMESTAMP NOT NULL")
        columns.append("    RECORD_SOURCE VARCHAR(256) NOT NULL")

        # Build foreign key constraints
        fk_constraints = []
        for hub_name in hub_references:
            hub_table_name = self._get_hub_name(hub_name)
            hub_hash_key = f"HK_{hub_name.upper()}"
            fk_constraints.append(
                f"    CONSTRAINT fk_{link_name.lower()}_{hub_name.lower()} "
                f"FOREIGN KEY ({hub_hash_key}) REFERENCES raw_vault.{hub_table_name} ({hub_hash_key})"
            )

        # Build the DDL
        ddl = f"""-- Link: {link_name}
-- Source: {fact_table.source_tables[0] if fact_table.source_tables else 'Unknown'}
-- Connects: {', '.join(hub_references)}
-- Generated by DataForge Data Vault Generator on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

CREATE TABLE IF NOT EXISTS raw_vault.{link_name} (
{chr(10).join(columns)},

    -- Primary Key
    CONSTRAINT pk_{link_name.lower()} PRIMARY KEY ({link_hash_key}),

    -- Foreign Keys to Hubs
{chr(10).join(fk_constraints)}
);

-- Index for each hub hash key (for join performance)
"""
        for hub_name in hub_references:
            hub_hash_key = f"HK_{hub_name.upper()}"
            ddl += f"""CREATE INDEX IF NOT EXISTS idx_{link_name.lower()}_{hub_name.lower()}
ON raw_vault.{link_name} ({hub_hash_key});

"""

        # Index for load timestamp
        ddl += f"""-- Index for load timestamp (for incremental loads)
CREATE INDEX IF NOT EXISTS idx_{link_name.lower()}_load_dts
ON raw_vault.{link_name} (LOAD_DTS);
"""
        return ddl

    def _generate_satellite(
        self,
        hub_or_link: DesignedTable,
        descriptive_attrs: List[Column]
    ) -> str:
        """
        Generate Satellite DDL with descriptive attributes.

        Creates a Satellite table following Data Vault 2.0 standards:
        - Parent hash key (foreign key to Hub/Link)
        - Load timestamp as part of primary key (for history)
        - Hash diff for change detection
        - Descriptive attribute columns
        - Record source

        Args:
            hub_or_link: The parent Hub or Link table.
            descriptive_attrs: List of descriptive attribute columns.

        Returns:
            SQL DDL for the Satellite table.
        """
        # Determine if this is a Hub or Link satellite
        is_link = hub_or_link.role in [TableRole.FACT, TableRole.JUNCTION, TableRole.LINK]

        if is_link:
            parent_name = self._get_link_name(hub_or_link.name)
            parent_hash_key = f"LK_{hub_or_link.name.upper()}"
            sat_name = f"SAT_{hub_or_link.name.upper()}"
        else:
            parent_name = self._get_hub_name(hub_or_link.name)
            parent_hash_key = f"HK_{hub_or_link.name.upper()}"
            sat_name = f"SAT_{hub_or_link.name.upper()}"

        # Generate HASHDIFF from descriptive attributes
        attr_names = [col.name for col in descriptive_attrs]
        hashdiff = self._generate_hashdiff(attr_names)

        # Build column definitions
        columns = []

        # Parent hash key (part of primary key)
        columns.append(f"    {parent_hash_key} CHAR(32) NOT NULL")

        # Load timestamp (part of primary key for versioning)
        columns.append("    LOAD_DTS TIMESTAMP NOT NULL")

        # Optional load end timestamp (for SCD Type 2)
        columns.append("    LOAD_END_DTS TIMESTAMP")

        # Hash diff for change detection
        columns.append(f"    {hashdiff} CHAR(32) NOT NULL")

        # Descriptive attributes
        for col in descriptive_attrs:
            data_type = self._normalize_data_type(col.data_type)
            null_clause = "" if col.is_nullable else "NOT NULL"
            columns.append(f"    {col.name} {data_type} {null_clause}".strip())

        # Record source
        columns.append("    RECORD_SOURCE VARCHAR(256) NOT NULL")

        # Build the DDL
        ddl = f"""-- Satellite: {sat_name}
-- Parent: {parent_name}
-- Attributes: {', '.join(attr_names)}
-- Generated by DataForge Data Vault Generator on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

CREATE TABLE IF NOT EXISTS raw_vault.{sat_name} (
{chr(10).join(columns)},

    -- Primary Key (composite: parent hash key + load timestamp)
    CONSTRAINT pk_{sat_name.lower()} PRIMARY KEY ({parent_hash_key}, LOAD_DTS),

    -- Foreign Key to parent Hub/Link
    CONSTRAINT fk_{sat_name.lower()}_parent
        FOREIGN KEY ({parent_hash_key})
        REFERENCES raw_vault.{parent_name} ({parent_hash_key})
);

-- Index for hash diff (for change detection queries)
CREATE INDEX IF NOT EXISTS idx_{sat_name.lower()}_hashdiff
ON raw_vault.{sat_name} ({hashdiff});

-- Index for load end timestamp (for current record queries)
CREATE INDEX IF NOT EXISTS idx_{sat_name.lower()}_load_end_dts
ON raw_vault.{sat_name} (LOAD_END_DTS)
WHERE LOAD_END_DTS IS NULL;
"""
        return ddl

    def _classify_tables(
        self,
        tables: List[DesignedTable]
    ) -> Dict[str, List[DesignedTable]]:
        """
        Classify tables into Data Vault components.

        Analyzes table roles and relationships to determine
        which tables become Hubs (entities), Links (relationships),
        or contribute attributes to Satellites.

        Args:
            tables: List of designed tables to classify.

        Returns:
            Dictionary with keys 'hubs', 'links', 'satellites'.
        """
        classification: Dict[str, List[DesignedTable]] = {
            "hubs": [],
            "links": [],
            "satellites": []
        }

        for table in tables:
            if table.role in [TableRole.DIMENSION, TableRole.HUB, TableRole.ENTITY]:
                # Dimensions and entities become Hubs
                classification["hubs"].append(table)
            elif table.role in [TableRole.FACT, TableRole.JUNCTION, TableRole.LINK]:
                # Facts and junctions become Links
                classification["links"].append(table)
            elif table.role == TableRole.SATELLITE:
                # Already classified as a satellite
                classification["satellites"].append(table)
            elif table.role == TableRole.BRIDGE:
                # Bridge tables become Links
                classification["links"].append(table)
            elif table.role == TableRole.LOOKUP:
                # Lookup tables become small Hubs
                classification["hubs"].append(table)
            else:
                # Default to Hub for unclassified tables with business keys
                business_keys = self._get_business_keys(table)
                if business_keys:
                    classification["hubs"].append(table)

        return classification

    def _generate_hash_key(self, columns: List[str], prefix: str) -> str:
        """
        Generate a hash key column name and expression.

        Creates a deterministic hash key name based on the
        source columns and prefix.

        Args:
            columns: List of column names to include in hash.
            prefix: Prefix for the hash key name (e.g., HK_, LK_).

        Returns:
            Hash key column name.
        """
        # Extract the entity name from prefix (e.g., HK_CUSTOMER -> CUSTOMER)
        entity_name = prefix.replace("HK_", "").replace("LK_", "")
        return prefix if prefix.startswith(("HK_", "LK_")) else f"HK_{prefix}"

    def _generate_hash_expression(self, columns: List[str]) -> str:
        """
        Generate the SQL expression for computing a hash.

        Creates the SQL expression that computes the hash value
        from the input columns, handling NULLs appropriately.

        Args:
            columns: List of column names to hash.

        Returns:
            SQL expression for computing the hash.
        """
        # Wrap each column with COALESCE to handle NULLs
        coalesced = [
            f"COALESCE(CAST({col} AS VARCHAR), '{self.null_placeholder}')"
            for col in columns
        ]

        # Concatenate and hash
        concat_expr = self.hash_concatenator.join(coalesced)

        if self.hash_algorithm == HashAlgorithm.MD5:
            return f"MD5({concat_expr})"
        elif self.hash_algorithm == HashAlgorithm.SHA1:
            return f"SHA1({concat_expr})"
        else:  # SHA256
            return f"SHA256({concat_expr})"

    def _generate_hashdiff(self, columns: List[str]) -> str:
        """
        Generate HASHDIFF column name.

        HASHDIFF is used for change detection in satellites.
        It's a hash of all descriptive attributes.

        Args:
            columns: List of descriptive attribute column names.

        Returns:
            HASHDIFF column name.
        """
        return "HASHDIFF"

    def _generate_hashdiff_expression(self, columns: List[str]) -> str:
        """
        Generate the SQL expression for computing HASHDIFF.

        Args:
            columns: List of column names to include in hashdiff.

        Returns:
            SQL expression for computing HASHDIFF.
        """
        return self._generate_hash_expression(sorted(columns))

    def _get_business_keys(self, table: DesignedTable) -> List[Column]:
        """
        Extract business key columns from a table.

        Business keys are the natural/business identifiers for
        an entity, not surrogate keys.

        Args:
            table: The designed table.

        Returns:
            List of business key columns.
        """
        business_keys = []

        for col in table.columns:
            # Check for explicit business key role
            if col.role == ColumnRole.BUSINESS_KEY:
                business_keys.append(self._designed_column_to_column(col))
            # Check for natural key role
            elif col.role == ColumnRole.NATURAL_KEY:
                business_keys.append(self._designed_column_to_column(col))
            # Fall back to primary key if no business keys defined
            elif col.is_primary_key and col.role != ColumnRole.SURROGATE_KEY:
                business_keys.append(self._designed_column_to_column(col))

        # If no business keys found, use primary key columns
        if not business_keys:
            for col in table.columns:
                if col.is_primary_key:
                    business_keys.append(self._designed_column_to_column(col))

        return business_keys

    def _get_descriptive_attributes(self, table: DesignedTable) -> List[Column]:
        """
        Extract descriptive attribute columns from a table.

        Descriptive attributes are non-key columns that describe
        the business entity.

        Args:
            table: The designed table.

        Returns:
            List of descriptive attribute columns.
        """
        attributes = []

        # Get business keys to exclude them
        business_key_names = {col.name for col in self._get_business_keys(table)}

        for col in table.columns:
            # Skip keys
            if col.name in business_key_names:
                continue
            if col.role in [ColumnRole.SURROGATE_KEY, ColumnRole.FOREIGN_KEY]:
                continue
            if col.is_primary_key:
                continue

            # Skip audit columns (they're handled by metadata columns)
            if col.role == ColumnRole.AUDIT:
                continue

            # Include attributes
            if col.role in [ColumnRole.ATTRIBUTE, ColumnRole.MEASURE]:
                attributes.append(self._designed_column_to_column(col))

        return attributes

    def _get_link_descriptive_attributes(self, table: DesignedTable) -> List[Column]:
        """
        Extract descriptive attributes from a link (fact) table.

        For links, we extract any non-foreign-key columns that
        describe the relationship.

        Args:
            table: The fact/link table.

        Returns:
            List of descriptive attribute columns.
        """
        attributes = []

        for col in table.columns:
            # Skip keys
            if col.role in [ColumnRole.SURROGATE_KEY, ColumnRole.FOREIGN_KEY]:
                continue
            if col.is_primary_key:
                continue
            if col.role == ColumnRole.AUDIT:
                continue

            # Include measures and attributes
            if col.role in [ColumnRole.ATTRIBUTE, ColumnRole.MEASURE, ColumnRole.DEGENERATE_DIMENSION]:
                attributes.append(self._designed_column_to_column(col))

        return attributes

    def _get_link_hub_references(
        self,
        link_table: DesignedTable,
        hubs: List[DesignedTable]
    ) -> List[str]:
        """
        Get list of hub names that a link references.

        Args:
            link_table: The link/fact table.
            hubs: List of hub tables.

        Returns:
            List of hub table names.
        """
        hub_names = []
        hub_name_set = {h.name.lower() for h in hubs}

        for col in link_table.columns:
            if col.role == ColumnRole.FOREIGN_KEY and col.references_table:
                ref_table = col.references_table.lower()
                if ref_table in hub_name_set:
                    hub_names.append(col.references_table)

        # If no FK references found, use dimension_keys from table definition
        if not hub_names and link_table.dimension_keys:
            for dk in link_table.dimension_keys:
                # Try to find matching hub
                for hub in hubs:
                    for hub_col in hub.columns:
                        if hub_col.name.lower() == dk.lower():
                            hub_names.append(hub.name)
                            break

        return list(set(hub_names))  # Remove duplicates

    def _get_hub_name(self, table_name: str) -> str:
        """Generate Hub table name from source table name."""
        clean_name = table_name.upper().replace("DIM_", "").replace("_DIM", "")
        return f"HUB_{clean_name}"

    def _get_link_name(self, table_name: str) -> str:
        """Generate Link table name from source table name."""
        clean_name = table_name.upper().replace("FCT_", "").replace("_FCT", "").replace("FACT_", "")
        return f"LNK_{clean_name}"

    def _designed_column_to_column(self, designed_col: DesignedColumn) -> Column:
        """Convert a DesignedColumn to a Column."""
        return Column(
            name=designed_col.name,
            data_type=designed_col.data_type,
            is_nullable=designed_col.is_nullable,
            is_primary_key=designed_col.is_primary_key,
            is_foreign_key=designed_col.role == ColumnRole.FOREIGN_KEY,
            foreign_key_table=designed_col.references_table,
            foreign_key_column=designed_col.references_column,
            description=designed_col.description
        )

    def _normalize_data_type(self, data_type: str) -> str:
        """Normalize data type for DDL generation."""
        # Ensure consistent data type formatting
        return data_type.upper()

    def _create_hub_from_table(self, table: DesignedTable) -> Hub:
        """Create a Hub dataclass from a DesignedTable."""
        business_keys = self._get_business_keys(table)
        hub_name = self._get_hub_name(table.name)
        hash_key = f"HK_{table.name.upper()}"

        return Hub(
            name=hub_name,
            business_key_columns=business_keys,
            hash_key_name=hash_key,
            source_table=table.source_tables[0] if table.source_tables else None,
            description=table.description
        )

    def _create_link_from_table(
        self,
        table: DesignedTable,
        hubs: List[DesignedTable]
    ) -> Link:
        """Create a Link dataclass from a DesignedTable."""
        link_name = self._get_link_name(table.name)
        hash_key = f"LK_{table.name.upper()}"
        hub_refs = self._get_link_hub_references(table, hubs)
        hub_references = [(ref, f"HK_{ref.upper()}") for ref in hub_refs]

        return Link(
            name=link_name,
            hash_key_name=hash_key,
            hub_references=hub_references,
            source_table=table.source_tables[0] if table.source_tables else None,
            description=table.description
        )

    def _create_satellite_from_table(
        self,
        table: DesignedTable,
        parent_name: str,
        attrs: List[Column]
    ) -> Satellite:
        """Create a Satellite dataclass for a Hub."""
        sat_name = f"SAT_{table.name.upper()}"
        parent_hash_key = f"HK_{table.name.upper()}"

        return Satellite(
            name=sat_name,
            parent_name=parent_name,
            parent_hash_key_name=parent_hash_key,
            descriptive_attributes=attrs,
            source_table=table.source_tables[0] if table.source_tables else None,
            description=f"Satellite for {parent_name}"
        )

    def _create_link_satellite(
        self,
        table: DesignedTable,
        parent_name: str,
        attrs: List[Column]
    ) -> Satellite:
        """Create a Satellite dataclass for a Link."""
        sat_name = f"SAT_{table.name.upper()}"
        parent_hash_key = f"LK_{table.name.upper()}"

        return Satellite(
            name=sat_name,
            parent_name=parent_name,
            parent_hash_key_name=parent_hash_key,
            descriptive_attributes=attrs,
            source_table=table.source_tables[0] if table.source_tables else None,
            description=f"Satellite for {parent_name}"
        )

    def _generate_pit_tables(self) -> Dict[str, str]:
        """
        Generate Point-in-Time (PIT) tables.

        PIT tables enable efficient querying of satellite data
        at specific points in time.

        Returns:
            Dictionary mapping PIT table names to DDL.
        """
        pit_ddl: Dict[str, str] = {}

        if not self._generated_model:
            return pit_ddl

        # Create PIT for each Hub with satellites
        hub_satellites: Dict[str, List[Satellite]] = {}
        for sat in self._generated_model.satellites:
            # Check if satellite belongs to a hub (not a link)
            for hub in self._generated_model.hubs:
                if sat.parent_hash_key_name == f"HK_{hub.name.replace('HUB_', '')}":
                    if hub.name not in hub_satellites:
                        hub_satellites[hub.name] = []
                    hub_satellites[hub.name].append(sat)
                    break

        for hub_name, satellites in hub_satellites.items():
            if not satellites:
                continue

            pit_name = f"PIT_{hub_name.replace('HUB_', '')}"
            hub_hash_key = f"HK_{hub_name.replace('HUB_', '')}"

            # Build column definitions
            columns = [
                f"    {hub_hash_key} CHAR(32) NOT NULL",
                "    SNAPSHOT_DTS TIMESTAMP NOT NULL"
            ]

            # Add satellite hash key columns
            for sat in satellites:
                columns.append(f"    {sat.name}_LOAD_DTS TIMESTAMP")

            ddl = f"""-- Point-in-Time Table: {pit_name}
-- Hub: {hub_name}
-- Satellites: {', '.join(s.name for s in satellites)}
-- Generated by DataForge Data Vault Generator on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

CREATE TABLE IF NOT EXISTS business_vault.{pit_name} (
{chr(10).join(columns)},

    -- Primary Key
    CONSTRAINT pk_{pit_name.lower()} PRIMARY KEY ({hub_hash_key}, SNAPSHOT_DTS),

    -- Foreign Key to Hub
    CONSTRAINT fk_{pit_name.lower()}_{hub_name.lower()}
        FOREIGN KEY ({hub_hash_key})
        REFERENCES raw_vault.{hub_name} ({hub_hash_key})
);

-- Index for snapshot queries
CREATE INDEX IF NOT EXISTS idx_{pit_name.lower()}_snapshot
ON business_vault.{pit_name} (SNAPSHOT_DTS);
"""
            pit_ddl[pit_name] = ddl

        return pit_ddl

    def _generate_ghost_records(self) -> str:
        """
        Generate ghost records for referential integrity.

        Ghost records represent "unknown" or "not applicable"
        relationships in the Data Vault, ensuring referential
        integrity while handling NULL foreign keys.

        Returns:
            SQL script for inserting ghost records.
        """
        if not self._generated_model:
            return "-- No model generated yet"

        ghost_sql = f"""-- Ghost Records for Data Vault
-- These records represent "unknown" or "not applicable" relationships
-- Generated by DataForge Data Vault Generator on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

-- Standard ghost hash key value (all zeros)
-- Used for NULL foreign key handling

"""
        # Generate ghost records for each Hub
        for hub in self._generated_model.hubs:
            bk_columns = hub.get_business_key_names()
            bk_values = ["'-1'"] * len(bk_columns)

            ghost_sql += f"""-- Ghost record for {hub.name}
INSERT INTO raw_vault.{hub.name} (
    {hub.hash_key_name},
    {', '.join(bk_columns)},
    LOAD_DTS,
    RECORD_SOURCE
)
SELECT
    '00000000000000000000000000000000',
    {', '.join(bk_values)},
    '1900-01-01 00:00:00'::TIMESTAMP,
    'SYSTEM'
WHERE NOT EXISTS (
    SELECT 1 FROM raw_vault.{hub.name}
    WHERE {hub.hash_key_name} = '00000000000000000000000000000000'
);

"""
        return ghost_sql

    def _generate_staging_layer(self, design: ModelDesign) -> Dict[str, str]:
        """
        Generate staging models for dbt.

        Creates staging models that prepare source data for
        loading into the Raw Vault.

        Args:
            design: The model design.

        Returns:
            Dictionary mapping file names to content.
        """
        staging_models: Dict[str, str] = {}

        for table in design.tables:
            model_name = f"stg_{table.name.lower()}"

            # Build column list
            columns = []
            for col in table.columns:
                columns.append(f"        {col.name}")

            # Generate hash key expressions
            business_keys = self._get_business_keys(table)
            bk_names = [col.name for col in business_keys]
            hash_expr = self._generate_hash_expression(bk_names)

            sql = f"""-- Staging model: {model_name}
-- Prepares source data for loading into Raw Vault
-- Generated by DataForge Data Vault Generator on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{{{{ config(
    materialized='view',
    schema='staging'
) }}}}

WITH source AS (
    SELECT * FROM {{{{ source('{design.source_schema or "source"}', '{table.name}') }}}}
),

hashed AS (
    SELECT
        -- Hash key
        {hash_expr} AS HK_{table.name.upper()},

        -- Source columns
{chr(10).join(columns)},

        -- Metadata
        CURRENT_TIMESTAMP AS LOAD_DTS,
        '{self.record_source_default}' AS RECORD_SOURCE
    FROM source
)

SELECT * FROM hashed
"""
            staging_models[f"{model_name}.sql"] = sql

            # Track staging table
            if self._generated_model:
                self._generated_model.staging_tables.append(model_name)

        return staging_models

    def _generate_dbt_schema_files(self) -> Dict[str, str]:
        """
        Generate dbt schema.yml files for documentation and testing.

        Returns:
            Dictionary mapping file paths to YAML content.
        """
        import yaml

        schema_files: Dict[str, str] = {}

        if not self._generated_model:
            return schema_files

        # Hub schema
        hub_models = []
        for hub in self._generated_model.hubs:
            columns = [
                {"name": hub.hash_key_name, "description": "Hash key", "tests": ["unique", "not_null"]},
            ]
            for col in hub.business_key_columns:
                columns.append({
                    "name": col.name,
                    "description": col.description or f"Business key: {col.name}"
                })
            columns.extend([
                {"name": "LOAD_DTS", "description": "Load timestamp", "tests": ["not_null"]},
                {"name": "RECORD_SOURCE", "description": "Source system", "tests": ["not_null"]}
            ])

            hub_models.append({
                "name": hub.name.lower(),
                "description": hub.description or f"Hub table for {hub.name}",
                "columns": columns
            })

        if hub_models:
            schema_files["raw_vault/hubs/schema.yml"] = yaml.dump(
                {"version": 2, "models": hub_models},
                default_flow_style=False,
                sort_keys=False
            )

        # Link schema
        link_models = []
        for link in self._generated_model.links:
            columns = [
                {"name": link.hash_key_name, "description": "Link hash key", "tests": ["unique", "not_null"]},
            ]
            for hub_name, hub_hk in link.hub_references:
                columns.append({
                    "name": hub_hk,
                    "description": f"Hash key to {hub_name}",
                    "tests": ["not_null"]
                })
            columns.extend([
                {"name": "LOAD_DTS", "description": "Load timestamp", "tests": ["not_null"]},
                {"name": "RECORD_SOURCE", "description": "Source system", "tests": ["not_null"]}
            ])

            link_models.append({
                "name": link.name.lower(),
                "description": link.description or f"Link table for {link.name}",
                "columns": columns
            })

        if link_models:
            schema_files["raw_vault/links/schema.yml"] = yaml.dump(
                {"version": 2, "models": link_models},
                default_flow_style=False,
                sort_keys=False
            )

        # Satellite schema
        sat_models = []
        for sat in self._generated_model.satellites:
            columns = [
                {"name": sat.parent_hash_key_name, "description": "Parent hash key", "tests": ["not_null"]},
                {"name": "LOAD_DTS", "description": "Load timestamp", "tests": ["not_null"]},
                {"name": "LOAD_END_DTS", "description": "Record end timestamp"},
                {"name": sat.hashdiff_name, "description": "Hash diff for change detection", "tests": ["not_null"]},
            ]
            for col in sat.descriptive_attributes:
                columns.append({
                    "name": col.name,
                    "description": col.description or f"Attribute: {col.name}"
                })
            columns.append({
                "name": "RECORD_SOURCE", "description": "Source system", "tests": ["not_null"]
            })

            sat_models.append({
                "name": sat.name.lower(),
                "description": sat.description or f"Satellite for {sat.parent_name}",
                "columns": columns
            })

        if sat_models:
            schema_files["raw_vault/satellites/schema.yml"] = yaml.dump(
                {"version": 2, "models": sat_models},
                default_flow_style=False,
                sort_keys=False
            )

        return schema_files

    def generate_dbtvault_models(self, design: ModelDesign) -> Dict[str, str]:
        """
        Generate dbt models using dbtvault macros.

        This method generates dbt models that use the dbtvault
        package for Data Vault automation.

        Args:
            design: The model design.

        Returns:
            Dictionary mapping file paths to model content.
        """
        models: Dict[str, str] = {}

        # First run standard generation to populate model
        self.generate(design)

        if not self._generated_model:
            return models

        # Generate Hub models using dbtvault
        for hub in self._generated_model.hubs:
            bk_names = hub.get_business_key_names()
            staging_model = f"stg_{hub.name.replace('HUB_', '').lower()}"

            sql = f"""-- Hub: {hub.name} (using dbtvault)
-- Generated by DataForge Data Vault Generator

{{{{ config(
    materialized='incremental',
    schema='raw_vault'
) }}}}

{{%- set source_model = "{staging_model}" -%}}
{{%- set src_pk = "{hub.hash_key_name}" -%}}
{{%- set src_nk = {bk_names} -%}}
{{%- set src_ldts = "LOAD_DTS" -%}}
{{%- set src_source = "RECORD_SOURCE" -%}}

{{{{ dbtvault.hub(src_pk=src_pk, src_nk=src_nk, src_ldts=src_ldts,
                   src_source=src_source, source_model=source_model) }}}}
"""
            models[f"raw_vault/hubs/{hub.name.lower()}.sql"] = sql

        # Generate Link models using dbtvault
        for link in self._generated_model.links:
            hub_hks = link.get_hub_hash_key_names()
            staging_model = f"stg_{link.name.replace('LNK_', '').lower()}"

            sql = f"""-- Link: {link.name} (using dbtvault)
-- Generated by DataForge Data Vault Generator

{{{{ config(
    materialized='incremental',
    schema='raw_vault'
) }}}}

{{%- set source_model = "{staging_model}" -%}}
{{%- set src_pk = "{link.hash_key_name}" -%}}
{{%- set src_fk = {hub_hks} -%}}
{{%- set src_ldts = "LOAD_DTS" -%}}
{{%- set src_source = "RECORD_SOURCE" -%}}

{{{{ dbtvault.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}}}
"""
            models[f"raw_vault/links/{link.name.lower()}.sql"] = sql

        # Generate Satellite models using dbtvault
        for sat in self._generated_model.satellites:
            attr_names = sat.get_attribute_names()
            staging_model = f"stg_{sat.name.replace('SAT_', '').lower()}"

            sql = f"""-- Satellite: {sat.name} (using dbtvault)
-- Generated by DataForge Data Vault Generator

{{{{ config(
    materialized='incremental',
    schema='raw_vault'
) }}}}

{{%- set source_model = "{staging_model}" -%}}
{{%- set src_pk = "{sat.parent_hash_key_name}" -%}}
{{%- set src_hashdiff = "{sat.hashdiff_name}" -%}}
{{%- set src_payload = {attr_names} -%}}
{{%- set src_ldts = "LOAD_DTS" -%}}
{{%- set src_source = "RECORD_SOURCE" -%}}

{{{{ dbtvault.sat(src_pk=src_pk, src_hashdiff=src_hashdiff,
                   src_payload=src_payload, src_ldts=src_ldts,
                   src_source=src_source, source_model=source_model) }}}}
"""
            models[f"raw_vault/satellites/{sat.name.lower()}.sql"] = sql

        return models
