#!/usr/bin/env python3
"""
Database Migration Script for Flight Monitoring Models

This script handles database schema updates for the new Flight, Traveler, 
and TripMonitor models, as well as enhancements to existing models.

Usage:
    python migrate_database.py [--backup] [--force]
    
Options:
    --backup    Create a backup of the existing database before migration
    --force     Force migration even if tables already exist
"""

import os
import sys
import argparse
import shutil
from datetime import datetime
from sqlalchemy import create_engine, MetaData, text, inspect
from sqlalchemy.exc import SQLAlchemyError

# Import our models to ensure they're registered
from flight_agent.models import Base, engine, DATABASE_URL


def backup_database(db_path: str) -> str:
    """Create a backup of the database file (SQLite only)"""
    if not db_path or not os.path.exists(db_path):
        print(f"Warning: Database file {db_path} does not exist yet or not SQLite")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"✓ Database backed up to: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"✗ Failed to create backup: {e}")
        return None


def get_existing_tables(engine):
    """Get list of existing tables in the database"""
    inspector = inspect(engine)
    return inspector.get_table_names()


def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        inspector = inspect(engine)
        columns = inspector.get_columns(table_name)
        return any(col['name'] == column_name for col in columns)
    except:
        return False


def get_db_type(engine):
    """Determine database type from engine"""
    return engine.dialect.name.lower()


def add_missing_columns(engine):
    """Add missing columns to existing tables with proper SQL syntax"""
    migrations = []
    db_type = get_db_type(engine)
    
    # Check if we need to add new columns to existing tables
    existing_tables = get_existing_tables(engine)
    
    # Enhanced Booking table columns
    if 'bookings' in existing_tables:
        booking_additions = [
            ('flight_id', 'VARCHAR'),
            ('traveler_id', 'VARCHAR'),  
            ('ticket_number', 'VARCHAR'),
            ('booking_reference', 'VARCHAR'),
            ('fare_basis', 'VARCHAR'),
            ('fare_amount', 'FLOAT'),
            ('currency', 'VARCHAR'),
            ('updated_at', 'TIMESTAMP')
        ]
        
        for column, column_type in booking_additions:
            if not check_column_exists(engine, 'bookings', column):
                if db_type == 'postgresql':
                    migrations.append(f"ALTER TABLE bookings ADD COLUMN {column} {column_type}")
                    # Add default value separately for PostgreSQL
                    if column == 'currency':
                        migrations.append(f"ALTER TABLE bookings ALTER COLUMN {column} SET DEFAULT 'USD'")
                else:
                    # SQLite syntax
                    default_val = " DEFAULT 'USD'" if column == 'currency' else ""
                    migrations.append(f"ALTER TABLE bookings ADD COLUMN {column} {column_type}{default_val}")
    
    # Enhanced DisruptionEvent table columns  
    if 'disruption_events' in existing_tables:
        disruption_additions = [
            ('delay_minutes', 'INTEGER'),
            ('reason', 'VARCHAR'),
            ('notification_sent_at', 'TIMESTAMP'),
            ('compensation_eligible', 'BOOLEAN'),
            ('compensation_amount', 'FLOAT'),
            ('compensation_status', 'VARCHAR')
        ]
        
        for column, column_type in disruption_additions:
            if not check_column_exists(engine, 'disruption_events', column):
                if db_type == 'postgresql':
                    migrations.append(f"ALTER TABLE disruption_events ADD COLUMN {column} {column_type}")
                    # Add defaults separately for PostgreSQL
                    if column == 'delay_minutes':
                        migrations.append(f"ALTER TABLE disruption_events ALTER COLUMN {column} SET DEFAULT 0")
                    elif column == 'compensation_eligible':
                        migrations.append(f"ALTER TABLE disruption_events ALTER COLUMN {column} SET DEFAULT FALSE")
                    elif column == 'compensation_status':
                        migrations.append(f"ALTER TABLE disruption_events ALTER COLUMN {column} SET DEFAULT 'PENDING'")
                else:
                    # SQLite syntax with defaults
                    if column == 'delay_minutes':
                        column_type += " DEFAULT 0"
                    elif column == 'compensation_eligible':
                        column_type += " DEFAULT FALSE"
                    elif column == 'compensation_status':
                        column_type += " DEFAULT 'PENDING'"
                    migrations.append(f"ALTER TABLE disruption_events ADD COLUMN {column} {column_type}")
    
    return migrations


