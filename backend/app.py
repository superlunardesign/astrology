"""
Flask API for Transit Tracker
"""
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from transit_calculator import TransitCalculator
from collections import OrderedDict
from datetime import datetime, timedelta
import traceback
import os
import threading
import uuid
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

app = Flask(__name__)
CORS(app)

# Initialize transit calculator
tc = TransitCalculator()

# Background job storage
export_jobs = {}  # job_id -> {status, progress, result, error, created_at}

# Email configuration (set via environment variables on Render)
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
DEFAULT_EMAIL_TO = os.environ.get('DEFAULT_EMAIL_TO', 'christinasuze@gmail.com')


def send_export_email(to_email, subject, body, attachment_text, attachment_filename):
    """Send email with text file attachment"""
    if not SMTP_USER or not SMTP_PASSWORD:
        print("Email not configured - SMTP_USER and SMTP_PASSWORD environment variables required")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        # Attach the text file
        attachment = MIMEApplication(attachment_text.encode('utf-8'), Name=attachment_filename)
        attachment['Content-Disposition'] = f'attachment; filename="{attachment_filename}"'
        msg.attach(attachment)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        print(f"Email sent successfully to {to_email}")
        return True

    except Exception as e:
        print(f"Failed to send email: {e}")
        traceback.print_exc()
        return False


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
                'motion': '(Rx) RETROGRADE' if aspect['is_retrograde'] else 'DIRECT',
                'exactness': aspect['exact_summary']
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

        upcoming = tc.scan_future_transits(
            chart_key, start_date, end_date,
            transit_planets, aspect_types
        )

        return jsonify({
            'chart': chart_key,
            'chart_name': tc.ncm.get_chart(chart_key)['name'],
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
        charts_str = request.args.get('charts', 'christina,julian,davison')
        chart_keys = charts_str.split(',')

        # Get current planetary positions (same for all charts)
        transit_positions = tc.get_transiting_positions(date_str, time_str, timezone)
        planet_positions = {}
        planet_order = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter',
                        'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron',
                        'North Node', 'South Node']

        for planet_name in planet_order:
            if planet_name in transit_positions:
                pos = transit_positions[planet_name]
                longitude = pos['longitude']
                sign = tc.get_sign_from_longitude(longitude)
                degree = int(longitude % 30)
                planet_positions[planet_name] = {
                    'longitude': longitude,
                    'sign': sign,
                    'degree': degree
                }

        results = {}
        for chart_key in chart_keys:
            chart_key = chart_key.strip()
            dashboard = tc.get_daily_dashboard(chart_key, date_str, max_orb=3, time_str=time_str, timezone=timezone)

            # Summarize
            # Get Moon info for this chart
            moon_info = tc._get_moon_daily_info(chart_key, date_str, timezone)

            # Get natal positions for this chart
            chart = tc.ncm.get_chart(chart_key)
            natal_positions = {}
            natal_order = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter',
                          'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron',
                          'North Node', 'South Node', 'Ascendant', 'Midheaven']
            for point in natal_order:
                if point in chart['positions']:
                    longitude = chart['positions'][point]['longitude']
                    sign = tc.get_sign_from_longitude(longitude)
                    degree = int(longitude % 30)
                    natal_positions[point] = {
                        'longitude': longitude,
                        'sign': sign,
                        'degree': degree
                    }

            results[chart_key] = {
                'name': tc.ncm.get_chart(chart_key)['name'],
                'total_aspects': dashboard['total_aspects'],
                'top_aspects': dashboard['aspects'],  # All aspects within 3° orb
                'moon_info': moon_info,
                'natal_positions': natal_positions
            }

        return jsonify({
            'date': date_str,
            'time': time_str,
            'planet_positions': planet_positions,
            'charts': results
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# Journals are the heaviest thing the app builds, and the same one gets asked
# for repeatedly (a re-click, or each chart of a comparison). Keeping the last
# few in memory turns those into instant responses.
JOURNAL_CACHE_LIMIT = 24
_journal_cache = OrderedDict()


def build_journal(chart_key, start_date, days, timezone):
    """Journal for one chart, reusing a recent identical one if we have it"""
    cache_key = (chart_key, start_date, days, timezone)

    cached = _journal_cache.get(cache_key)
    if cached is not None:
        _journal_cache.move_to_end(cache_key)
        return cached

    journal = tc.generate_transit_journal(chart_key, start_date, days, timezone)

    _journal_cache[cache_key] = journal
    while len(_journal_cache) > JOURNAL_CACHE_LIMIT:
        _journal_cache.popitem(last=False)

    return journal


@app.route('/api/journal/<chart_key>', methods=['GET'])
def get_transit_journal(chart_key):
    """
    Get transit journal for a chart over a date range

    Query params:
        start_date: Start date (default: today)
        days: Number of days to include (default: 7, max: 30)
        timezone: Timezone string (default: America/Los_Angeles)
    """
    try:
        start_date = request.args.get('start_date', datetime.now().strftime('%Y-%m-%d'))
        days = int(request.args.get('days', 7))
        timezone = request.args.get('timezone', 'America/Los_Angeles')

        # Cap days at 30
        days = min(max(days, 1), 30)

        # Validate date
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        journal = build_journal(chart_key, start_date, days, timezone)

        return jsonify(journal)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/journal-compare', methods=['GET'])
def get_journal_compare():
    """
    Get combined transit journals for multiple charts

    Query params:
        start_date: Start date (default: today)
        days: Number of days (default: 7, max: 30)
        charts: Comma-separated chart keys (default: christina,julian,davison)
        timezone: Timezone string (default: America/Los_Angeles)
    """
    try:
        start_date = request.args.get('start_date', datetime.now().strftime('%Y-%m-%d'))
        days = int(request.args.get('days', 7))
        charts_str = request.args.get('charts', 'christina,julian,davison')
        timezone = request.args.get('timezone', 'America/Los_Angeles')

        chart_keys = [k.strip() for k in charts_str.split(',')]
        days = min(max(days, 1), 30)

        # Validate date
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        journals = {}
        combined_plain_text = []

        for chart_key in chart_keys:
            journal = build_journal(chart_key, start_date, days, timezone)
            journals[chart_key] = journal
            combined_plain_text.append(journal['plain_text'])
            combined_plain_text.append("\n" + "=" * 60 + "\n")

        return jsonify({
            'start_date': start_date,
            'days': days,
            'charts': journals,
            'combined_plain_text': "\n".join(combined_plain_text)
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def generate_export_journal(job_id, charts, start_date, days, timezone, email_to=None):
    """Background task to generate long-term journal export"""
    try:
        export_jobs[job_id]['status'] = 'running'
        export_jobs[job_id]['progress'] = 0

        combined_text = []
        total_charts = len(charts)

        for i, chart_key in enumerate(charts):
            export_jobs[job_id]['progress'] = int((i / total_charts) * 100)
            export_jobs[job_id]['current_chart'] = chart_key

            # Generate journal in smaller chunks to avoid memory issues
            chart_text_parts = []
            chunk_size = 7  # Process 7 days at a time

            for day_offset in range(0, days, chunk_size):
                chunk_start = datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=day_offset)
                chunk_days = min(chunk_size, days - day_offset)

                journal = tc.generate_transit_journal(
                    chart_key,
                    chunk_start.strftime('%Y-%m-%d'),
                    chunk_days,
                    timezone
                )
                chart_text_parts.append(journal['plain_text'])

                # Small pause to avoid CPU spikes
                time.sleep(0.5)

            combined_text.append('\n\n'.join(chart_text_parts))
            combined_text.append('\n' + '=' * 60 + '\n')

        result_text = '\n'.join(combined_text)
        export_jobs[job_id]['status'] = 'complete'
        export_jobs[job_id]['progress'] = 100
        export_jobs[job_id]['result'] = result_text
        export_jobs[job_id]['completed_at'] = datetime.now().isoformat()

        # Send email if requested
        if email_to:
            end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=days-1)).strftime('%Y-%m-%d')
            filename = f"transit_journal_{start_date}_to_{end_date}.txt"
            subject = f"Transit Journal Export - {start_date} to {end_date}"
            body = f"""Your transit journal export is ready!

Charts: {', '.join(charts)}
Date Range: {start_date} to {end_date} ({days} days)

The journal is attached as a .txt file.
"""
            email_sent = send_export_email(email_to, subject, body, result_text, filename)
            export_jobs[job_id]['email_sent'] = email_sent
            export_jobs[job_id]['email_to'] = email_to

    except Exception as e:
        export_jobs[job_id]['status'] = 'error'
        export_jobs[job_id]['error'] = str(e)
        traceback.print_exc()


@app.route('/api/export-journal', methods=['POST'])
def start_export_journal():
    """
    Start a background job to generate a long-term transit journal export

    POST body (JSON):
        charts: List of chart keys (default: ['christina', 'julian', 'davison'])
        start_date: Start date YYYY-MM-DD (default: today)
        days: Number of days to generate (default: 30, max: 180)
        timezone: Timezone string (default: America/Los_Angeles)
        email: Email address to send result to (default: christinasuze@gmail.com)

    Returns:
        job_id: ID to check status and download result
    """
    try:
        data = request.get_json() or {}

        charts = data.get('charts', ['christina', 'julian', 'davison'])
        start_date = data.get('start_date', datetime.now().strftime('%Y-%m-%d'))
        days = int(data.get('days', 30))
        timezone = data.get('timezone', 'America/Los_Angeles')
        email_to = data.get('email', DEFAULT_EMAIL_TO)

        # Validate
        days = min(max(days, 1), 180)  # Cap at 6 months

        try:
            datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        # Create job
        job_id = str(uuid.uuid4())[:8]
        export_jobs[job_id] = {
            'status': 'queued',
            'progress': 0,
            'charts': charts,
            'start_date': start_date,
            'days': days,
            'email_to': email_to,
            'result': None,
            'error': None,
            'created_at': datetime.now().isoformat()
        }

        # Start background thread
        thread = threading.Thread(
            target=generate_export_journal,
            args=(job_id, charts, start_date, days, timezone, email_to)
        )
        thread.daemon = True
        thread.start()

        email_msg = f" Email will be sent to {email_to} when complete." if email_to else ""

        # Estimate time (roughly 1 second per day per chart, plus overhead)
        estimated_minutes = max(1, (days * len(charts)) // 60 + 1)

        return jsonify({
            'job_id': job_id,
            'status': 'queued',
            'estimated_minutes': estimated_minutes,
            'message': f'Export started for {len(charts)} charts over {days} days.{email_msg}',
            'status_url': f'/api/export-journal/{job_id}',
            'download_url': f'/api/export-journal/{job_id}?download=true',
            'keep_alive_tip': 'Check status every few minutes to prevent server sleep on free tier'
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/export-journal/<job_id>', methods=['GET'])
def get_export_status(job_id):
    """
    Check status of an export job and download when complete

    Query params:
        download: If 'true' and job is complete, returns the .txt file
    """
    if job_id not in export_jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = export_jobs[job_id]
    download = request.args.get('download', 'false').lower() == 'true'

    if download and job['status'] == 'complete':
        # Return as downloadable text file
        filename = f"transit_journal_{job['start_date']}_{job['days']}days.txt"
        return Response(
            job['result'],
            mimetype='text/plain',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    return jsonify({
        'job_id': job_id,
        'status': job['status'],
        'progress': job['progress'],
        'charts': job.get('charts'),
        'current_chart': job.get('current_chart'),
        'start_date': job.get('start_date'),
        'days': job.get('days'),
        'error': job.get('error'),
        'created_at': job.get('created_at'),
        'completed_at': job.get('completed_at')
    })


@app.route('/api/export-jobs', methods=['GET'])
def list_export_jobs():
    """List all export jobs (for debugging)"""
    return jsonify({
        'jobs': {
            job_id: {
                'status': job['status'],
                'progress': job['progress'],
                'charts': job.get('charts'),
                'days': job.get('days'),
                'created_at': job.get('created_at')
            }
            for job_id, job in export_jobs.items()
        }
    })


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
            avg_strength = sum(a['strength'] for a in dashboard['aspects']) / len(dashboard['aspects']) if dashboard['aspects'] else 0

            daily_summaries.append({
                'date': date_str,
                'total_aspects': dashboard['total_aspects'],
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
    print("  GET /api/compare?date=YYYY-MM-DD&charts=christina,julian,davison")
    print("  GET /api/journal/<chart_key>?start_date=YYYY-MM-DD&days=7")
    print("  GET /api/journal-compare?start_date=YYYY-MM-DD&days=7&charts=christina,julian,davison")
    print("  GET /api/date-range/<chart_key>?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD")
    print("="*80)

    app.run(debug=True, host='0.0.0.0', port=5000)
