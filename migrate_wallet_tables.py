#!/usr/bin/env python3
"""
Database Migration Script for Wallet Tables

This script creates the wallet and wallet_transaction tables in the existing
travel_disruption.db SQLite database for the IROPS Agent compensation system.
"""

import os
import sqlite3
import sys
from datetime import datetime

DATABASE_PATH = "./travel_disruption.db"


def check_database_exists():
    """Check if the database file exists"""
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ Database file {DATABASE_PATH} not found!")
        print("Please run the main application first to create the database.")
        return False
    return True


def check_table_exists(cursor, table_name):
    """Check if a table exists in the database"""
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None


def create_wallet_tables(cursor):
    """Create wallet and wallet_transaction tables"""
    
    # Create wallets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            wallet_id VARCHAR PRIMARY KEY,
            user_id VARCHAR UNIQUE NOT NULL,
            balance FLOAT DEFAULT 0.0,
            currency VARCHAR DEFAULT 'USD',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)
    
    # Create wallet_transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            transaction_id VARCHAR PRIMARY KEY,
            wallet_id VARCHAR NOT NULL,
            amount FLOAT NOT NULL,
            transaction_type VARCHAR NOT NULL,
            description VARCHAR,
            reference_id VARCHAR,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT,
            FOREIGN KEY (wallet_id) REFERENCES wallets (wallet_id)
        )
    """)
    
    # Create indexes for better performance
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_wallets_user_id 
        ON wallets (user_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_wallet_transactions_wallet_id 
        ON wallet_transactions (wallet_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_wallet_transactions_created_at 
        ON wallet_transactions (created_at)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_wallet_transactions_type 
        ON wallet_transactions (transaction_type)
    """)


def create_sample_wallet_data(cursor):
    """Create sample wallet data for testing"""
    
    # Check if users exist first
    cursor.execute("SELECT user_id FROM users LIMIT 3")
    users = cursor.fetchall()
    
    if not users:
        print("⚠️  No users found in database. Skipping sample data creation.")
        print("   Run the booking import process first to create test users.")
        return
    
    sample_wallets = []
    sample_transactions = []
    
    for i, user_row in enumerate(users[:3]):
        user_id = user_row[0]
        wallet_id = f"wallet_{user_id}_{int(datetime.now().timestamp())}_{i}"
        
        # Create wallet
        sample_wallets.append((
            wallet_id,
            user_id,
            100.0 if i == 0 else 0.0,  # First user gets some starting balance
            'USD',
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        # Create sample compensation transaction for first user
        if i == 0:
            sample_transactions.append((
                f"txn_{wallet_id}_compensation",
                wallet_id,
                100.0,
                'COMPENSATION',
                'Sample flight cancellation compensation',
                'sample_disruption_001',
                datetime.now().isoformat(),
                '{"disruption_type": "CANCELLED", "automatic_processing": true}'
            ))
    
    # Insert sample data
    if sample_wallets:
        cursor.executemany("""
            INSERT OR IGNORE INTO wallets 
            (wallet_id, user_id, balance, currency, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, sample_wallets)
        
        print(f"✅ Created {len(sample_wallets)} sample wallets")
    
    if sample_transactions:
        cursor.executemany("""
            INSERT OR IGNORE INTO wallet_transactions 
            (transaction_id, wallet_id, amount, transaction_type, description, reference_id, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_transactions)
        
        print(f"✅ Created {len(sample_transactions)} sample transactions")


def verify_migration(cursor):
    """Verify that the migration was successful"""
    
    # Check if tables exist
    tables_to_check = ['wallets', 'wallet_transactions']
    
    for table in tables_to_check:
        if check_table_exists(cursor, table):
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"✅ Table '{table}' exists with {count} records")
        else:
            print(f"❌ Table '{table}' was not created successfully")
            return False
    
    # Check foreign key constraints
    cursor.execute("PRAGMA foreign_key_check")
    fk_violations = cursor.fetchall()
    
    if fk_violations:
        print(f"⚠️  Found {len(fk_violations)} foreign key violations:")
        for violation in fk_violations:
            print(f"   {violation}")
    else:
        print("✅ No foreign key violations found")
    
    return True


def main():
    """Main migration function"""
    
    print("🚀 Starting wallet tables migration for IROPS Agent...")
    print("=" * 60)
    
    # Check if database exists
    if not check_database_exists():
        sys.exit(1)
    
    try:
        # Connect to database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Check existing tables
        print("📋 Checking existing database structure...")
        
        existing_tables = []
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for row in cursor.fetchall():
            existing_tables.append(row[0])
        
        print(f"   Found existing tables: {', '.join(existing_tables)}")
        
        # Check if wallet tables already exist
        if check_table_exists(cursor, 'wallets'):
            print("⚠️  Wallet tables already exist. Skipping creation.")
            create_sample = input("Create sample data? (y/N): ").lower() == 'y'
            if create_sample:
                create_sample_wallet_data(cursor)
                conn.commit()
        else:
            print("📝 Creating wallet tables...")
            create_wallet_tables(cursor)
            
            print("📊 Creating sample wallet data...")
            create_sample_wallet_data(cursor)
            
            # Commit changes
            conn.commit()
            print("💾 Changes committed to database")
        
        # Verify migration
        print("🔍 Verifying migration...")
        success = verify_migration(cursor)
        
        if success:
            print("\n🎉 Wallet tables migration completed successfully!")
            print("\nNext steps:")
            print("1. Test the compensation system with: python -c 'from flight_agent.tools.compensation_engine import test_compensation_scenarios; test_compensation_scenarios()'")
            print("2. Run the application and test wallet functionality")
            print("3. Check wallet balance with the agent: 'check my wallet'")
        else:
            print("\n❌ Migration completed with issues. Please check the errors above.")
            sys.exit(1)
    
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
    
    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    main()