def run_migration_sql(engine, sql_commands: list) -> bool:
    """Execute SQL migration commands"""
    if not sql_commands:
        print("✓ No SQL migrations needed")
        return True
    
    print(f"Running {len(sql_commands)} SQL migration commands...")
    
    try:
        with engine.connect() as conn:
            for sql in sql_commands:
                try:
                    print(f"  Executing: {sql}")
                    conn.execute(text(sql))
                    conn.commit()
                except Exception as e:
                    # Some columns might already exist, which is OK
                    if "already exists" in str(e) or "duplicate column" in str(e).lower():
                        print(f"    (Column already exists, skipping)")
                    else:
                        print(f"    ✗ Failed: {e}")
                        # Don't fail completely, continue with other migrations
                
        print("✓ SQL migrations completed")
        return True
                
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        return False


def create_new_tables(engine) -> bool:
    """Create new tables using SQLAlchemy metadata"""
    try:
        print("Creating new database tables...")
        
        # This will create all tables defined in our models
        # If tables already exist, SQLAlchemy will skip them
        Base.metadata.create_all(bind=engine)
        
        print("✓ Database tables created/verified successfully")
        return True
        
    except SQLAlchemyError as e:
        print(f"✗ Failed to create tables: {e}")
        return False


def verify_migration(engine) -> bool:
    """Verify that the migration was successful"""
    print("Verifying migration...")
    
    expected_tables = [
        'users', 'email_connections', 'flights', 'travelers', 'bookings', 
        'trip_monitors', 'disruption_events', 'wallets', 'wallet_transactions',
        'compensation_rules', 'compensation_rule_history'
    ]
    
    try:
        existing_tables = get_existing_tables(engine)
        
        all_good = True
        for table in expected_tables:
            if table in existing_tables:
                print(f"  ✓ Table '{table}' exists")
            else:
                print(f"  ✗ Table '{table}' missing")
                all_good = False
        
        if not all_good:
            return False
        
        # Check key columns in new tables
        inspector = inspect(engine)
        
        # Check flights table structure
        if 'flights' in existing_tables:
            flight_columns = [col['name'] for col in inspector.get_columns('flights')]
            required_flight_columns = ['flight_id', 'airline', 'flight_number', 'departure_airport', 'arrival_airport']
            for col in required_flight_columns:
                if col in flight_columns:
                    print(f"    ✓ Flight column '{col}' exists")
                else:
                    print(f"    ✗ Flight column '{col}' missing")
                    all_good = False
        
        # Check travelers table structure
        if 'travelers' in existing_tables:
            traveler_columns = [col['name'] for col in inspector.get_columns('travelers')]
            required_traveler_columns = ['traveler_id', 'user_id', 'first_name', 'last_name']
            for col in required_traveler_columns:
                if col in traveler_columns:
                    print(f"    ✓ Traveler column '{col}' exists")
                else:
                    print(f"    ✗ Traveler column '{col}' missing")
                    all_good = False
        
        # Check trip_monitors table structure
        if 'trip_monitors' in existing_tables:
            monitor_columns = [col['name'] for col in inspector.get_columns('trip_monitors')]
            required_monitor_columns = ['monitor_id', 'user_id', 'booking_id', 'flight_id']
            for col in required_monitor_columns:
                if col in monitor_columns:
                    print(f"    ✓ TripMonitor column '{col}' exists")
                else:
                    print(f"    ✗ TripMonitor column '{col}' missing")
                    all_good = False
        
        if all_good:
            print("✓ Migration verification successful")
        return all_good
        
    except Exception as e:
        print(f"✗ Migration verification failed: {e}")
        return False


