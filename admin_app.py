#!/usr/bin/env python3
"""
IROPS Agent Admin Interface
Flask-based web application for managing compensation rules
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import json
from datetime import datetime
import os

# Import models and functions
from flight_agent.models import (
    create_compensation_rule, update_compensation_rule, get_all_compensation_rules,
    get_compensation_rule_by_id, deactivate_compensation_rule, get_compensation_rule_history,
    validate_compensation_rule, get_active_compensation_rules, CompensationRule
)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Configure Flask for development
app.config['DEBUG'] = True


@app.route('/')
def index():
    """Main dashboard showing compensation rules overview"""
    try:
        all_rules = get_all_compensation_rules()
        active_rules = [rule for rule in all_rules if rule.is_active]
        inactive_rules = [rule for rule in all_rules if not rule.is_active]
        
        # Statistics
        stats = {
            'total_rules': len(all_rules),
            'active_rules': len(active_rules),
            'inactive_rules': len(inactive_rules),
            'disruption_types': {}
        }
        
        # Count rules by disruption type
        for rule in active_rules:
            disruption_type = rule.disruption_type
            if disruption_type not in stats['disruption_types']:
                stats['disruption_types'][disruption_type] = 0
            stats['disruption_types'][disruption_type] += 1
        
        return render_template('admin/index.html', 
                             active_rules=active_rules,
                             inactive_rules=inactive_rules,
                             stats=stats)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('admin/index.html', 
                             active_rules=[], 
                             inactive_rules=[], 
                             stats={})


@app.route('/rules')
def list_rules():
    """List all compensation rules with filtering and sorting"""
    disruption_type = request.args.get('disruption_type', '')
    status = request.args.get('status', 'all')  # all, active, inactive
    sort_by = request.args.get('sort', 'priority')  # priority, created_at, amount
    
    try:
        if disruption_type:
            if status == 'active':
                rules = get_active_compensation_rules(disruption_type)
            else:
                all_rules = get_all_compensation_rules()
                rules = [r for r in all_rules if r.disruption_type == disruption_type]
        else:
            if status == 'active':
                rules = get_active_compensation_rules()
            elif status == 'inactive':
                all_rules = get_all_compensation_rules()
                rules = [r for r in all_rules if not r.is_active]
            else:
                rules = get_all_compensation_rules()
        
        # Sort rules
        if sort_by == 'priority':
            rules.sort(key=lambda x: x.priority, reverse=True)
        elif sort_by == 'amount':
            rules.sort(key=lambda x: x.amount, reverse=True)
        elif sort_by == 'created_at':
            rules.sort(key=lambda x: x.created_at, reverse=True)
        
        disruption_types = ['CANCELLED', 'DELAYED', 'DIVERTED', 'OVERBOOKED']
        
        return render_template('admin/rules_list.html',
                             rules=rules,
                             disruption_types=disruption_types,
                             current_filters={
                                 'disruption_type': disruption_type,
                                 'status': status,
                                 'sort': sort_by
                             })
    except Exception as e:
        flash(f'Error loading rules: {str(e)}', 'error')
        return render_template('admin/rules_list.html', rules=[])


@app.route('/rules/new', methods=['GET', 'POST'])
def create_rule():
    """Create a new compensation rule"""
    if request.method == 'POST':
        try:
            # Parse form data
            rule_data = {
                'rule_name': request.form.get('rule_name', '').strip(),
                'description': request.form.get('description', '').strip(),
                'disruption_type': request.form.get('disruption_type', '').strip(),
                'amount': float(request.form.get('amount', 0)),
                'priority': int(request.form.get('priority', 0)),
                'conditions': {}
            }
            
            # Parse conditions from form
            conditions_json = request.form.get('conditions', '').strip()
            if conditions_json:
                try:
                    rule_data['conditions'] = json.loads(conditions_json)
                except json.JSONDecodeError:
                    flash('Invalid JSON format in conditions', 'error')
                    return render_template('admin/rule_form.html', 
                                         rule=None, 
                                         disruption_types=['CANCELLED', 'DELAYED', 'DIVERTED', 'OVERBOOKED'])
            
            # Validate rule data
            validation_result = validate_compensation_rule(rule_data)
            
            if not validation_result['valid']:
                for error in validation_result['errors']:
                    flash(error, 'error')
                return render_template('admin/rule_form.html', 
                                     rule=None, 
                                     rule_data=rule_data,
                                     disruption_types=['CANCELLED', 'DELAYED', 'DIVERTED', 'OVERBOOKED'])
            
            # Show warnings but continue
            for warning in validation_result['warnings']:
                flash(warning, 'warning')
            
            # Create the rule
            new_rule = create_compensation_rule(rule_data, created_by='admin')
            flash(f'Compensation rule "{new_rule.rule_name}" created successfully!', 'success')
            return redirect(url_for('view_rule', rule_id=new_rule.rule_id))
            
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'error')
        except Exception as e:
            flash(f'Error creating rule: {str(e)}', 'error')
    
    return render_template('admin/rule_form.html', 
                         rule=None, 
                         disruption_types=['CANCELLED', 'DELAYED', 'DIVERTED', 'OVERBOOKED'])


@app.route('/rules/<rule_id>')
def view_rule(rule_id):
    """View details of a specific compensation rule"""
    try:
        rule = get_compensation_rule_by_id(rule_id)
        if not rule:
            flash('Compensation rule not found', 'error')
            return redirect(url_for('list_rules'))
        
        # Get rule history for audit trail
        history = get_compensation_rule_history(rule_id)
        
        return render_template('admin/rule_detail.html', rule=rule, history=history)
    except Exception as e:
        flash(f'Error loading rule: {str(e)}', 'error')
        return redirect(url_for('list_rules'))


@app.route('/rules/<rule_id>/edit', methods=['GET', 'POST'])
def edit_rule(rule_id):
    """Edit an existing compensation rule"""
    try:
        rule = get_compensation_rule_by_id(rule_id)
        if not rule:
            flash('Compensation rule not found', 'error')
            return redirect(url_for('list_rules'))
        
        if request.method == 'POST':
            # Parse form data
            updated_data = {
                'rule_name': request.form.get('rule_name', '').strip(),
                'description': request.form.get('description', '').strip(),
                'disruption_type': request.form.get('disruption_type', '').strip(),
                'amount': float(request.form.get('amount', 0)),
                'priority': int(request.form.get('priority', 0)),
                'conditions': {}
            }
            
            # Parse conditions from form
            conditions_json = request.form.get('conditions', '').strip()
            if conditions_json:
                try:
                    updated_data['conditions'] = json.loads(conditions_json)
                except json.JSONDecodeError:
                    flash('Invalid JSON format in conditions', 'error')
                    return render_template('admin/rule_form.html', 
                                         rule=rule, 
                                         disruption_types=['CANCELLED', 'DELAYED', 'DIVERTED', 'OVERBOOKED'])
            
            # Validate rule data
            validation_result = validate_compensation_rule(updated_data)
            
            if not validation_result['valid']:
                for error in validation_result['errors']:
                    flash(error, 'error')
                return render_template('admin/rule_form.html', 
                                     rule=rule, 
                                     rule_data=updated_data,
                                     disruption_types=['CANCELLED', 'DELAYED', 'DIVERTED', 'OVERBOOKED'])
            
            # Show warnings but continue
            for warning in validation_result['warnings']:
                flash(warning, 'warning')
            
            # Update the rule
            updated_rule = update_compensation_rule(rule_id, updated_data, updated_by='admin')
            flash(f'Compensation rule "{updated_rule.rule_name}" updated successfully!', 'success')
            return redirect(url_for('view_rule', rule_id=rule_id))
        
        return render_template('admin/rule_form.html', 
                             rule=rule, 
                             disruption_types=['CANCELLED', 'DELAYED', 'DIVERTED', 'OVERBOOKED'])
        
    except ValueError as e:
        flash(f'Invalid input: {str(e)}', 'error')
        return redirect(url_for('list_rules'))
    except Exception as e:
        flash(f'Error editing rule: {str(e)}', 'error')
        return redirect(url_for('list_rules'))


@app.route('/rules/<rule_id>/toggle', methods=['POST'])
def toggle_rule(rule_id):
    """Toggle rule activation status"""
    try:
        rule = get_compensation_rule_by_id(rule_id)
        if not rule:
            flash('Compensation rule not found', 'error')
            return redirect(url_for('list_rules'))
        
        if rule.is_active:
            # Deactivate rule
            updated_rule = deactivate_compensation_rule(rule_id, deactivated_by='admin')
            flash(f'Rule "{updated_rule.rule_name}" deactivated successfully!', 'success')
        else:
            # Reactivate rule
            updated_rule = update_compensation_rule(rule_id, {'is_active': True}, updated_by='admin')
            flash(f'Rule "{updated_rule.rule_name}" activated successfully!', 'success')
        
        return redirect(url_for('view_rule', rule_id=rule_id))
        
    except Exception as e:
        flash(f'Error toggling rule status: {str(e)}', 'error')
        return redirect(url_for('list_rules'))


@app.route('/api/rules')
def api_rules():
    """API endpoint to get all compensation rules as JSON"""
    try:
        disruption_type = request.args.get('disruption_type')
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        
        if active_only:
            rules = get_active_compensation_rules(disruption_type)
        else:
            rules = get_all_compensation_rules()
            if disruption_type:
                rules = [r for r in rules if r.disruption_type == disruption_type]
        
        # Convert to JSON-serializable format
        rules_data = []
        for rule in rules:
            rules_data.append({
                'rule_id': rule.rule_id,
                'rule_name': rule.rule_name,
                'description': rule.description,
                'disruption_type': rule.disruption_type,
                'amount': rule.amount,
                'conditions': rule.conditions,
                'priority': rule.priority,
                'is_active': rule.is_active,
                'version': rule.version,
                'created_at': rule.created_at.isoformat() if rule.created_at else None,
                'updated_at': rule.updated_at.isoformat() if rule.updated_at else None,
                'created_by': rule.created_by
            })
        
        return jsonify({
            'success': True,
            'rules': rules_data,
            'count': len(rules_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/rules/validate', methods=['POST'])
def api_validate_rule():
    """API endpoint to validate a compensation rule"""
    try:
        rule_data = request.get_json()
        if not rule_data:
            return jsonify({
                'success': False,
                'error': 'No rule data provided'
            }), 400
        
        validation_result = validate_compensation_rule(rule_data)
        
        return jsonify({
            'success': True,
            'validation': validation_result
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
    app.run(debug=True, host='0.0.0.0', port=5000)