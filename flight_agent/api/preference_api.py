# flight_agent/api/preference_api.py
"""
API endpoints for managing user communication preferences.
This module provides functions that can be called by the ADK agents or external services.
"""
from typing import Dict, Any, Optional
from datetime import datetime
from ..models import SessionLocal, User
from ..tools.preference_tools import (
    get_user_preferences,
    update_user_preferences,
    validate_notification_settings,
    get_default_preferences,
    get_user_preferences_by_email,
    update_user_preferences_by_email
)


class PreferenceAPI:
    """API class for managing user communication preferences"""
    
    @staticmethod
    def get_preferences(user_id: str) -> Dict[str, Any]:
        """Get user preferences by user ID"""
        try:
            return get_user_preferences(user_id)
        except Exception as e:
            return {"error": f"Failed to get preferences: {str(e)}"}
    
    @staticmethod
    def get_preferences_by_email(email: str) -> Dict[str, Any]:
        """Get user preferences by email"""
        try:
            return get_user_preferences_by_email(email)
        except Exception as e:
            return {"error": f"Failed to get preferences: {str(e)}"}
    
    @staticmethod
    def update_preferences(user_id: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Update user preferences by user ID"""
        try:
            return update_user_preferences(user_id, preferences)
        except Exception as e:
            return {"error": f"Failed to update preferences: {str(e)}"}
    
    @staticmethod
    def update_preferences_by_email(email: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Update user preferences by email"""
        try:
            return update_user_preferences_by_email(email, preferences)
        except Exception as e:
            return {"error": f"Failed to update preferences: {str(e)}"}
    
    @staticmethod
    def validate_settings(email: str = None, phone: str = None, 
                         enable_email: bool = False, enable_sms: bool = False) -> Dict[str, Any]:
        """Validate notification settings"""
        try:
            return validate_notification_settings(email, phone, enable_email, enable_sms)
        except Exception as e:
            return {"error": f"Failed to validate settings: {str(e)}"}
    
    @staticmethod
    def get_defaults() -> Dict[str, Any]:
        """Get default preferences"""
        try:
            return get_default_preferences()
        except Exception as e:
            return {"error": f"Failed to get default preferences: {str(e)}"}
    
    @staticmethod
    def bulk_update_notification_type(notification_type: str, enabled: bool, user_ids: list = None) -> Dict[str, Any]:
        """Bulk update a specific notification type for multiple users"""
        db = SessionLocal()
        try:
            query = db.query(User)
            if user_ids:
                query = query.filter(User.user_id.in_(user_ids))
            
            users = query.all()
            updated_count = 0
            
            for user in users:
                if user.notification_types is None:
                    user.notification_types = {}
                
                user.notification_types[notification_type] = enabled
                user.last_preference_update = datetime.utcnow()
                updated_count += 1
            
            db.commit()
            
            return {
                "success": True,
                "message": f"Updated {notification_type} to {enabled} for {updated_count} users",
                "updated_count": updated_count
            }
        
        except Exception as e:
            db.rollback()
            return {"error": f"Failed to bulk update: {str(e)}"}
        finally:
            db.close()
    
    @staticmethod
    def get_users_with_notification_enabled(notification_type: str) -> Dict[str, Any]:
        """Get all users who have a specific notification type enabled"""
        db = SessionLocal()
        try:
            users = db.query(User).filter(
                User.notification_types.isnot(None)
            ).all()
            
            enabled_users = []
            for user in users:
                if user.notification_types and user.notification_types.get(notification_type, False):
                    enabled_users.append({
                        "user_id": user.user_id,
                        "email": user.email,
                        "phone": user.phone,
                        "enable_email_notifications": user.enable_email_notifications,
                        "enable_sms_notifications": user.enable_sms_notifications,
                        "notification_frequency": user.notification_frequency
                    })
            
            return {
                "notification_type": notification_type,
                "enabled_users": enabled_users,
                "count": len(enabled_users)
            }
        
        except Exception as e:
            return {"error": f"Failed to get users: {str(e)}"}
        finally:
            db.close()


# Convenience functions for direct use
def get_user_communication_preferences(user_id: str) -> Dict[str, Any]:
    """Get user communication preferences - convenience function"""
    return PreferenceAPI.get_preferences(user_id)


def update_user_communication_preferences(user_id: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
    """Update user communication preferences - convenience function"""
    return PreferenceAPI.update_preferences(user_id, preferences)


def validate_user_notification_settings(email: str = None, phone: str = None, 
                                       enable_email: bool = False, enable_sms: bool = False) -> Dict[str, Any]:
    """Validate user notification settings - convenience function"""
    return PreferenceAPI.validate_settings(email, phone, enable_email, enable_sms)