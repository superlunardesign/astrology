"""
Flask API for Transit Tracker
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from transit_calculator import TransitCalculator
from datetime import datetime, timedelta
import traceback
import os

app = Flask(__name__)
CORS(app)

# Initialize transit calculator
tc = TransitCalculator()


@app.route('/')
def serve_frontend():
    """Serve the frontend HTML"""
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_dir, 'index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Transit Tracker API is running'})


@app.route('/api/charts', methods=['GET'])
def get_charts():
    """Get list of available charts"""
    return jsonify({
        'charts': [
            {'id': 'christina', 'name': 'Christina'},
            {'id': 'julian', 'name': 'Julian'},
            {'id': 'anna', 'name': 'Anna'},
            {'id': 'davison', 'name': 'Davison (Midpoint)'}
        ]
    })


@app.route('/api/chart/<chart_key>', methods=['GET'])
def get_chart(chart_key):
    """Get natal chart data"""
    try:
        chart = tc.ncm.get_chart(chart_key)

        # Format positions for display
        formatted_positions = {}
        for point_name, point_data in chart['positions'].items():
            formatted_positions[point_name] = {
                'longitude': point_data['longitude'],
                'formatted': tc.ncm.format_position(point_data['longitude'])
            }

        return jsonify({
            'name': chart['name'],
            'birth_data': chart['birth_data'],
            'positions': formatted_positions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/dashboard/<chart_key>', methods=['GET'])
def get_dashboard(chart_key):
    """
    Get daily dashboard for a chart

    Query params:
        date: Date in YYYY-MM-DD format (default: today)
        time: Time in HH:MM format (default: 12:00)
        timezone: Timezone string (default: America/Los_Angeles for Pacific)
        max_orb: Maximum orb in degrees (default: 3)
    """
    try:
        date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        time_str = request.args.get('time', '12:00')
        timezone = request.args.get('timezone', 'America/Los_Angeles')
        max_orb = float(request.args.get('max_orb', 3))

        # Validate date
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        # Validate time
        try:
            datetime.strptime(time_str, '%H:%M')
        except ValueError:
            return jsonify({'error': 'Invalid time format. Use HH:MM (24-hour)'}), 400

        dashboard = tc.get_daily_dashboard(chart_key, date_str, max_orb, time_str, timezone)

        # Format aspects for display
        for aspect in dashboard['aspects']:
            aspect['formatted'] = {
                'transit_long': tc.ncm.format_position(aspect['transit_longitude']),
                'natal_long': tc.ncm.format_position(aspect['natal_longitude']),
                'direction': '→ APPLYING' if aspect['is_applying'] else '← SEPARATING',
                'challenge_type': '⚠️ CHALLENGING' if aspect['is_challenging'] else '✓ SUPPORTIVE'
            }

        return jsonify(dashboard)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/timeline/<chart_key>/<transit_planet>/<natal_point>/<aspect_name>', methods=['GET'])
def get_aspect_timeline(chart_key, transit_planet, natal_point, aspect_name):
    """
    Get complete timeline for a specific aspect

    Query params:
        reference_date: Reference date (default: today)
        precise: If 'true', return exact times (hour/minute) for crossings
    """
    try:
        reference_date = request.args.get('reference_date', datetime.now().strftime('%Y-%m-%d'))
        precise = request.args.get('precise', 'false').lower() == 'true'

        # Validate date
        try:
            datetime.strptime(reference_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        timeline = tc.calculate_aspect_timeline(
            chart_key, transit_planet, natal_point, aspect_name, reference_date, precise=precise
        )

        # Calculate days remaining (handle both date and datetime formats)
        if timeline['leave_3deg']:
            leave_str = timeline['leave_3deg']
            # Handle datetime format (YYYY-MM-DD HH:MM) or date format (YYYY-MM-DD)
            leave_date = datetime.strptime(leave_str[:10], '%Y-%m-%d')
            today = datetime.strptime(reference_date, '%Y-%m-%d')
            days_remaining = (leave_date - today).days
            timeline['days_remaining'] = days_remaining
        else:
            timeline['days_remaining'] = None

        # Get current status
        aspects = tc.find_aspects(chart_key, reference_date, max_orb=5)
        current_aspect = None
        for aspect in aspects:
            if (aspect['transit_planet'] == transit_planet and
                aspect['natal_point'] == natal_point and
                aspect['aspect'] == aspect_name):
                current_aspect = aspect
                break

        return jsonify({
            'chart': chart_key,
            'transit_planet': transit_planet,
            'natal_point': natal_point,
            'aspect': aspect_name,
            'timeline': timeline,
            'current_status': current_aspect
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/scan/<chart_key>', methods=['GET'])
def scan_transits(chart_key):
    """
    Scan for upcoming exact transits

    Query params:
        start_date: Start date (default: today)
        end_date: End date (default: 180 days from start)
        planets: Comma-separated list of planets (default: all)
        aspects: Comma-separated list of aspects (default: all)
        min_significance: Minimum significance (CRITICAL, HIGH, MEDIUM, LOW) (default: LOW)
    """
    try:
        start_date = request.args.get('start_date', datetime.now().strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date')

        # Default end date to 180 days from start
        if not end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = start + timedelta(days=180)
            end_date = end.strftime('%Y-%m-%d')

        # Parse planets filter
        planets_str = request.args.get('planets')
        transit_planets = planets_str.split(',') if planets_str else None

        # Parse aspects filter
        aspects_str = request.args.get('aspects')
        aspect_types = aspects_str.split(',') if aspects_str else None

        # Parse significance filter
        min_significance = request.args.get('min_significance', 'LOW')

        # Validate significance
        valid_significance = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        if min_significance not in valid_significance:
            return jsonify({'error': f'Invalid significance. Must be one of: {valid_significance}'}), 400

        upcoming = tc.scan_future_transits(
            chart_key, start_date, end_date,
            transit_planets, aspect_types, min_significance
        )

        return jsonify({
            'chart': chart_key,
            'start_date': start_date,
            'end_date': end_date,
            'total_found': len(upcoming),
            'transits': upcoming
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/compare', methods=['GET'])
def compare_charts():
    """
    Compare transits across multiple charts for a given date and time

    Query params:
        date: Date in YYYY-MM-DD format (default: today)
        time: Time in HH:MM format (default: 12:00)
        timezone: Timezone string (default: America/Los_Angeles)
        charts: Comma-separated list of chart keys (default: all three)
    """
    try:
        date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        time_str = request.args.get('time', '12:00')
        timezone = request.args.get('timezone', 'America/Los_Angeles')
        charts_str = request.args.get('charts', 'christina,julian,superlunar,davison')
        chart_keys = charts_str.split(',')

        results = {}
        for chart_key in chart_keys:
            chart_key = chart_key.strip()
            dashboard = tc.get_daily_dashboard(chart_key, date_str, max_orb=3, time_str=time_str, timezone=timezone)

            # Summarize
            critical = sum(1 for a in dashboard['aspects'] if a['significance'] == 'CRITICAL')
            high = sum(1 for a in dashboard['aspects'] if a['significance'] == 'HIGH')
            challenging = sum(1 for a in dashboard['aspects'] if a['is_challenging'])
            supportive = sum(1 for a in dashboard['aspects'] if not a['is_challenging'])

            results[chart_key] = {
                'name': tc.ncm.get_chart(chart_key)['name'],
                'total_aspects': dashboard['total_aspects'],
                'critical': critical,
                'high': high,
                'challenging': challenging,
                'supportive': supportive,
                'top_aspects': dashboard['aspects']  # All aspects within 3° orb
            }

        return jsonify({
            'date': date_str,
            'time': time_str,
            'charts': results
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/date-range/<chart_key>', methods=['GET'])
def get_date_range_summary(chart_key):
    """
    Get summary of transits over a date range

    Query params:
        start_date: Start date (default: today)
        end_date: End date (default: 30 days from start)
    """
    try:
        start_date = request.args.get('start_date', datetime.now().strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date')

        # Default end date to 30 days from start
        if not end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = start + timedelta(days=30)
            end_date = end.strftime('%Y-%m-%d')

        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end - start).days

        daily_summaries = []

        for day_offset in range(days + 1):
            current_date = start + timedelta(days=day_offset)
            date_str = current_date.strftime('%Y-%m-%d')

            dashboard = tc.get_daily_dashboard(chart_key, date_str, max_orb=3)

            # Calculate summary metrics
            critical = sum(1 for a in dashboard['aspects'] if a['significance'] == 'CRITICAL')
            high = sum(1 for a in dashboard['aspects'] if a['significance'] == 'HIGH')
            challenging = sum(1 for a in dashboard['aspects'] if a['is_challenging'])
            avg_strength = sum(a['strength'] for a in dashboard['aspects']) / len(dashboard['aspects']) if dashboard['aspects'] else 0

            daily_summaries.append({
                'date': date_str,
                'total_aspects': dashboard['total_aspects'],
                'critical': critical,
                'high': high,
                'challenging': challenging,
                'avg_strength': round(avg_strength, 1)
            })

        return jsonify({
            'chart': chart_key,
            'start_date': start_date,
            'end_date': end_date,
            'daily_summaries': daily_summaries
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("="*80)
    print("TRANSIT TRACKER API")
    print("="*80)
    print("\nInitializing natal charts...")

    # Test that everything is working
    try:
        dashboard = tc.get_daily_dashboard('julian', datetime.now().strftime('%Y-%m-%d'))
        print(f"✓ Successfully calculated {dashboard['total_aspects']} aspects for Julian")
    except Exception as e:
        print(f"✗ Error during initialization: {e}")
        traceback.print_exc()

    print("\nStarting Flask server...")
    print("API will be available at http://localhost:5000")
    print("\nAvailable endpoints:")
    print("  GET /api/health")
    print("  GET /api/charts")
    print("  GET /api/chart/<chart_key>")
    print("  GET /api/dashboard/<chart_key>?date=YYYY-MM-DD")
    print("  GET /api/timeline/<chart_key>/<transit_planet>/<natal_point>/<aspect_name>")
    print("  GET /api/scan/<chart_key>?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD")
    print("  GET /api/compare?date=YYYY-MM-DD&charts=christina,julian,superlunar,davison")
    print("  GET /api/date-range/<chart_key>?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD")
    print("="*80)

    app.run(debug=True, host='0.0.0.0', port=5000)
