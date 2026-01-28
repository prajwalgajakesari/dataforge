"""
PostgreSQL MCP Server for DataForge.

Provides schema discovery, data profiling, and query capabilities for PostgreSQL databases.
"""

import asyncio
from typing import Any, Dict, List, Optional

import asyncpg
from pydantic import BaseModel

from core.mcp.client import MCPClient, MCPResponse
from core.mcp.registry import MCPServerConfig
from core.utils.logger import get_logger

logger = get_logger(__name__)


class PostgresColumn(BaseModel):
    """PostgreSQL column metadata."""

    table_schema: str
    table_name: str
    column_name: str
    ordinal_position: int
    column_default: Optional[str] = None
    is_nullable: bool
    data_type: str
    character_maximum_length: Optional[int] = None
    numeric_precision: Optional[int] = None
    numeric_scale: Optional[int] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_table: Optional[str] = None
    foreign_key_column: Optional[str] = None


class PostgresTable(BaseModel):
    """PostgreSQL table metadata."""

    table_schema: str
    table_name: str
    table_type: str
    row_count: Optional[int] = None
    size_bytes: Optional[int] = None
    columns: List[PostgresColumn] = []


class PostgresSchema(BaseModel):
    """PostgreSQL schema metadata."""

    schema_name: str
    tables: List[PostgresTable] = []


class DataProfile(BaseModel):
    """Data profiling results for a column."""

    column_name: str
    data_type: str
    null_count: int
    null_percentage: float
    distinct_count: Optional[int] = None
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    avg_value: Optional[float] = None
    sample_values: List[Any] = []


