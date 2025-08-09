#!/usr/bin/env python3
"""
Proactive Trip Saver API
Flask-based web application for managing proactive trip planning and optimization
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import json
from datetime import datetime, timedelta
import os

# Import models and services
from trip_saver.models.trip_models import TripPlan, TripAlert, ProactiveSuggestion, TripOptimization
from trip_saver.services.trip_planning_service import TripPlanningService
from trip_saver.services.alert_service import AlertService
from trip_saver.services.suggestion_service import SuggestionService
from flight_agent.models import get_user_by_email

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Configure Flask for development
app.config['DEBUG'] = True

# Initialize services
trip_service = TripPlanningService()
alert_service = AlertService()
suggestion_service = SuggestionService()


@app.route('/')
def index():
    """Main dashboard showing trip saver overview"""
    try:
        # Get active trips summary
        active_trips = trip_service.get_active_trips()
        critical_alerts = alert_service.get_active_alerts(severity='CRITICAL')
        high_value_suggestions = suggestion_service.get_high_value_suggestions()
        
        # Statistics
        stats = {
            'active_trips': len(active_trips),
            'critical_alerts': len(critical_alerts),
            'pending_suggestions': len(high_value_suggestions),
            'total_potential_savings': sum(s.potential_savings for s in high_value_suggestions)
        }
        
        return jsonify({
            'success': True,
            'message': 'Proactive Trip Saver API',
            'stats': stats,
            'active_trips': len(active_trips),
            'critical_alerts': len(critical_alerts)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/trips', methods=['GET', 'POST'])
def manage_trips():
    """API endpoint for managing trip plans"""
    if request.method == 'POST':
        try:
            trip_data = request.get_json()
            if not trip_data:
                return jsonify({
                    'success': False,
                    'error': 'No trip data provided'
                }), 400
            
            # Validate required fields
            required_fields = ['user_id', 'trip_name', 'start_date', 'end_date', 'origin', 'destination']
            for field in required_fields:
                if field not in trip_data:
                    return jsonify({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }), 400
            
            # Parse dates
            try:
                trip_data['start_date'] = datetime.fromisoformat(trip_data['start_date'].replace('Z', '+00:00'))
                trip_data['end_date'] = datetime.fromisoformat(trip_data['end_date'].replace('Z', '+00:00'))
            except ValueError as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid date format: {str(e)}'
                }), 400
            
            # Create trip plan
            trip = trip_service.create_trip_plan(trip_data['user_id'], trip_data)
            
            return jsonify({
                'success': True,
                'trip': {
                    'trip_id': trip.trip_id,
                    'trip_name': trip.trip_name,
                    'start_date': trip.start_date.isoformat(),
                    'end_date': trip.end_date.isoformat(),
                    'origin': trip.origin,
                    'destination': trip.destination,
                    'status': trip.status,
                    'priority': trip.priority
                }
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    else:  # GET request
        try:
            user_id = request.args.get('user_id')
            status = request.args.get('status', 'active')
            
            if status == 'active':
                trips = trip_service.get_active_trips(user_id)
            else:
                # Could implement get_all_trips method for other statuses
                trips = trip_service.get_active_trips(user_id)
            
            trips_data = []
            for trip in trips:
                trips_data.append({
                    'trip_id': trip.trip_id,
                    'user_id': trip.user_id,
                    'trip_name': trip.trip_name,
                    'start_date': trip.start_date.isoformat(),
                    'end_date': trip.end_date.isoformat(),
                    'origin': trip.origin,
                    'destination': trip.destination,
                    'trip_type': trip.trip_type,
                    'status': trip.status,
                    'priority': trip.priority,
                    'created_at': trip.created_at.isoformat() if trip.created_at else None
                })
            
            return jsonify({
                'success': True,
                'trips': trips_data,
                'count': len(trips_data)
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


@app.route('/api/alerts', methods=['GET', 'POST'])
def manage_alerts():
    """API endpoint for managing trip alerts"""
    if request.method == 'POST':
        try:
            alert_data = request.get_json()
            if not alert_data:
                return jsonify({
                    'success': False,
                    'error': 'No alert data provided'
                }), 400
            
            # Validate required fields
            required_fields = ['trip_id', 'alert_type', 'title', 'description']
            for field in required_fields:
                if field not in alert_data:
                    return jsonify({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }), 400
            
            # Parse expires_at if provided
            if 'expires_at' in alert_data:
                try:
                    alert_data['expires_at'] = datetime.fromisoformat(
                        alert_data['expires_at'].replace('Z', '+00:00')
                    )
                except ValueError:
                    return jsonify({
                        'success': False,
                        'error': 'Invalid expires_at date format'
                    }), 400
            
            # Create alert
            alert = alert_service.create_alert(alert_data['trip_id'], alert_data)
            
            return jsonify({
                'success': True,
                'alert': {
                    'alert_id': alert.alert_id,
                    'trip_id': alert.trip_id,
                    'alert_type': alert.alert_type,
                    'severity': alert.severity,
                    'title': alert.title,
                    'description': alert.description,
                    'detected_at': alert.detected_at.isoformat(),
                    'is_active': alert.is_active
                }
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    else:  # GET request
        try:
            trip_id = request.args.get('trip_id')
            severity = request.args.get('severity')
            active_only = request.args.get('active_only', 'true').lower() == 'true'
            
            if active_only:
                alerts = alert_service.get_active_alerts(trip_id, severity)
            else:
                # For now, just return active alerts
                alerts = alert_service.get_active_alerts(trip_id, severity)
            
            alerts_data = []
            for alert in alerts:
                alerts_data.append({
                    'alert_id': alert.alert_id,
                    'trip_id': alert.trip_id,
                    'alert_type': alert.alert_type,
                    'severity': alert.severity,
                    'title': alert.title,
                    'description': alert.description,
                    'detected_at': alert.detected_at.isoformat(),
                    'expires_at': alert.expires_at.isoformat() if alert.expires_at else None,
                    'is_active': alert.is_active,
                    'user_notified': alert.user_notified
                })
            
            return jsonify({
                'success': True,
                'alerts': alerts_data,
                'count': len(alerts_data)
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


@app.route('/api/suggestions', methods=['GET', 'POST'])
def manage_suggestions():
    """API endpoint for managing proactive suggestions"""
    if request.method == 'POST':
        try:
            suggestion_data = request.get_json()
            if not suggestion_data:
                return jsonify({
                    'success': False,
                    'error': 'No suggestion data provided'
                }), 400
            
            # Validate required fields
            required_fields = ['trip_id', 'suggestion_type', 'title', 'description']
            for field in required_fields:
                if field not in suggestion_data:
                    return jsonify({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }), 400
            
            # Parse expires_at if provided
            if 'expires_at' in suggestion_data:
                try:
                    suggestion_data['expires_at'] = datetime.fromisoformat(
                        suggestion_data['expires_at'].replace('Z', '+00:00')
                    )
                except ValueError:
                    return jsonify({
                        'success': False,
                        'error': 'Invalid expires_at date format'
                    }), 400
            
            # Create suggestion
            suggestion = suggestion_service.create_suggestion(
                suggestion_data['trip_id'], suggestion_data
            )
            
            return jsonify({
                'success': True,
                'suggestion': {
                    'suggestion_id': suggestion.suggestion_id,
                    'trip_id': suggestion.trip_id,
                    'suggestion_type': suggestion.suggestion_type,
                    'title': suggestion.title,
                    'description': suggestion.description,
                    'confidence_score': suggestion.confidence_score,
                    'potential_savings': suggestion.potential_savings,
                    'time_savings_minutes': suggestion.time_savings_minutes,
                    'status': suggestion.status,
                    'created_at': suggestion.created_at.isoformat()
                }
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    else:  # GET request
        try:
            trip_id = request.args.get('trip_id')
            min_confidence = float(request.args.get('min_confidence', 0.5))
            status = request.args.get('status', 'PENDING')
            
            if status == 'PENDING':
                suggestions = suggestion_service.get_active_suggestions(trip_id, min_confidence)
            else:
                # Could implement method to get suggestions by status
                suggestions = suggestion_service.get_active_suggestions(trip_id, min_confidence)
            
            suggestions_data = []
            for suggestion in suggestions:
                suggestions_data.append({
                    'suggestion_id': suggestion.suggestion_id,
                    'trip_id': suggestion.trip_id,
                    'suggestion_type': suggestion.suggestion_type,
                    'title': suggestion.title,
                    'description': suggestion.description,
                    'confidence_score': suggestion.confidence_score,
                    'potential_savings': suggestion.potential_savings,
                    'time_savings_minutes': suggestion.time_savings_minutes,
                    'status': suggestion.status,
                    'created_at': suggestion.created_at.isoformat(),
                    'expires_at': suggestion.expires_at.isoformat() if suggestion.expires_at else None
                })
            
            return jsonify({
                'success': True,
                'suggestions': suggestions_data,
                'count': len(suggestions_data)
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


@app.route('/api/suggestions/<suggestion_id>/respond', methods=['POST'])
def respond_to_suggestion(suggestion_id):
    """API endpoint to respond to a suggestion"""
    try:
        response_data = request.get_json()
        if not response_data or 'status' not in response_data:
            return jsonify({
                'success': False,
                'error': 'Status is required'
            }), 400
        
        status = response_data['status']
        if status not in ['ACCEPTED', 'REJECTED']:
            return jsonify({
                'success': False,
                'error': 'Status must be ACCEPTED or REJECTED'
            }), 400
        
        suggestion = suggestion_service.respond_to_suggestion(suggestion_id, status)
        if not suggestion:
            return jsonify({
                'success': False,
                'error': 'Suggestion not found'
            }), 404
        
        return jsonify({
            'success': True,
            'suggestion': {
                'suggestion_id': suggestion.suggestion_id,
                'status': suggestion.status,
                'user_response_at': suggestion.user_response_at.isoformat() if suggestion.user_response_at else None
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/monitoring/trips')
def get_monitoring_trips():
    """API endpoint to get trips requiring monitoring"""
    try:
        days_ahead = int(request.args.get('days_ahead', 7))
        trips = trip_service.get_trips_requiring_monitoring(days_ahead)
        
        trips_data = []
        for trip in trips:
            # Get trip risk analysis
            risk_analysis = trip_service.analyze_trip_risks(trip.trip_id)
            
            trips_data.append({
                'trip_id': trip.trip_id,
                'trip_name': trip.trip_name,
                'start_date': trip.start_date.isoformat(),
                'origin': trip.origin,
                'destination': trip.destination,
                'priority': trip.priority,
                'risk_analysis': risk_analysis
            })
        
        return jsonify({
            'success': True,
            'trips': trips_data,
            'count': len(trips_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # Ensure database tables exist
    from flight_agent.models import Base, engine
    Base.metadata.create_all(bind=engine)
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5001)