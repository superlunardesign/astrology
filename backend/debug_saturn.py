"""
Debug Saturn transit calculations
"""
from transit_calculator import TransitCalculator
from datetime import date, timedelta

tc = TransitCalculator()

# Get Julian's chart
julian_chart = tc.ncm.get_chart('julian')

print("="*80)
print("JULIAN'S NATAL POSITIONS")
print("="*80)
print(f"North Node: {julian_chart['positions']['North Node']['longitude']:.2f}°")
print(f"South Node: {julian_chart['positions']['South Node']['longitude']:.2f}°")
print(f"Saturn: {julian_chart['positions']['Saturn']['longitude']:.2f}°")

# Get current transiting positions
today = date.today().strftime('%Y-%m-%d')
transit_pos = tc.get_transiting_positions(today)

print("\n" + "="*80)
print(f"TRANSITING POSITIONS ({today})")
print("="*80)
print(f"Saturn: {transit_pos['Saturn']['longitude']:.2f}° (speed: {transit_pos['Saturn']['speed']:.5f}°/day)")
print(f"North Node: {transit_pos['North Node']['longitude']:.2f}° (speed: {transit_pos['North Node']['speed']:.5f}°/day)")

# Calculate the angle between transiting Saturn and natal North Node
natal_nn_long = julian_chart['positions']['North Node']['longitude']
transit_saturn_long = transit_pos['Saturn']['longitude']

print("\n" + "="*80)
print("ASPECT CALCULATION")
print("="*80)
print(f"Transiting Saturn: {transit_saturn_long:.2f}°")
print(f"Natal North Node: {natal_nn_long:.2f}°")

# Calculate difference
diff = abs(transit_saturn_long - natal_nn_long)
if diff > 180:
    diff = 360 - diff

print(f"Angle between them: {diff:.2f}°")

# Check for square (90°)
square_orb = abs(diff - 90)
print(f"Orb to square (90°): {square_orb:.2f}°")

# Check for opposition (180°)
opp_orb = abs(diff - 180)
print(f"Orb to opposition (180°): {opp_orb:.2f}°")

# Check for conjunction (0°)
conj_orb = min(diff, 360 - diff)
print(f"Orb to conjunction (0°): {conj_orb:.2f}°")

# Check a few dates around now
print("\n" + "="*80)
print("SATURN POSITION OVER TIME")
print("="*80)

for days_offset in [-30, -15, 0, 15, 30, 45, 60, 75]:
    check_date = date.today() + timedelta(days=days_offset)
    date_str = check_date.strftime('%Y-%m-%d')

    jd = tc.em.get_julian_day(date_str, '12:00', 'UTC')
    saturn_pos = tc.em.get_planet_position('Saturn', jd)

    diff = abs(saturn_pos['longitude'] - natal_nn_long)
    if diff > 180:
        diff = 360 - diff

    square_orb = abs(diff - 90)

    print(f"{date_str}: Saturn @ {saturn_pos['longitude']:>6.2f}° | "
          f"Angle to NN: {diff:>6.2f}° | Square orb: {square_orb:>5.2f}°")