class PostgresMCP(MCPClient):
    """
    MCP Server for PostgreSQL databases.

    Capabilities:
    - Schema discovery (databases, schemas, tables, columns, constraints)
    - Data profiling (row counts, data types, statistics)
    - Query execution
    - Sample data retrieval
    - Relationship discovery (foreign keys)
    """

    def __init__(self, config: MCPServerConfig):
        """
        Initialize PostgreSQL MCP server.

        Args:
            config: Server configuration with connection details
        """
        super().__init__(config)
        self.pool: Optional[asyncpg.Pool] = None
        self._schema_cache: Dict[str, PostgresSchema] = {}

    async def _connect_database(self) -> None:
        """Establish connection pool to PostgreSQL."""
        try:
            conn_config = self.config.connection_config

            self.pool = await asyncpg.create_pool(
                host=conn_config.get("host", "localhost"),
                port=conn_config.get("port", 5432),
                user=conn_config.get("user", "postgres"),
                password=conn_config.get("password", ""),
                database=conn_config.get("database", "postgres"),
                min_size=2,
                max_size=10,
                timeout=self.config.timeout,
            )

            # Test connection
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            logger.info(f"Connected to PostgreSQL: {conn_config.get('host')}")
            self.connection = self.pool

        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise ConnectionError(f"PostgreSQL connection failed: {e}")

    async def disconnect(self) -> None:
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            self._connected = False
            logger.info("Disconnected from PostgreSQL")

    async def discover_schemas(
        self,
        schema_pattern: Optional[str] = None,
        exclude_system: bool = True,
    ) -> List[PostgresSchema]:
        """
        Discover all schemas in the database.

        Args:
            schema_pattern: Optional SQL LIKE pattern for schema names
            exclude_system: Exclude system schemas (pg_*, information_schema)

        Returns:
            List of schema metadata objects
        """
        if not self._connected:
            await self.connect()

        query = """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE 1=1
        """

        params = []

        if exclude_system:
            query += """
                AND schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                AND schema_name NOT LIKE 'pg_temp_%'
                AND schema_name NOT LIKE 'pg_toast_temp_%'
            """

        if schema_pattern:
            query += " AND schema_name LIKE $1"
            params.append(schema_pattern)

        query += " ORDER BY schema_name"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        schemas = []
        for row in rows:
            schema_name = row["schema_name"]
            schema = PostgresSchema(schema_name=schema_name)

            # Discover tables for this schema
            schema.tables = await self.discover_tables(schema_name)

            schemas.append(schema)
            self._schema_cache[schema_name] = schema

        logger.info(f"Discovered {len(schemas)} schemas")
        return schemas

    async def discover_tables(
        self,
        schema_name: str,
        table_pattern: Optional[str] = None,
    ) -> List[PostgresTable]:
        """
        Discover tables in a schema.

        Args:
            schema_name: Name of the schema
            table_pattern: Optional SQL LIKE pattern for table names

        Returns:
            List of table metadata objects
        """
        if not self._connected:
            await self.connect()

        query = """
            SELECT
                t.table_schema,
                t.table_name,
                t.table_type,
                pg_total_relation_size(quote_ident(t.table_schema) || '.' || quote_ident(t.table_name)) as size_bytes
            FROM information_schema.tables t
            WHERE t.table_schema = $1
                AND t.table_type IN ('BASE TABLE', 'VIEW')
        """

        params = [schema_name]

        if table_pattern:
            query += " AND t.table_name LIKE $2"
            params.append(table_pattern)

        query += " ORDER BY t.table_name"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        tables = []
        for row in rows:
            table = PostgresTable(
                table_schema=row["table_schema"],
                table_name=row["table_name"],
                table_type=row["table_type"],
                size_bytes=row["size_bytes"],
            )

            # Get row count
            try:
                row_count_query = f"""
                    SELECT COUNT(*) as cnt
                    FROM {row['table_schema']}.{row['table_name']}
                """
                async with self.pool.acquire() as conn:
                    count_row = await conn.fetchrow(row_count_query)
                    table.row_count = count_row["cnt"]
            except Exception as e:
                logger.warning(f"Could not get row count for {table.table_name}: {e}")

            # Discover columns
            table.columns = await self.discover_columns(
                row["table_schema"],
                row["table_name"],
            )

            tables.append(table)

        logger.info(f"Discovered {len(tables)} tables in schema {schema_name}")
        return tables

    async def discover_columns(
        self,
        schema_name: str,
        table_name: str,
    ) -> List[PostgresColumn]:
        """
        Discover columns for a table.

        Args:
            schema_name: Name of the schema
            table_name: Name of the table

        Returns:
            List of column metadata objects
        """
        if not self._connected:
            await self.connect()

        # Get column information
        column_query = """
            SELECT
                c.table_schema,
                c.table_name,
                c.column_name,
                c.ordinal_position,
                c.column_default,
                c.is_nullable = 'YES' as is_nullable,
                c.data_type,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale
            FROM information_schema.columns c
            WHERE c.table_schema = $1
                AND c.table_name = $2
            ORDER BY c.ordinal_position
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(column_query, schema_name, table_name)

        columns = []
        for row in rows:
            column = PostgresColumn(
                table_schema=row["table_schema"],
                table_name=row["table_name"],
                column_name=row["column_name"],
                ordinal_position=row["ordinal_position"],
                column_default=row["column_default"],
                is_nullable=row["is_nullable"],
                data_type=row["data_type"],
                character_maximum_length=row["character_maximum_length"],
                numeric_precision=row["numeric_precision"],
                numeric_scale=row["numeric_scale"],
            )
            columns.append(column)

        # Get primary key information
        pk_query = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = $1
                AND tc.table_name = $2
        """

        async with self.pool.acquire() as conn:
            pk_rows = await conn.fetch(pk_query, schema_name, table_name)

        pk_columns = {row["column_name"] for row in pk_rows}

        # Get foreign key information
        fk_query = """
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = $1
                AND tc.table_name = $2
        """

        async with self.pool.acquire() as conn:
            fk_rows = await conn.fetch(fk_query, schema_name, table_name)

        fk_map = {
            row["column_name"]: {
                "table": row["foreign_table_name"],
                "column": row["foreign_column_name"],
            }
            for row in fk_rows
        }

        # Update columns with key information
        for column in columns:
            column.is_primary_key = column.column_name in pk_columns

            if column.column_name in fk_map:
                column.is_foreign_key = True
                column.foreign_key_table = fk_map[column.column_name]["table"]
                column.foreign_key_column = fk_map[column.column_name]["column"]

        return columns

    async def profile_table(
        self,
        schema_name: str,
        table_name: str,
        sample_size: int = 1000,
    ) -> List[DataProfile]:
        """
        Profile data in a table.

        Args:
            schema_name: Name of the schema
            table_name: Name of the table
            sample_size: Number of rows to sample

        Returns:
            List of data profiles for each column
        """
        if not self._connected:
            await self.connect()

        # Get columns
        columns = await self.discover_columns(schema_name, table_name)

        profiles = []

        for column in columns:
            col_name = column.column_name
            data_type = column.data_type

            # Build profiling query based on data type
            profile_query = f"""
                SELECT
                    COUNT(*) as total_count,
                    COUNT({col_name}) as non_null_count,
                    COUNT(*) - COUNT({col_name}) as null_count
            """

            # Add type-specific aggregations
            if data_type in ("integer", "bigint", "numeric", "real", "double precision"):
                profile_query += f""",
                    MIN({col_name})::text as min_value,
                    MAX({col_name})::text as max_value,
                    AVG({col_name})::numeric as avg_value,
                    COUNT(DISTINCT {col_name}) as distinct_count
                """
            elif data_type in ("character varying", "text", "character"):
                profile_query += f""",
                    MIN({col_name})::text as min_value,
                    MAX({col_name})::text as max_value,
                    COUNT(DISTINCT {col_name}) as distinct_count
                """
            else:
                profile_query += f""",
                    COUNT(DISTINCT {col_name}) as distinct_count
                """

            profile_query += f" FROM {schema_name}.{table_name}"

            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(profile_query)

                total_count = row["total_count"]
                null_count = row["null_count"]
                null_percentage = (null_count / total_count * 100) if total_count > 0 else 0

                # Get sample values
                sample_query = f"""
                    SELECT {col_name}
                    FROM {schema_name}.{table_name}
                    WHERE {col_name} IS NOT NULL
                    ORDER BY RANDOM()
                    LIMIT $1
                """

                async with self.pool.acquire() as conn:
                    sample_rows = await conn.fetch(sample_query, min(sample_size, 10))

                sample_values = [r[col_name] for r in sample_rows]

                profile = DataProfile(
                    column_name=col_name,
                    data_type=data_type,
                    null_count=null_count,
                    null_percentage=round(null_percentage, 2),
                    distinct_count=row.get("distinct_count"),
                    min_value=row.get("min_value"),
                    max_value=row.get("max_value"),
                    avg_value=float(row["avg_value"]) if row.get("avg_value") else None,
                    sample_values=sample_values,
                )

                profiles.append(profile)

            except Exception as e:
                logger.warning(f"Could not profile column {col_name}: {e}")
                # Add minimal profile
                profiles.append(
                    DataProfile(
                        column_name=col_name,
                        data_type=data_type,
                        null_count=0,
                        null_percentage=0.0,
                    )
                )

        logger.info(f"Profiled {len(profiles)} columns in {schema_name}.{table_name}")
        return profiles

    async def execute_query(
        self,
        query: str,
        params: Optional[List[Any]] = None,
        fetch_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a SQL query.

        Args:
            query: SQL query to execute
            params: Optional query parameters
            fetch_size: Optional limit on rows to fetch

        Returns:
            Dictionary with rows and metadata
        """
        if not self._connected:
            await self.connect()

        try:
            if fetch_size:
                query = f"{query} LIMIT {fetch_size}"

            async with self.pool.acquire() as conn:
                if params:
                    rows = await conn.fetch(query, *params)
                else:
                    rows = await conn.fetch(query)

            # Convert to list of dicts
            results = [dict(row) for row in rows]

            return {
                "rows": results,
                "row_count": len(results),
                "columns": list(rows[0].keys()) if results else [],
            }

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise Exception(f"Query failed: {e}")

    async def _execute_database_operation(
        self,
        operation: str,
        params: Dict[str, Any],
    ) -> MCPResponse:
        """Execute database operations via MCP protocol."""
        try:
            if operation == "discover_schemas":
                schemas = await self.discover_schemas(
                    schema_pattern=params.get("pattern"),
                    exclude_system=params.get("exclude_system", True),
                )
                return MCPResponse(
                    success=True,
                    data=[s.model_dump() for s in schemas],
                )

            elif operation == "discover_tables":
                tables = await self.discover_tables(
                    schema_name=params["schema"],
                    table_pattern=params.get("pattern"),
                )
                return MCPResponse(
                    success=True,
                    data=[t.model_dump() for t in tables],
                )

            elif operation == "profile_table":
                profiles = await self.profile_table(
                    schema_name=params["schema"],
                    table_name=params["table"],
                    sample_size=params.get("sample_size", 1000),
                )
                return MCPResponse(
                    success=True,
                    data=[p.model_dump() for p in profiles],
                )

            elif operation == "query":
                result = await self.execute_query(
                    query=params["sql"],
                    params=params.get("params"),
                    fetch_size=params.get("fetch_size"),
                )
                return MCPResponse(success=True, data=result)

            else:
                return MCPResponse(
                    success=False,
                    error=f"Unknown operation: {operation}",
                )

        except Exception as e:
            logger.error(f"Operation {operation} failed: {e}")
            return MCPResponse(success=False, error=str(e))

    async def health_check(self) -> bool:
        """Check if the database connection is healthy."""
        try:
            if not self._connected:
                await self.connect()

            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
