# tests/trip_saver/test_trip_planning_service.py
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from trip_saver.services.trip_planning_service import TripPlanningService
from trip_saver.models.trip_models import TripPlan


class TestTripPlanningService(unittest.TestCase):
    """Test cases for TripPlanningService"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = TripPlanningService()
        self.sample_trip_data = {
            'trip_name': 'Business Trip to NYC',
            'start_date': datetime.utcnow() + timedelta(days=30),
            'end_date': datetime.utcnow() + timedelta(days=35),
            'origin': 'LAX',
            'destination': 'JFK',
            'trip_type': 'ROUND_TRIP',
            'priority': 'HIGH',
            'preferences': {
                'seat_preference': 'aisle',
                'meal_preference': 'vegetarian'
            }
        }
    
    @patch('trip_saver.services.trip_planning_service.SessionLocal')
    def test_create_trip_plan_success(self, mock_session):
        """Test successful trip plan creation"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Mock created trip
        mock_trip = MagicMock()
        mock_trip.trip_id = 'trip_test_user_123456.789'
        mock_trip.trip_name = self.sample_trip_data['trip_name']
        mock_trip.user_id = 'test_user'
        
        # Execute
        result = self.service.create_trip_plan('test_user', self.sample_trip_data)
        
        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        mock_db.close.assert_called_once()
    
    @patch('trip_saver.services.trip_planning_service.SessionLocal')
    def test_get_active_trips(self, mock_session):
        """Test retrieving active trips"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Mock query results
        mock_trips = [MagicMock(), MagicMock()]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_trips
        
        # Execute
        result = self.service.get_active_trips()
        
        # Verify
        self.assertEqual(len(result), 2)
        mock_db.query.assert_called_once()
        mock_db.close.assert_called_once()
    
    @patch('trip_saver.services.trip_planning_service.SessionLocal')
    def test_update_trip_status(self, mock_session):
        """Test updating trip status"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Mock trip
        mock_trip = MagicMock()
        mock_trip.trip_id = 'test_trip_id'
        mock_db.query.return_value.filter.return_value.first.return_value = mock_trip
        
        # Execute
        result = self.service.update_trip_status('test_trip_id', 'ACTIVE')
        
        # Verify
        self.assertEqual(mock_trip.status, 'ACTIVE')
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        mock_db.close.assert_called_once()
    
    def test_analyze_trip_risks(self):
        """Test trip risk analysis"""
        # Execute
        result = self.service.analyze_trip_risks('test_trip_id')
        
        # Verify structure
        self.assertIsInstance(result, dict)
        self.assertIn('weather_risk', result)
        self.assertIn('strike_risk', result)
        self.assertIn('airport_congestion_risk', result)
        self.assertIn('price_volatility_risk', result)
        self.assertIn('overall_risk_score', result)
        self.assertIsInstance(result['overall_risk_score'], float)


if __name__ == '__main__':
    unittest.main()