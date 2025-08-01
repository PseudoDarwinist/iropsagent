#!/usr/bin/env python3
"""
Migration script to add communication preferences to existing users.
This script updates the database schema and sets default preference values for existing users.

Usage:
    python3 migrate_user_preferences.py [--dry-run]
"""
import argparse
import sys
from datetime import datetime
from flight_agent.models import SessionLocal, User, Base, engine
from flight_agent.tools.preference_tools import get_default_preferences


def migrate_user_preferences(dry_run=False):
    """Migrate existing users to have communication preferences"""
    
    print("Starting user preference migration...")
    print(f"Dry run mode: {dry_run}")
    
    # First, ensure the database schema is updated
    print("Updating database schema...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ Database schema updated successfully")
    except Exception as e:
        print(f"✗ Failed to update database schema: {e}")
        return False
    
    # Get default preferences
    default_prefs = get_default_preferences()
    
    db = SessionLocal()
    try:
        # Get all existing users
        users = db.query(User).all()
        print(f"Found {len(users)} users to migrate")
        
        if len(users) == 0:
            print("No users found to migrate")
            return True
        
        updated_count = 0
        skipped_count = 0
        
        for user in users:
            # Check if user already has communication preferences set
            needs_migration = (
                user.enable_email_notifications is None or
                user.notification_frequency is None or
                user.notification_types is None
            )
            
            if not needs_migration:
                print(f"Skipping user {user.email} - already has preferences")
                skipped_count += 1
                continue
            
            print(f"Migrating user: {user.email}")
            
            if not dry_run:
                # Set default communication preferences
                user.enable_email_notifications = default_prefs["enable_email_notifications"]
                user.enable_sms_notifications = default_prefs["enable_sms_notifications"] 
                user.notification_frequency = default_prefs["notification_frequency"]
                user.notification_types = default_prefs["notification_types"]
                user.quiet_hours_start = default_prefs["quiet_hours_start"]
                user.quiet_hours_end = default_prefs["quiet_hours_end"]
                user.timezone = default_prefs["timezone"]
                user.last_preference_update = datetime.utcnow()
                
                # Enable SMS only if user has a phone number
                if user.phone:
                    print(f"  User has phone number, keeping SMS enabled as default")
                else:
                    user.enable_sms_notifications = False
                    print(f"  User has no phone number, disabling SMS notifications")
            
            updated_count += 1
            
            # Show what would be set
            print(f"  Email notifications: {default_prefs['enable_email_notifications']}")
            print(f"  SMS notifications: {default_prefs['enable_sms_notifications'] if user.phone else False}")
            print(f"  Notification frequency: {default_prefs['notification_frequency']}")
            print(f"  Quiet hours: {default_prefs['quiet_hours_start']} - {default_prefs['quiet_hours_end']}")
        
        if not dry_run:
            # Commit all changes
            db.commit()
            print(f"✓ Successfully migrated {updated_count} users")
        else:
            print(f"✓ Dry run complete - would migrate {updated_count} users")
        
        print(f"Migration summary:")
        print(f"  Total users: {len(users)}")
        print(f"  Updated: {updated_count}")
        print(f"  Skipped (already migrated): {skipped_count}")
        
        return True
        
    except Exception as e:
        if not dry_run:
            db.rollback()
        print(f"✗ Migration failed: {e}")
        return False
        
    finally:
        db.close()


def verify_migration():
    """Verify that the migration was successful"""
    print("\nVerifying migration...")
    
    db = SessionLocal()
    try:
        users = db.query(User).all()
        
        migrated_count = 0
        for user in users:
            if (user.enable_email_notifications is not None and 
                user.notification_frequency is not None and
                user.notification_types is not None):
                migrated_count += 1
        
        print(f"✓ Verification complete: {migrated_count}/{len(users)} users have communication preferences")
        return migrated_count == len(users)
        
    except Exception as e:
        print(f"✗ Verification failed: {e}")
        return False
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate user communication preferences")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Show what would be migrated without making changes")
    parser.add_argument("--verify", action="store_true",
                       help="Verify that migration was successful")
    
    args = parser.parse_args()
    
    if args.verify:
        success = verify_migration()
        sys.exit(0 if success else 1)
    
    # Run the migration
    success = migrate_user_preferences(dry_run=args.dry_run)
    
    if success and not args.dry_run:
        # Verify the migration
        verify_migration()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()