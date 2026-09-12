import os
import re
import math
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import urllib.request

from flask import Flask, jsonify, request, send_from_directory
import icalendar
from dateutil import parser as date_parser

app = Flask(__name__, static_folder=".", static_url_path="")

# On PythonAnywhere's free tier, direct outbound requests to icloud.com are blocked
# by their proxy whitelist, so we relay through a GitHub Actions job that syncs the
# feed into flight_calendar.ics on this repo and we read it via raw.githubusercontent.com.
DEFAULT_ICAL_URL = os.environ.get(
    "ICAL_URL",
    "https://raw.githubusercontent.com/Sean-Wiki-Williams/PilotScheduler/main/flight_calendar.ics",
)

AIRPORT_DB: Dict[str, Dict[str, Any]] = {
    "ATL": {"name": "Hartsfield–Jackson Atlanta International Airport", "city": "Atlanta, GA", "lat": 33.6407, "lon": -84.4277},
    "SAP": {"name": "Ramón Villeda Morales International Airport", "city": "San Pedro Sula, Honduras", "lat": 15.4528, "lon": -87.9238},
    "MCI": {"name": "Kansas City International Airport", "city": "Kansas City, MO", "lat": 39.2976, "lon": -94.7139},
    "SMF": {"name": "Sacramento International Airport", "city": "Sacramento, CA", "lat": 38.6954, "lon": -121.5908},
    "BNA": {"name": "Nashville International Airport", "city": "Nashville, TN", "lat": 36.1245, "lon": -86.6782},
    "LAX": {"name": "Los Angeles International Airport", "city": "Los Angeles, CA", "lat": 33.9416, "lon": -118.4085},
    "SEA": {"name": "Seattle-Tacoma International Airport", "city": "Seattle, WA", "lat": 47.4502, "lon": -122.3088},
    "MEX": {"name": "Mexico City International Airport", "city": "Mexico City, Mexico", "lat": 19.4361, "lon": -99.0719},
    "RSW": {"name": "Southwest Florida International Airport", "city": "Fort Myers, FL", "lat": 26.5362, "lon": -81.7552},
    "COS": {"name": "Colorado Springs Airport", "city": "Colorado Springs, CO", "lat": 38.8058, "lon": -104.7008},
    "JFK": {"name": "John F. Kennedy International Airport", "city": "New York, NY", "lat": 40.6413, "lon": -73.7781},
    "LGA": {"name": "LaGuardia Airport", "city": "New York, NY", "lat": 40.7769, "lon": -73.8740},
    "EWR": {"name": "Newark Liberty International Airport", "city": "Newark, NJ", "lat": 40.6895, "lon": -74.1745},
    "ORD": {"name": "O'Hare International Airport", "city": "Chicago, IL", "lat": 41.9742, "lon": -87.9073},
    "MDW": {"name": "Chicago Midway International Airport", "city": "Chicago, IL", "lat": 41.7868, "lon": -87.7522},
    "DFW": {"name": "Dallas/Fort Worth International Airport", "city": "Dallas, TX", "lat": 32.8998, "lon": -97.0403},
    "DEN": {"name": "Denver International Airport", "city": "Denver, CO", "lat": 39.8561, "lon": -104.6737},
    "SFO": {"name": "San Francisco International Airport", "city": "San Francisco, CA", "lat": 37.6213, "lon": -122.3790},
    "BOS": {"name": "Boston Logan International Airport", "city": "Boston, MA", "lat": 42.3656, "lon": -71.0096},
    "MIA": {"name": "Miami International Airport", "city": "Miami, FL", "lat": 25.7959, "lon": -80.2870},
    "MCO": {"name": "Orlando International Airport", "city": "Orlando, FL", "lat": 28.4312, "lon": -81.3081},
    "LAS": {"name": "Harry Reid International Airport", "city": "Las Vegas, NV", "lat": 36.0840, "lon": -115.1537},
    "PHX": {"name": "Phoenix Sky Harbor International Airport", "city": "Phoenix, AZ", "lat": 33.4373, "lon": -112.0078},
    "IAH": {"name": "George Bush Intercontinental Airport", "city": "Houston, TX", "lat": 29.9902, "lon": -95.3368},
    "CLT": {"name": "Charlotte Douglas International Airport", "city": "Charlotte, NC", "lat": 35.2144, "lon": -80.9473},
    "DTW": {"name": "Detroit Metropolitan Wayne County Airport", "city": "Detroit, MI", "lat": 42.2162, "lon": -83.3554},
    "MSP": {"name": "Minneapolis-Saint Paul International Airport", "city": "Minneapolis, MN", "lat": 44.8848, "lon": -93.2223},
    "SLC": {"name": "Salt Lake City International Airport", "city": "Salt Lake City, UT", "lat": 40.7899, "lon": -111.9791},
    "SAN": {"name": "San Diego International Airport", "city": "San Diego, CA", "lat": 32.7338, "lon": -117.1933},
    "TPA": {"name": "Tampa International Airport", "city": "Tampa, FL", "lat": 27.9772, "lon": -82.5311},
    "PDX": {"name": "Portland International Airport", "city": "Portland, OR", "lat": 45.5898, "lon": -122.5951},
    "STL": {"name": "St. Louis Lambert International Airport", "city": "St. Louis, MO", "lat": 38.7472, "lon": -90.3599},
    "CVG": {"name": "Cincinnati/Northern Kentucky International Airport", "city": "Cincinnati, OH", "lat": 29.0488, "lon": -84.6678},
    "RDU": {"name": "Raleigh-Durham International Airport", "city": "Raleigh, NC", "lat": 35.8801, "lon": -78.7880},
    "AUS": {"name": "Austin-Bergstrom International Airport", "city": "Austin, TX", "lat": 30.1975, "lon": -97.6664},
    "IND": {"name": "Indianapolis International Airport", "city": "Indianapolis, IN", "lat": 39.7173, "lon": -86.2944},
    "CMH": {"name": "John Glenn Columbus International Airport", "city": "Columbus, OH", "lat": 39.9980, "lon": -82.8919},
    "PIT": {"name": "Pittsburgh International Airport", "city": "Pittsburgh, PA", "lat": 40.4915, "lon": -80.2329},
    "JAX": {"name": "Jacksonville International Airport", "city": "Jacksonville, FL", "lat": 30.4941, "lon": -81.6879},
    "MSY": {"name": "Louis Armstrong New Orleans International Airport", "city": "New Orleans, LA", "lat": 29.9911, "lon": -90.2580},
    "SAT": {"name": "San Antonio International Airport", "city": "San Antonio, TX", "lat": 29.5337, "lon": -98.4698},
    "DAL": {"name": "Dallas Love Field", "city": "Dallas, TX", "lat": 32.8481, "lon": -96.8512},
    "HOU": {"name": "William P. Hobby Airport", "city": "Houston, TX", "lat": 29.6454, "lon": -95.2789},
}

