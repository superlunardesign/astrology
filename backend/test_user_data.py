"""
Calculate transits for Julian at specific time: Nov 21, 2025 at 12:00am Pacific
"""
from ephemeris_manager import EphemerisManager
from natal_charts import NatalChartManager
from config import PLANETS

em = EphemerisManager()
ncm = NatalChartManager()

# Load Julian's chart
ncm.calculate_all_charts()
julian = ncm.get_chart('julian')

print("="*80)
print("JULIAN'S NATAL POSITIONS")
print("="*80)
print(f"Mercury:    {julian['positions']['Mercury']['longitude']:.4f}° ({ncm.format_position(julian['positions']['Mercury']['longitude'])})")
print(f"Sun:        {julian['positions']['Sun']['longitude']:.4f}° ({ncm.format_position(julian['positions']['Sun']['longitude'])})")
print(f"Mars:       {julian['positions']['Mars']['longitude']:.4f}° ({ncm.format_position(julian['positions']['Mars']['longitude'])})")
print(f"North Node: {julian['positions']['North Node']['longitude']:.4f}° ({ncm.format_position(julian['positions']['North Node']['longitude'])})")
print(f"South Node: {julian['positions']['South Node']['longitude']:.4f}° ({ncm.format_position(julian['positions']['South Node']['longitude'])})")
print(f"Ascendant:  {julian['positions']['Ascendant']['longitude']:.4f}° ({ncm.format_position(julian['positions']['Ascendant']['longitude'])})")
print(f"Descendant: {julian['positions']['Descendant']['longitude']:.4f}° ({ncm.format_position(julian['positions']['Descendant']['longitude'])})")

# Calculate for Nov 21, 2025 at 12:00am Pacific (8:00am UTC)
jd = em.get_julian_day('2025-11-21', '00:00', 'America/Los_Angeles')

print("\n" + "="*80)
print("TRANSITING POSITIONS: Nov 21, 2025 at 12:00am Pacific")
print("="*80)

planets_to_check = ['Pluto', 'Saturn', 'Moon', 'Mercury', 'Venus', 'Sun']
transit_positions = {}

for planet in planets_to_check:
    pos = em.get_planet_position(planet, jd)
    transit_positions[planet] = pos
    print(f"{planet:10s}: {pos['longitude']:7.4f}° ({ncm.format_position(pos['longitude'])}) | Speed: {pos['speed']:+.5f}°/day")

print("\n" + "="*80)
print("MANUAL ASPECT CALCULATIONS")
print("="*80)

# 1. Pluto conjunct Mercury
print("\n1. PLUTO CONJUNCT MERCURY")
pluto = transit_positions['Pluto']['longitude']
merc_natal = julian['positions']['Mercury']['longitude']
diff = abs(pluto - merc_natal)
if diff > 180:
    diff = 360 - diff
print(f"   Pluto: {pluto:.4f}° | Natal Mercury: {merc_natal:.4f}°")
print(f"   Orb: {diff:.4f}°")
print(f"   User reports: 0.05° separating")

# 2. Saturn square North Node
print("\n2. SATURN SQUARE NORTH NODE")
saturn = transit_positions['Saturn']['longitude']
nn_natal = julian['positions']['North Node']['longitude']
diff = abs(saturn - nn_natal)
if diff > 180:
    diff = 360 - diff
orb = abs(diff - 90)
print(f"   Saturn: {saturn:.4f}° | Natal Node: {nn_natal:.4f}°")
print(f"   Angle between: {diff:.4f}°")
print(f"   Orb from square (90°): {orb:.4f}°")
print(f"   User reports: 0.20° applying")

# 3. Saturn square South Node
print("\n3. SATURN SQUARE SOUTH NODE")
sn_natal = julian['positions']['South Node']['longitude']
diff = abs(saturn - sn_natal)
if diff > 180:
    diff = 360 - diff
orb = abs(diff - 90)
print(f"   Saturn: {saturn:.4f}° | Natal South Node: {sn_natal:.4f}°")
print(f"   Angle between: {diff:.4f}°")
print(f"   Orb from square (90°): {orb:.4f}°")
print(f"   User reports: 0.20° applying")

# 4. Moon trine Mars
print("\n4. MOON TRINE MARS")
moon = transit_positions['Moon']['longitude']
mars_natal = julian['positions']['Mars']['longitude']
diff = abs(moon - mars_natal)
if diff > 180:
    diff = 360 - diff
orb = abs(diff - 120)
print(f"   Moon: {moon:.4f}° | Natal Mars: {mars_natal:.4f}°")
print(f"   Angle between: {diff:.4f}°")
print(f"   Orb from trine (120°): {orb:.4f}°")
print(f"   User reports: 0.30° applying")

# 5. Mercury square Sun
print("\n5. MERCURY SQUARE SUN")
merc = transit_positions['Mercury']['longitude']
sun_natal = julian['positions']['Sun']['longitude']
diff = abs(merc - sun_natal)
if diff > 180:
    diff = 360 - diff
orb = abs(diff - 90)
print(f"   Mercury: {merc:.4f}° | Natal Sun: {sun_natal:.4f}°")
print(f"   Angle between: {diff:.4f}°")
print(f"   Orb from square (90°): {orb:.4f}°")
print(f"   User reports: 1.30° separating")

# 6. Venus conjunct Ascendant
print("\n6. VENUS CONJUNCT ASCENDANT")
venus = transit_positions['Venus']['longitude']
asc_natal = julian['positions']['Ascendant']['longitude']
diff = abs(venus - asc_natal)
if diff > 180:
    diff = 360 - diff
orb = abs(diff - 0)
print(f"   Venus: {venus:.4f}° | Natal Ascendant: {asc_natal:.4f}°")
print(f"   Angle between: {diff:.4f}°")
print(f"   Orb from conjunction (0°): {orb:.4f}°")
print(f"   User reports: 1.21° separating")

# 7. Venus opposite Descendant
print("\n7. VENUS OPPOSITE DESCENDANT")
desc_natal = julian['positions']['Descendant']['longitude']
diff = abs(venus - desc_natal)
if diff > 180:
    diff = 360 - diff
orb = abs(diff - 180)
print(f"   Venus: {venus:.4f}° | Natal Descendant: {desc_natal:.4f}°")
print(f"   Angle between: {diff:.4f}°")
print(f"   Orb from opposition (180°): {orb:.4f}°")
print(f"   User reports: 1.21° separating")

em.close_ephemeris()
