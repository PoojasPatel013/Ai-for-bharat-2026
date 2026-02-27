import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add scripts directory to path for testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

try:
    import migrate_postgres_to_sqlite as p2s
    import migrate_sqlite_to_postgres as s2p
except ImportError:
    pass

@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = MagicMock()
    session.query.return_value.all.return_value = []
    return session

@pytest.fixture
def mock_db_engine():
    """Mock database engine."""
    engine = MagicMock()
    return engine

class TestPostgresToSqliteMigration:
    """Tests for PostgreSQL to SQLite migration script."""

    @patch('migrate_postgres_to_sqlite.Base')
    @patch('migrate_postgres_to_sqlite.create_engine')
    @patch('migrate_postgres_to_sqlite.sessionmaker')
    def test_migration_success(self, mock_sessionmaker, mock_create_engine, mock_base, caplog):
        """Test successful migration from Postgres to SQLite."""
        pg_engine = MagicMock()
        sqlite_engine = MagicMock()
        mock_create_engine.side_effect = [pg_engine, sqlite_engine]
        
        pg_session = MagicMock()
        sqlite_session = MagicMock()
        
        mock_table = MagicMock()
        mock_base.metadata.tables.items.return_value = [("system_config", mock_table)]
        
        mock_row = MagicMock()
        mock_row.keys.return_value = ["id", "key"]
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        pg_engine.execute.return_value = mock_result
        
        mock_session_class = MagicMock()
        mock_session_class.side_effect = [pg_session, sqlite_session]
        mock_sessionmaker.return_value = mock_session_class
        
        with patch('builtins.dict', return_value={"id": 1, "key": "value"}):
            result = p2s.migrate_data("postgresql://mock/db", "sqlite://mock.db")
            
        assert result is True
        assert sqlite_session.commit.called
        assert sqlite_engine.execute.called

    @patch('migrate_postgres_to_sqlite.Base')
    @patch('migrate_postgres_to_sqlite.create_engine')
    @patch('migrate_postgres_to_sqlite.sessionmaker')
    def test_migration_error_handling(self, mock_sessionmaker, mock_create_engine, mock_base):
        """Test migration fails gracefully with engine errors."""
        mock_table = MagicMock()
        mock_base.metadata.tables.items.return_value = [("system_config", mock_table)]
        
        # Raise exception during execute to trigger the try/except block
        pg_engine = MagicMock()
        pg_engine.execute.side_effect = Exception("DB Error")
        
        sqlite_engine = MagicMock()
        mock_create_engine.side_effect = [pg_engine, sqlite_engine]
        
        with patch('builtins.dict', return_value={"id": 1, "key": "value"}):
            result = p2s.migrate_data("postgresql://bad/db", "sqlite://bad.db")
            
        assert result is False


class TestSqliteToPostgresMigration:
    """Tests for SQLite to PostgreSQL migration script."""

    @patch('migrate_sqlite_to_postgres.Base')
    @patch('migrate_sqlite_to_postgres.create_engine')
    @patch('migrate_sqlite_to_postgres.sessionmaker')
    def test_migration_success(self, mock_sessionmaker, mock_create_engine, mock_base, caplog):
        """Test successful migration from SQLite to Postgres."""
        sqlite_engine = MagicMock()
        pg_engine = MagicMock()
        mock_create_engine.side_effect = [sqlite_engine, pg_engine]
        
        sqlite_session = MagicMock()
        pg_session = MagicMock()
        
        mock_table = MagicMock()
        mock_base.metadata.tables.items.return_value = [("system_config", mock_table)]
        
        mock_row = MagicMock()
        mock_row.keys.return_value = ["id", "key"]
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        sqlite_engine.execute.return_value = mock_result
        
        mock_session_class = MagicMock()
        mock_session_class.side_effect = [sqlite_session, pg_session]
        mock_sessionmaker.return_value = mock_session_class
        
        with patch('builtins.dict', return_value={"id": 1, "key": "value"}):
            result = s2p.migrate_data("sqlite://mock.db", "postgresql://mock/db")
            
        assert result is True
        assert pg_session.commit.called
        assert pg_engine.execute.called

    @patch('migrate_sqlite_to_postgres.Base')
    @patch('migrate_sqlite_to_postgres.create_engine')
    @patch('migrate_sqlite_to_postgres.sessionmaker')
    def test_migration_error_handling(self, mock_sessionmaker, mock_create_engine, mock_base):
        """Test migration handles database errors correctly."""
        mock_table = MagicMock()
        mock_base.metadata.tables.items.return_value = [("system_config", mock_table)]
        
        # Raise exception during execute to trigger the try/except block
        sqlite_engine = MagicMock()
        sqlite_engine.execute.side_effect = Exception("DB Connection Error")
        
        pg_engine = MagicMock()
        mock_create_engine.side_effect = [sqlite_engine, pg_engine]

        with patch('builtins.dict', return_value={"id": 1, "key": "value"}):
            result = s2p.migrate_data("sqlite://bad.db", "postgresql://bad/db")
            
        assert result is False