AIRCRAFT_MODELS: Dict[str, str] = {
    "739": "Boeing 737-900ER",
    "73N": "Boeing 737-900ER",
    "73J": "Boeing 737-900",
    "73R": "Boeing 737-800",
    "738": "Boeing 737-800",
    "73H": "Boeing 737-800",
    "757": "Boeing 757-200",
    "752": "Boeing 757-200",
    "753": "Boeing 757-300",
    "767": "Boeing 767-300ER",
    "763": "Boeing 767-300ER",
    "764": "Boeing 767-400ER",
    "321": "Airbus A321-200",
    "32B": "Airbus A321neo",
    "32Q": "Airbus A321neo",
    "320": "Airbus A320-200",
    "319": "Airbus A319",
    "221": "Airbus A220-100",
    "223": "Airbus A220-300",
    "332": "Airbus A330-200",
    "333": "Airbus A330-300",
    "339": "Airbus A330-900neo",
    "359": "Airbus A350-900",
}

# Cache for iCal data to avoid rate limits
_cache: Dict[str, Any] = {"data": None, "timestamp": 0}
CACHE_TTL_SECONDS = 60

MONTH_ABBR: Dict[str, int] = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

RPT_RE = re.compile(r"Rpt-\s*\d{4}\s+(\d{1,2})([A-Z]{3})")
LEG_RE = re.compile(r"^(?:([ID])\s+)?([A-Z]{2}\d{2,4})\s+([A-Z]{3})-([A-Z]{3})\s+(\d{1,2}:\d{2})-(\d{1,2}:\d{2})\s+(\S+)$")
LAYOVER_RE = re.compile(r"^LAYOVER\s+[\d:]+/([A-Z]{3})$")
HOTEL_RE = re.compile(r"^([^:]+):\s*([\d\-\+\(\)\s]+)$")


