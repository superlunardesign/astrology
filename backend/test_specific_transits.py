"""
Test specific transits mentioned by the user
"""
from transit_calculator import TransitCalculator
from datetime import date, timedelta

tc = TransitCalculator()

# Today's date
today = date.today().strftime('%Y-%m-%d')

print("="*80)
print("TESTING JULIAN'S SPECIFIC TRANSITS")
print("="*80)

# Get dashboard for Julian
dashboard = tc.get_daily_dashboard('julian', today, max_orb=3)

print(f"\nDate: {today}")
print(f"Total aspects found: {dashboard['total_aspects']}")

# Find and display specific transits mentioned
print("\n" + "="*80)
print("CLOSEST TRANSITS:")
print("="*80)

for aspect in dashboard['aspects'][:8]:
    if True:
        direction = "→ APPLYING" if aspect['is_applying'] else "← SEPARATING"
        print(f"\n{aspect['transit_planet']} {aspect['aspect_symbol']} {aspect['natal_point']}")
        print(f"  Current orb: {aspect['orb']:.2f}°")
        print(f"  Direction: {direction}")
        print(f"  Strength: {aspect['strength']:.1f}%")
        # No exact date means the aspect never reaches 0°00' from here -
        # the planet stations and turns back before it can perfect
        print(f"  Exactness: {aspect['exact_summary']}")
        print(f"  Motion: {aspect['motion']}")

        # Special handling for Pluto-Mercury
        if aspect['transit_planet'] == 'Pluto' and aspect['natal_point'] == 'Mercury':
            print(f"\n  ** This is the Pluto-Mercury transit you're tracking! **")
            print(f"  Calculating complete timeline...")

            timeline = tc.calculate_aspect_timeline(
                'julian', 'Pluto', 'Mercury', aspect['aspect'], today
            )

            print(f"\n  TIMELINE:")
            print(f"    Entered 5° orb: {timeline['enter_5deg']}")
            print(f"    Entered 3° orb: {timeline['enter_3deg']}")
            print(f"    Entered 1° orb: {timeline['enter_1deg']}")
            if timeline['exact_date']:
                print(f"    EXACT: {timeline['exact_date']} (orb: {timeline['exact_orb']:.4f}°)")
            else:
                print(f"    Never exact - closest approach: {timeline['closest_approach']}")
            print(f"    Leaves 1° orb: {timeline['leave_1deg']}")
            print(f"    Leaves 3° orb: {timeline['leave_3deg']}")
            print(f"    Leaves 5° orb: {timeline['leave_5deg']}")

            if timeline['leave_3deg']:
                leave_date = date.fromisoformat(timeline['leave_3deg'])
                days_remaining = (leave_date - date.today()).days
                print(f"\n  ** {days_remaining} days until this transit leaves 3° orb **")

# Check for Saturn aspects
print("\n" + "="*80)
print("SATURN TRANSITS:")
print("="*80)

for aspect in dashboard['aspects']:
    if aspect['transit_planet'] == 'Saturn':
        direction = "→ APPLYING" if aspect['is_applying'] else "← SEPARATING"
        print(f"\n{aspect['transit_planet']} {aspect['aspect_symbol']} {aspect['natal_point']}")
        print(f"  Current orb: {aspect['orb']:.2f}°")
        print(f"  Direction: {direction}")
        print(f"  Strength: {aspect['strength']:.1f}%")
        print(f"  Exactness: {aspect['exact_summary']}")

        # Calculate timeline for Saturn-North Node
        if aspect['natal_point'] == 'North Node':
            print(f"\n  ** This is the Saturn-North Node transit you're tracking! **")
            timeline = tc.calculate_aspect_timeline(
                'julian', 'Saturn', 'North Node', aspect['aspect'], today
            )

            print(f"\n  TIMELINE:")
            print(f"    Entered 3° orb: {timeline['enter_3deg']}")
            print(f"    EXACT: {timeline['exact_date']}")
            print(f"    Leaves 3° orb: {timeline['leave_3deg']}")

            if timeline['leave_3deg']:
                leave_date = date.fromisoformat(timeline['leave_3deg'])
                days_remaining = (leave_date - date.today()).days
                print(f"\n  ** {days_remaining} days until this transit leaves 3° orb **")

# Scan for upcoming exact transits
print("\n" + "="*80)
print("UPCOMING EXACT TRANSITS (Next 120 days)")
print("="*80)

end_date = (date.today() + timedelta(days=120)).strftime('%Y-%m-%d')
upcoming = tc.scan_future_transits(
    'julian',
    today,
    end_date,
)

print(f"\nFound {len(upcoming)} upcoming transits:")
for i, transit in enumerate(upcoming[:10], 1):
    print(f"{i}. {transit['exact_date']}: {transit['transit_planet']} "
          f"{transit['aspect']} {transit['natal_point']}")

print("\n" + "="*80)
