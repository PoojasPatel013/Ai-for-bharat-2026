"""Migration script from SQLite to PostgreSQL.

This utility copies all data from the lightweight SQLite database
into the full production PostgreSQL database.
"""

import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from doc_healing.db.base import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_data(sqlite_url: str, postgres_url: str) -> bool:
    """Migrate data from SQLite to PostgreSQL."""
    logger.info(f"Connecting to Source SQLite: {sqlite_url}")
    source_engine = create_engine(sqlite_url)
    SourceSession = sessionmaker(bind=source_engine)
    
    logger.info(f"Connecting to Target PostgreSQL: {postgres_url}")
    target_engine = create_engine(postgres_url)
    TargetSession = sessionmaker(bind=target_engine)
    
    # Ensure target tables exist
    Base.metadata.create_all(target_engine)
    
    source_session = SourceSession()
    target_session = TargetSession()
    
    try:
        # Get all table models from Base
        # We need to migrate each table data
        tables_migrated = 0
        records_migrated = 0
        
        for name, table in Base.metadata.tables.items():
            logger.info(f"Migrating table: {name}")
            
            # Read all rows from source
            result = source_engine.execute(table.select())
            rows = result.fetchall()
            
            if not rows:
                logger.info(f"  Table {name} is empty, skipping.")
                continue
                
            # Clear target table just in case (optional, depends on use case)
            # target_engine.execute(table.delete())
            
            # Insert into target
            # Note: For large tables we should batch this
            dicts = [dict(row) for row in rows]
            target_engine.execute(table.insert(), dicts)
            
            tables_migrated += 1
            records_migrated += len(rows)
            logger.info(f"  Migrated {len(rows)} records for {name}")
            
        target_session.commit()
        logger.info(f"Migration successful: {records_migrated} records across {tables_migrated} tables.")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        target_session.rollback()
        return False
    finally:
        source_session.close()
        target_session.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate Doc Healing data from SQLite to PostgreSQL")
    parser.add_argument("--sqlite", default="sqlite:///./data/doc_healing.db", help="Source SQLite URL")
    parser.add_argument("--postgres", default="postgresql://postgres:postgres@localhost:5432/doc_healing", help="Target PostgreSQL URL")
    
    args = parser.parse_args()
    success = migrate_data(args.sqlite, args.postgres)
    sys.exit(0 if success else 1)