def parse_rotation_legs(description: str, event_start: Optional[datetime], event_end: Optional[datetime]) -> List[Dict[str, Any]]:
    """Extract individual flight legs from a multi-day rotation report DESCRIPTION block.

    Real MyCrew/PilotScheduler exports bundle several days of flight legs (each preceded
    by a "Rpt- HHMM DDMMM" report-time marker) inside a single VEVENT's description,
    rather than one VEVENT per flight leg.
    """
    legs: List[Dict[str, Any]] = []
    if not description or not event_start:
        return legs

    tzinfo = event_start.tzinfo or timezone.utc
    lines = [ln.strip() for ln in description.splitlines() if ln.strip()]

    current_date = event_start.date()
    last_dest_code: Optional[str] = None
    pending_layover: Optional[Dict[str, Any]] = None

    for line in lines:
        m_rpt = RPT_RE.search(line)
        if m_rpt:
            day = int(m_rpt.group(1))
            month = MONTH_ABBR.get(m_rpt.group(2), event_start.month)
            year = event_start.year
            try:
                candidate = datetime(year, month, day, tzinfo=tzinfo).date()
            except ValueError:
                candidate = event_start.date()
            # Adjust for rotations that span a New Year's boundary
            if event_end and (candidate - event_start.date()).days < -180:
                candidate = candidate.replace(year=year + 1)
            elif event_end and (candidate - event_end.date()).days > 180:
                candidate = candidate.replace(year=year - 1)
            current_date = candidate
            continue

        m_leg = LEG_RE.match(line)
        if m_leg:
            prefix, flight_num, origin_code, dest_code, dep_time, arr_time, eqp_code = m_leg.groups()
            dep_h, dep_m = (int(x) for x in dep_time.split(":"))
            arr_h, arr_m = (int(x) for x in arr_time.split(":"))
            start_dt = datetime(current_date.year, current_date.month, current_date.day, dep_h, dep_m, tzinfo=tzinfo)
            end_dt = datetime(current_date.year, current_date.month, current_date.day, arr_h, arr_m, tzinfo=tzinfo)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)

            legs.append({
                "flight": flight_num,
                "prefix": prefix or "D",
                "origin_code": origin_code,
                "dest_code": dest_code,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "equipment": eqp_code,
                "layover": None,
            })
            last_dest_code = dest_code
            pending_layover = None
            continue

        m_lay = LAYOVER_RE.match(line)
        if m_lay and legs:
            pending_layover = {"city": get_airport_info(last_dest_code)["city"] if last_dest_code else ""}
            continue

        if pending_layover is not None:
            m_hotel = HOTEL_RE.match(line)
            if m_hotel:
                pending_layover["hotel_name"] = m_hotel.group(1).strip()
                pending_layover["hotel_phone"] = m_hotel.group(2).strip()
                legs[-1]["layover"] = pending_layover
                pending_layover = None
            continue

    return legs


