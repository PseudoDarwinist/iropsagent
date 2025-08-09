# tests/trip_saver/test_api.py
import unittest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from trip_saver_api import app


class TestTripSaverAPI(unittest.TestCase):
    """Test cases for Trip Saver API endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        app.config['TESTING'] = True
        self.client = app.test_client()
        
        self.sample_trip = {
            'user_id': 'test_user_123',
            'trip_name': 'Test Business Trip',
            'start_date': (datetime.utcnow() + timedelta(days=30)).isoformat(),
            'end_date': (datetime.utcnow() + timedelta(days=35)).isoformat(),
            'origin': 'LAX',
            'destination': 'JFK',
            'trip_type': 'ROUND_TRIP',
            'priority': 'HIGH'
        }
    
    def test_index_endpoint(self):
        """Test the main index endpoint"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('stats', data)
        self.assertIn('message', data)
    
    @patch('trip_saver_api.trip_service.create_trip_plan')
    def test_create_trip_success(self, mock_create_trip):
        """Test successful trip creation"""
        # Mock service response
        mock_trip = MagicMock()
        mock_trip.trip_id = 'trip_test_123'
        mock_trip.trip_name = self.sample_trip['trip_name']
        mock_trip.start_date = datetime.fromisoformat(self.sample_trip['start_date'])
        mock_trip.end_date = datetime.fromisoformat(self.sample_trip['end_date'])
        mock_trip.origin = self.sample_trip['origin']
        mock_trip.destination = self.sample_trip['destination']
        mock_trip.status = 'PLANNED'
        mock_trip.priority = self.sample_trip['priority']
        
        mock_create_trip.return_value = mock_trip
        
        # Make request
        response = self.client.post(
            '/api/trips',
            data=json.dumps(self.sample_trip),
            content_type='application/json'
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('trip', data)
        self.assertEqual(data['trip']['trip_name'], self.sample_trip['trip_name'])
    
    def test_create_trip_missing_fields(self):
        """Test trip creation with missing required fields"""
        incomplete_trip = {
            'user_id': 'test_user_123',
            'trip_name': 'Test Trip'
            # Missing required fields
        }
        
        response = self.client.post(
            '/api/trips',
            data=json.dumps(incomplete_trip),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('error', data)
    
    def test_create_trip_invalid_date_format(self):
        """Test trip creation with invalid date format"""
        invalid_trip = self.sample_trip.copy()
        invalid_trip['start_date'] = 'invalid-date-format'
        
        response = self.client.post(
            '/api/trips',
            data=json.dumps(invalid_trip),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('Invalid date format', data['error'])
    
    @patch('trip_saver_api.trip_service.get_active_trips')
    def test_get_trips(self, mock_get_trips):
        """Test retrieving trips"""
        # Mock service response
        mock_trip = MagicMock()
        mock_trip.trip_id = 'trip_test_123'
        mock_trip.user_id = 'test_user_123'
        mock_trip.trip_name = 'Test Trip'
        mock_trip.start_date = datetime.utcnow() + timedelta(days=30)
        mock_trip.end_date = datetime.utcnow() + timedelta(days=35)
        mock_trip.origin = 'LAX'
        mock_trip.destination = 'JFK'
        mock_trip.trip_type = 'ROUND_TRIP'
        mock_trip.status = 'PLANNED'
        mock_trip.priority = 'HIGH'
        mock_trip.created_at = datetime.utcnow()
        
        mock_get_trips.return_value = [mock_trip]
        
        # Make request
        response = self.client.get('/api/trips?user_id=test_user_123')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 1)
        self.assertIn('trips', data)
    
    @patch('trip_saver_api.alert_service.create_alert')
    def test_create_alert_success(self, mock_create_alert):
        """Test successful alert creation"""
        alert_data = {
            'trip_id': 'trip_test_123',
            'alert_type': 'WEATHER',
            'title': 'Weather Alert',
            'description': 'Severe weather expected at destination',
            'severity': 'HIGH'
        }
        
        # Mock service response
        mock_alert = MagicMock()
        mock_alert.alert_id = 'alert_test_123'
        mock_alert.trip_id = alert_data['trip_id']
        mock_alert.alert_type = alert_data['alert_type']
        mock_alert.severity = alert_data['severity']
        mock_alert.title = alert_data['title']
        mock_alert.description = alert_data['description']
        mock_alert.detected_at = datetime.utcnow()
        mock_alert.is_active = True
        
        mock_create_alert.return_value = mock_alert
        
        # Make request
        response = self.client.post(
            '/api/alerts',
            data=json.dumps(alert_data),
            content_type='application/json'
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('alert', data)
        self.assertEqual(data['alert']['alert_type'], alert_data['alert_type'])


if __name__ == '__main__':
    unittest.main()