def show_model_summary():
    """Show a summary of the new models and their purposes"""
    print("\n📋 Flight Monitoring Data Models Summary:")
    print("="*50)
    
    print("\n🛩️  Flight Model:")
    print("   • Stores comprehensive flight information")
    print("   • Tracks scheduled vs actual times, delays, gates")
    print("   • Supports real-time flight status updates")
    print("   • Links to bookings and trip monitors")
    
    print("\n👤 Traveler Model:")
    print("   • Stores passenger personal information")
    print("   • Manages passport, known traveler numbers")
    print("   • Tracks dietary restrictions and preferences")
    print("   • Links travelers to users and bookings")
    
    print("\n📱 TripMonitor Model:")
    print("   • Automated monitoring of flight status")
    print("   • Configurable notification preferences")
    print("   • Supports escalation rules and auto-rebooking")
    print("   • Links users to specific flights and bookings")
    
    print("\n🎫 Enhanced Booking Model:")
    print("   • Links to Flight and Traveler models")
    print("   • Stores fare information and ticket details")
    print("   • Tracks booking status and timestamps")
    print("   • Supports comprehensive trip management")
    
    print("\n⚠️  Enhanced DisruptionEvent Model:")
    print("   • Tracks delay minutes and disruption reasons")
    print("   • Supports compensation eligibility tracking")
    print("   • Records notification timestamps")
    print("   • Links to booking and flight information")


def main():
    """Main migration function"""
    parser = argparse.ArgumentParser(description='Migrate flight monitoring database schema')
    parser.add_argument('--backup', action='store_true', help='Create backup before migration (SQLite only)')
    parser.add_argument('--force', action='store_true', help='Force migration even if tables exist')
    args = parser.parse_args()
    
    print("Flight Monitoring Database Migration")
    print("=" * 40)
    print(f"Database URL: {DATABASE_URL}")
    
    db_type = get_db_type(engine)
    print(f"Database Type: {db_type}")
    
    # Extract database path for SQLite
    db_path = None
    if DATABASE_URL.startswith('sqlite:///'):
        db_path = DATABASE_URL.replace('sqlite:///', '')
        print(f"Database file: {db_path}")
    
    # Create backup if requested (SQLite only)
    if args.backup and db_path:
        backup_path = backup_database(db_path)
        if not backup_path:
            print("Warning: Backup failed, continuing anyway...")
    elif args.backup and not db_path:
        print("Note: Backup only supported for SQLite databases")
    
    # Check current state
    existing_tables = get_existing_tables(engine)
    print(f"Existing tables: {len(existing_tables)} tables found")
    
    # Check if migration is needed
    new_tables = ['flights', 'travelers', 'trip_monitors']
    needs_migration = not all(table in existing_tables for table in new_tables)
    
    if not needs_migration and not args.force:
        print("✓ All required tables already exist. Use --force to run anyway.")
        show_model_summary()
        return True
    
    # Step 1: Create new tables (this is safe, will skip existing ones)
    print("\nStep 1: Creating/verifying database tables...")
    if not create_new_tables(engine):
        print("✗ Table creation failed")
        return False
    
    # Step 2: Add missing columns to existing tables
    print("\nStep 2: Adding missing columns to existing tables...")
    sql_migrations = add_missing_columns(engine)
    if not run_migration_sql(engine, sql_migrations):
        print("✗ Column migrations failed")
        return False
    
    # Step 3: Verify migration
    print("\nStep 3: Verifying migration...")
    if not verify_migration(engine):
        print("✗ Migration verification failed")
        return False
    
    print("\n" + "=" * 40)
    print("✅ Database migration completed successfully!")
    
    show_model_summary()
    
    print("\n🚀 Ready for flight monitoring operations!")
    print("   You can now use the new models for comprehensive")
    print("   flight tracking, passenger management, and automated monitoring.")
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)