def build_flight_entry(
    flight_num: str,
    prefix: str,
    origin_code: str,
    dest_code: str,
    start_dt: datetime,
    end_dt: datetime,
    eqp_code: str,
    now: datetime,
    ship_code: str = "",
    dep_gate: str = "—",
    arr_gate: str = "—",
    duration: str = "—",
    layover: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    origin_info = get_airport_info(origin_code)
    dest_info = get_airport_info(dest_code)
    aircraft_name = AIRCRAFT_MODELS.get(eqp_code, f"Boeing {eqp_code}")

    if now < start_dt:
        diff_hours = (start_dt - now).total_seconds() / 3600.0
        status = "Upcoming" if diff_hours > 12 else "On time"
    elif start_dt <= now <= end_dt:
        status = "In air"
    else:
        status = "Completed"

    return {
        "flight": flight_num,
        "flight_type": "International" if prefix == "I" else "Domestic",
        "origin": origin_info,
        "dest": dest_info,
        "route": f"{origin_code} → {dest_code}",
        "dep_gate": dep_gate,
        "arr_gate": arr_gate,
        "duration": duration,
        "equipment": eqp_code,
        "ship": ship_code,
        "aircraft": f"Delta {eqp_code} — {aircraft_name}",
        "tail": f"N{ship_code}DN" if ship_code else "N8XXDN",
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "date_key": start_dt.strftime("%Y-%m-%d"),
        "date_display": start_dt.strftime("%a, %b %d, %Y"),
        "dep_time_formatted": start_dt.strftime("%I:%M %p").lstrip("0"),
        "arr_time_formatted": end_dt.strftime("%I:%M %p").lstrip("0"),
        "dep_date_formatted": start_dt.strftime("%b %d"),
        "status": status,
        "layover": layover,
    }


def fetch_ical_content(url: str) -> bytes:
    if url.startswith("webcal://"):
        url = "https://" + url[9:]
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DadTravelTracker/1.0"},
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read()


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360


def get_airport_info(code: str) -> Dict[str, Any]:
    code = code.strip().upper()
    if code in AIRPORT_DB:
        return {
            "code": code,
            "name": AIRPORT_DB[code]["name"],
            "city": AIRPORT_DB[code]["city"],
            "lat": AIRPORT_DB[code]["lat"],
            "lon": AIRPORT_DB[code]["lon"],
        }
    return {
        "code": code,
        "name": f"{code} Airport",
        "city": code,
        "lat": 0.0,
        "lon": 0.0,
    }


def parse_calendar_data(raw_ical_bytes: bytes) -> Dict[str, Any]:
    cal = icalendar.Calendar.from_ical(raw_ical_bytes)
    now = datetime.now(timezone.utc)

    flights = []
    layovers = []
    rotations = []

    for component in cal.walk("VEVENT"):
        summary = str(component.get("summary", "")).strip()
        description = str(component.get("description", "")).strip()
        st = component.get("dtstart")
        et = component.get("dtend")

        start_dt: Optional[datetime] = st.dt if st else None
        end_dt: Optional[datetime] = et.dt if et else None

        # Convert date-only objects to datetime UTC
        if start_dt and not isinstance(start_dt, datetime):
            start_dt = datetime.combine(start_dt, datetime.min.time(), tzinfo=timezone.utc)
        elif start_dt and start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

        if end_dt and not isinstance(end_dt, datetime):
            end_dt = datetime.combine(end_dt, datetime.min.time(), tzinfo=timezone.utc)
        elif end_dt and end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)

        # 1. Match single-leg colon-format events: e.g. "I DL1805 : SAP - ATL"
        flight_match = re.search(
            r"(?:([IDC])\s+)?([A-Z0-9]{2}\s*\d{1,4})\s*:\s*([A-Z]{3})\s*[-–—]\s*([A-Z]{3})",
            summary,
        )
        if flight_match:
            prefix = flight_match.group(1) or ("I" if "I " in summary else "D")
            flight_num = flight_match.group(2).replace(" ", "")
            origin_code = flight_match.group(3)
            dest_code = flight_match.group(4)

            dep_gate_m = re.search(r"Dep-[^\n]*?Gate-\s*([A-Z0-9]+)", description)
            arr_gate_m = re.search(r"Arr-[^\n]*?Gate-\s*([A-Z0-9]+)", description)
            blk_m = re.search(r"Blk-\s*(\d+:\d+)", description)
            eqp_m = re.search(r"Eqp/Ship-\s*([A-Z0-9]+)(?:/([A-Z0-9]+))?", description)

            hotel_m = re.search(r"LAYOVER[^\n]*\n+([^:\n]+):\s*([0-9\-\+\(\) ]+)", description)
            layover = None
            if hotel_m:
                layover = {
                    "city": get_airport_info(dest_code)["city"],
                    "hotel_name": hotel_m.group(1).strip(),
                    "hotel_phone": hotel_m.group(2).strip(),
                }
                layovers.append(layover)

            eqp_code = eqp_m.group(1) if eqp_m else "739"
            ship_code = eqp_m.group(2) if eqp_m else ""

            if start_dt and end_dt:
                flights.append(
                    build_flight_entry(
                        flight_num, prefix, origin_code, dest_code, start_dt, end_dt,
                        eqp_code, now, ship_code=ship_code,
                        dep_gate=dep_gate_m.group(1) if dep_gate_m else "—",
                        arr_gate=arr_gate_m.group(1) if arr_gate_m else "—",
                        duration=blk_m.group(1) if blk_m else "—",
                        layover=layover,
                    )
                )

        # 2. Extract individual legs bundled inside multi-day rotation report descriptions
        # e.g. SUMMARY "2904 BDL (0626-1706)" with "Rpt- 0626 13SEP" blocks in DESCRIPTION
        for leg in parse_rotation_legs(description, start_dt, end_dt):
            entry = build_flight_entry(
                leg["flight"], leg["prefix"], leg["origin_code"], leg["dest_code"],
                leg["start_dt"], leg["end_dt"], leg["equipment"], now,
                layover=leg["layover"],
            )
            flights.append(entry)
            if leg["layover"]:
                layovers.append(leg["layover"])

        # 3. Check Rotation Reports: e.g. "Rotation Report ATL 0227"
        if "Rotation Report" in summary or "Rpt-" in description:
            rpt_m = re.search(r"Rpt-\s*(\d{4}\s+[A-Z0-9]+)", description)
            rls_m = re.search(r"Rls-\s*(\d{4}\s+[A-Z0-9]+)", description)
            layover_text_m = re.search(r"Layover-\s*([^\n]+)", description)
            tafb_m = re.search(r"TAFB-\s*([^\n]+)", description)
            rotations.append(
                {
                    "summary": summary,
                    "start": start_dt.isoformat() if start_dt else None,
                    "end": end_dt.isoformat() if end_dt else None,
                    "rpt": rpt_m.group(1) if rpt_m else None,
                    "rls": rls_m.group(1) if rls_m else None,
                    "layovers": layover_text_m.group(1).strip() if layover_text_m else None,
                    "tafb": tafb_m.group(1).strip() if tafb_m else None,
                }
            )

    # Sort flights chronologically
    flights.sort(key=lambda f: f["start"] or "")

    # Drop flights that fully completed before today (keep in-progress/future ones)
    today_key = now.strftime("%Y-%m-%d")

    def _still_relevant(f: Dict[str, Any]) -> bool:
        if f.get("end"):
            if datetime.fromisoformat(f["end"]) >= now:
                return True
        if f.get("date_key") and f["date_key"] >= today_key:
            return True
        return False

    flights = [f for f in flights if _still_relevant(f)]

    # Identify active/featured flight
    featured_flight = None
    if flights:
        # Prefer in-air flight, then next upcoming flight, or default to the most recent flight
        in_air = [f for f in flights if f["status"] == "In air"]
        upcoming = [f for f in flights if f["status"] in ("On time", "Upcoming")]
        if in_air:
            featured_flight = in_air[0]
        elif upcoming:
            featured_flight = upcoming[0]
        else:
            featured_flight = flights[-1]

    # Calculate flight progress and coordinates for featured flight
    progress_pct = 62  # Default illustration percentage
    plane_pos = None
    bearing = 0.0

    if featured_flight:
        origin_lat = featured_flight["origin"]["lat"]
        origin_lon = featured_flight["origin"]["lon"]
        dest_lat = featured_flight["dest"]["lat"]
        dest_lon = featured_flight["dest"]["lon"]

        bearing = calculate_bearing(origin_lat, origin_lon, dest_lat, dest_lon)

        if featured_flight["start"] and featured_flight["end"]:
            st = datetime.fromisoformat(featured_flight["start"])
            et = datetime.fromisoformat(featured_flight["end"])
            total_sec = (et - st).total_seconds()
            elapsed_sec = (now - st).total_seconds()

            if total_sec > 0 and 0 <= elapsed_sec <= total_sec:
                progress_pct = max(0, min(100, int((elapsed_sec / total_sec) * 100)))
            elif now > et:
                progress_pct = 100
            else:
                progress_pct = 0

        # Interpolate position along great circle / line
        t = progress_pct / 100.0
        # If progress is 0, offset slightly along route so plane is visible near origin
        t_pos = max(0.05, min(0.95, t if 0 < t < 1 else 0.55))
        plane_lat = origin_lat + (dest_lat - origin_lat) * t_pos
        plane_lon = origin_lon + (dest_lon - origin_lon) * t_pos
        plane_pos = {"lat": round(plane_lat, 4), "lon": round(plane_lon, 4)}

    # Tonight's Stay
    tonight_stay = None
    if layovers:
        tonight_stay = layovers[-1]
    elif featured_flight and featured_flight.get("layover"):
        tonight_stay = featured_flight["layover"]
    else:
        dest_city = featured_flight["dest"]["city"] if featured_flight else "Los Angeles, CA"
        tonight_stay = {
            "city": dest_city,
            "hotel_name": "Marriott Downtown",
            "hotel_phone": "Direct Layover Hotel",
        }

    # Countdown: "leave" (no flight today, counts down to next flight) or
    # "home" (flying today, counts down to the next day off from flying)
    today_date = now.date()
    flight_dates = set()
    for f in flights:
        if f.get("date_key"):
            try:
                flight_dates.add(datetime.strptime(f["date_key"], "%Y-%m-%d").date())
            except Exception:
                pass

    has_flight_today = today_date in flight_dates
    if has_flight_today:
        countdown_mode = "home"
        countdown_days = 1
        probe = today_date + timedelta(days=1)
        for _ in range(120):
            if probe not in flight_dates:
                countdown_days = (probe - today_date).days
                break
            probe += timedelta(days=1)
    else:
        countdown_mode = "leave"
        future_flight_dates = sorted(d for d in flight_dates if d >= today_date)
        countdown_days = (future_flight_dates[0] - today_date).days if future_flight_dates else 0

    days_until_home = countdown_days  # kept for backward compatibility

    # Calculate 2-month window from today
    two_months_later = now + timedelta(days=60)
    today_date = now.date()
    two_months_date = two_months_later.date()

    for f in flights:
        if f.get("start"):
            try:
                f_date = datetime.fromisoformat(f["start"]).date()
                f["in_two_month_window"] = (today_date <= f_date <= two_months_date)
            except Exception:
                f["in_two_month_window"] = False
        else:
            f["in_two_month_window"] = False

    # Dates summary (group by date)
    dates_summary = {}
    for f in flights:
        dk = f.get("date_key")
        if not dk:
            continue
        if dk not in dates_summary:
            try:
                f_date = datetime.fromisoformat(f["start"]).date() if f.get("start") else None
                in_win = bool(f_date and (today_date <= f_date <= two_months_date))
            except Exception:
                in_win = False

            dates_summary[dk] = {
                "date_key": dk,
                "date_display": f.get("date_display"),
                "flight_count": 0,
                "routes": [],
                "in_two_month_window": in_win,
            }
        dates_summary[dk]["flight_count"] += 1
        dates_summary[dk]["routes"].append(f["route"])

    all_available_dates = list(dates_summary.values())
    all_available_dates.sort(key=lambda x: x["date_key"])
    
    # Filter for next 2 months dates
    upcoming_dates = [d for d in all_available_dates if d["in_two_month_window"]]

    # Upcoming flights in the next 2-month window
    upcoming_flights = [f for f in flights if f.get("in_two_month_window")]

    return {
        "success": True,
        "today_date_key": now.strftime("%Y-%m-%d"),
        "today_date_display": now.strftime("%a, %b %d, %Y"),
        "window_start": now.strftime("%Y-%m-%d"),
        "window_end": two_months_later.strftime("%Y-%m-%d"),
        "window_display": f"{now.strftime('%b %d, %Y')} – {two_months_later.strftime('%b %d, %Y')}",
        "available_dates": all_available_dates,
        "upcoming_dates": upcoming_dates,
        "upcoming_flights": upcoming_flights,
        "flights": flights,
        "featured_flight": featured_flight,
        "plane_position": plane_pos,
        "bearing": round(bearing, 1),
        "progress_percentage": progress_pct,
        "tonight_stay": tonight_stay,
        "rotations": rotations,
        "days_until_home": days_until_home,
        "countdown_mode": countdown_mode,
        "countdown_days": countdown_days,
        "has_flight_today": has_flight_today,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


@app.route("/api/flights")
@app.route("/api/data")
def get_flights_api():
    force_refresh = request.args.get("force", "0") in ("1", "true")
    now_ts = time.time()

    if not force_refresh and _cache["data"] and (now_ts - _cache["timestamp"] < CACHE_TTL_SECONDS):
        return jsonify(_cache["data"])

    try:
        raw_content = fetch_ical_content(DEFAULT_ICAL_URL)
        data = parse_calendar_data(raw_content)
        _cache["data"] = data
        _cache["timestamp"] = now_ts
        return jsonify(data)
    except Exception as e:
        app.logger.exception("Failed to fetch/parse flight calendar data")
        if _cache["data"]:
            return jsonify(_cache["data"])
        return jsonify({"success": False, "error": f"{type(e).__name__}: {e}"}), 500


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(".", filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

