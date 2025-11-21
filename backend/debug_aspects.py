"""
Debug script to verify aspect calculations
Shows actual planetary positions and manually calculates aspects
"""
from transit_calculator import TransitCalculator
from datetime import date

tc = TransitCalculator()

# Get today's date
today = date.today().strftime('%Y-%m-%d')

print("="*80)
print(f"TRANSIT POSITIONS DEBUG - {today}")
print("="*80)

# Get Julian's natal positions
julian_chart = tc.ncm.get_chart('julian')
print("\nJULIAN'S NATAL POSITIONS:")
print("-"*80)
for planet in ['Mercury', 'Sun', 'Moon', 'Venus', 'Mars', 'North Node', 'Ascendant', 'MC']:
    if planet in julian_chart['positions']:
        long = julian_chart['positions'][planet]['longitude']
        formatted = tc.ncm.format_position(long)
        print(f"{planet:15s}: {long:7.2f}° ({formatted})")

# Get current transiting positions
transit_pos = tc.get_transiting_positions(today)
print(f"\nTRANSITING POSITIONS ({today}):")
print("-"*80)
for planet in ['Pluto', 'Saturn', 'Uranus', 'Neptune', 'Jupiter', 'Sun', 'Mercury', 'North Node']:
    long = transit_pos[planet]['longitude']
    speed = transit_pos[planet]['speed']
    formatted = tc.ncm.format_position(long)
    print(f"{planet:15s}: {long:7.2f}° ({formatted}) | Speed: {speed:+.5f}°/day")

# Manual aspect calculation for Pluto-Mercury
print("\n" + "="*80)
print("MANUAL ASPECT CALCULATION: Pluto conjunct Mercury")
print("="*80)

pluto_long = transit_pos['Pluto']['longitude']
mercury_natal = julian_chart['positions']['Mercury']['longitude']

print(f"Transiting Pluto:  {pluto_long:.4f}°")
print(f"Natal Mercury:     {mercury_natal:.4f}°")

# Calculate difference
diff = abs(pluto_long - mercury_natal)
if diff > 180:
    diff = 360 - diff

print(f"Angle between:     {diff:.4f}°")

# For conjunction (0°)
orb = abs(diff - 0)
print(f"Orb to conjunction: {orb:.4f}°")
print(f"Within 3° orb?     {'YES' if orb <= 3 else 'NO'}")

# Manual aspect calculation for Saturn-North Node square
print("\n" + "="*80)
print("MANUAL ASPECT CALCULATION: Saturn square North Node")
print("="*80)

saturn_long = transit_pos['Saturn']['longitude']
node_natal = julian_chart['positions']['North Node']['longitude']

print(f"Transiting Saturn: {saturn_long:.4f}°")
print(f"Natal North Node:  {node_natal:.4f}°")

# Calculate difference
diff = abs(saturn_long - node_natal)
if diff > 180:
    diff = 360 - diff

print(f"Angle between:     {diff:.4f}°")

# For square (90°)
orb = abs(diff - 90)
print(f"Orb to square:     {orb:.4f}°")
print(f"Within 3° orb?     {'YES' if orb <= 3 else 'NO'}")

# Show what the API reports
print("\n" + "="*80)
print("WHAT THE API CALCULATES:")
print("="*80)

aspects = tc.find_aspects('julian', today, max_orb=3)
for aspect in aspects[:15]:
    print(f"{aspect['transit_planet']:10s} {aspect['aspect_symbol']} {aspect['natal_point']:12s} | "
          f"Orb: {aspect['orb']:6.2f}° | "
          f"Transit: {aspect['transit_longitude']:7.2f}° | "
          f"Natal: {aspect['natal_longitude']:7.2f}°")
