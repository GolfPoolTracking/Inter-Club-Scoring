import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
from supabase import create_client
import urllib.parse
import base64
import random
import string
import streamlit.components.v1 as components

# --- Random code generator for unique keys ---
def generate_random_code(length=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

# --- CONFIGURATION & STYLING ---
st.set_page_config(page_title="L&B Match Centre", layout="centered", initial_sidebar_state="collapsed")

# --- CRITICAL FIX: JAVASCRIPT KEYBOARD BLOCKER & UNIVERSAL TOGGLE FIX ---
# Restored safely to components.html to prevent raw text bleeding.
components.html(
    """
    <script>
    if (window.parent && window.parent.document) {
        const doc = window.parent.document;
        
        // 1. Prevent keyboard popups on Select, Date, and Time inputs
        const observer = new MutationObserver(function(mutations) {
            const inputs = doc.querySelectorAll(
                'div[data-baseweb="select"] input, div[data-testid="stDateInput"] input, div[data-testid="stTimeInput"] input'
            );
            inputs.forEach(function(input) {
                if (input.getAttribute('inputmode') !== 'none') {
                    input.setAttribute('inputmode', 'none');
                    input.setAttribute('readonly', 'true');
                    input.style.caretColor = 'transparent';
                }
            });
        });
        observer.observe(doc.body, { childList: true, subtree: true });

        // 2. Universal Mobile Toggle Fix
        // Track the *container node* instead of the input reference — survives re-renders.
        let lastTappedContainer = null;

        doc.addEventListener('touchstart', function(e) {
            const inputContainer = e.target.closest(
                'div[data-baseweb="select"], div[data-testid="stDateInput"], div[data-testid="stTimeInput"]'
            );

            if (inputContainer) {
                // FIX 1: include data-baseweb="calendar" for the date picker popover
                const popover = doc.querySelector(
                    'div[data-baseweb="popover"], div[data-baseweb="calendar"]'
                );

                // FIX 2: compare container nodes, not input element references
                if (popover && lastTappedContainer === inputContainer) {
                    e.preventDefault();
                    e.stopPropagation();

                    const esc = new KeyboardEvent('keydown', {
                        key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true
                    });
                    doc.dispatchEvent(esc);

                    const input = inputContainer.querySelector('input');
                    if (input) input.blur();
                    lastTappedContainer = null;
                } else {
                    lastTappedContainer = inputContainer;
                }
            } else {
                // Reset unless the user is tapping *inside* an open popover/calendar
                if (!e.target.closest('div[data-baseweb="popover"], div[data-baseweb="calendar"]')) {
                    lastTappedContainer = null;
                }
            }
        }, true);
    }
    </script>
    """,
    height=0,
    width=0
)


# Inject Mobile-Optimized CSS, Meta Tags, and Noto Serif font safely
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0D4722">

<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif:wght@400;700&display=swap');

/* Base Font */
div, p, h1, h2, h3, h4, h5, h6, .stMarkdown, .stButton, .stRadio, .stCheckbox { 
    font-family: 'Noto Serif', serif !important; 
}

/* Hide Streamlit Chrome */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Mobile Optimization: Prevent accidental text highlighting when double-tapping */
body {
    -webkit-user-select: none;
    -ms-user-select: none;
    user-select: none;
}

/* Mobile Optimization: Massive Touch Targets for Dropdowns */
div[data-baseweb="select"] > div {
    min-height: 55px !important;
    font-size: 16px !important;
    border-radius: 8px !important;
}

/* Mobile Optimization: Fat-finger friendly buttons */
.stButton > button {
    min-height: 55px !important;
    font-size: 18px !important;
    font-weight: bold !important;
    border-radius: 8px !important;
}

/* Mobile Optimization: Larger Checkboxes */
div[data-testid="stCheckbox"] label span {
    font-size: 16px !important;
    padding-top: 2px !important;
}
div[data-testid="stCheckbox"] div[role="checkbox"] {
    height: 24px !important;
    width: 24px !important;
}

/* Mobile Optimization: Taller Expanders */
.streamlit-expanderHeader {
    min-height: 60px !important;
    font-size: 16px !important;
    font-weight: 700 !important;
}
</style>
""", unsafe_allow_html=True)

# L&B Palette
LB_COLOR, OPP_COLOR, TIE_COLOR = "#0D4722", "#4A5568", "#A0AEC0"
APP_BASE_URL = "https://landb-inter-club-scoring.streamlit.app"
ireland_tz = ZoneInfo("Europe/Dublin")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- HELPERS ---
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    except Exception:
        return None

def get_leader_from_score(score_string):
    if "Up" in score_string: return "L&B"
    elif "Down" in score_string: return "Opposition"
    return "Tied"

def get_comp_status(pairings):
    if not pairings: return "Not Started"
    statuses = [p['status'] for p in pairings]
    return "LIVE" if "LIVE" in statuses else ("FINISHED" if all(s == "FINISHED" for s in statuses) else "Not Started")

def calculate_overall_score(pairings):
    lb, opp = 0.0, 0.0
    for p in pairings:
        if p["status"] in ["LIVE", "FINISHED"]:
            if p["leader"] == "L&B": lb += 1.0
            elif p["leader"] == "Opposition": opp += 1.0
            else: lb += 0.5; opp += 0.5
            
    # Format scores to remove .0 for whole numbers
    lb_display = int(lb) if lb.is_integer() else lb
    opp_display = int(opp) if opp.is_integer() else opp
    
    return lb_display, opp_display

def safe_index(lst, val): return lst.index(val) if val in lst else 0

def safe_time_parse(time_str):
    if not time_str: return None
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p"):
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            pass
    return None

def format_date_display(date_string):
    if not date_string or date_string == 'TBD': 
        return 'TBD'
    try:
        # Assumes date_string is stored as YYYY-MM-DD in the database
        return datetime.strptime(date_string, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return date_string

def get_formatted_time(iso_str):
    if not iso_str: return "N/A"
    try:
        dt = pd.to_datetime(iso_str)
        # Handle older legacy timestamps missing timezone
        if dt.tzinfo is None:
            dt = dt.tz_localize('UTC')
        return dt.astimezone(ireland_tz).strftime("%H:%M")
    except:
        return "N/A"

def get_comp_updated_time(pairings):
    times = [p.get('updated_at') for p in pairings if p.get('updated_at')]
    if not times:
        return datetime.now(ireland_tz).strftime("%H:%M")
    try:
        dts = []
        for t in times:
            dt = pd.to_datetime(t)
            if dt.tzinfo is None: dt = dt.tz_localize('UTC')
            dts.append(dt)
        return max(dts).astimezone(ireland_tz).strftime("%H:%M")
    except:
        return datetime.now(ireland_tz).strftime("%H:%M")

def should_hide_names(comp):
    """Calculates if names should be hidden based on the 'always_hide' flag or the reveal window."""
    if comp.get('always_hide_names', False):
        return True, None
        
    hide_mins = comp.get('hide_mins')
    if hide_mins is None or int(hide_mins) <= 0: return False, None
    if not comp.get('match_date') or not comp.get('start_time'): return False, None
    
    try:
        dt_str = f"{comp['match_date']} {comp['start_time']}"
        dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        dt_aware = dt_obj.replace(tzinfo=ireland_tz)
        reveal_time = dt_aware - timedelta(minutes=int(hide_mins))
        now = datetime.now(ireland_tz)
        if now < reveal_time:
            return True, reveal_time
        return False, None
    except Exception:
        return False, None

def get_comp_display_name(c):
    r = f" - {c['round']}" if c.get('round') else ""
    return f"{c['category']} {c['comp_name']}{r}"

def generate_comp_id(comp):
    base = f"{comp['category']}_{comp['comp_name']}"
    if comp.get('round'):
        base += f"_{comp['round']}"
    return base.replace(" ", "_")

# --- HTML GENERATORS ---
def generate_scoreboard_html(lb_score, opp_score, opp_team_name):
    return f"<div style='display: flex; justify-content: space-between; align-items: center; width: 100%; margin-bottom: 20px; max-width: 600px; margin-left: auto; margin-right: auto;'><div style='flex: 2; text-align: center; padding: 0 5px;'><div style='font-weight: bold; margin-bottom: 5px; font-size: 15px;'>L&B</div><div style='background-color: {LB_COLOR}; color: white; padding: 15px 5px; border-radius: 8px; font-weight: bold; font-size: 28px;'>{lb_score}</div></div><div style='flex: 1; text-align: center; font-size: 35px; font-weight: bold; padding-top: 25px;'>:</div><div style='flex: 2; text-align: center; padding: 0 5px;'><div style='font-weight: bold; margin-bottom: 5px; font-size: 15px;'>{opp_team_name}</div><div style='background-color: {OPP_COLOR}; color: white; padding: 15px 5px; border-radius: 8px; font-weight: bold; font-size: 28px;'>{opp_score}</div></div></div>"

def generate_pairing_html(p, view_mode="public", hide_names=False, reveal_time=None, show_venue=False, match_index=1):
    # Only hide L&B player if the hide_names flag is true
    if hide_names:
        if reveal_time:
            lb_name_display = f"Reveals<br>{reveal_time.strftime('%H:%M')}"
        else:
            lb_name_display = f"Match {match_index}<br>(Name Hidden)"
    else:
        lb_name_display = p.get('landb_player', 'TBD')
        
    # Opposition player is never hidden per new rules
    opp_name_display = p.get('opposition_player', 'TBD')

    is_started = p['status'] in ["LIVE", "FINISHED"]
    tied_text = "A/S" if is_started else "ALL SQUARE"

    if p['leader'] == 'L&B':
        lb_score_html = f"<div style='background-color: {LB_COLOR}; color: white; text-align: center; padding: 6px; font-weight: bold; border-radius: 5px; width: 100%; box-sizing: border-box;'>{p['score']}</div>"
    elif p['leader'] == 'Tied':
        lb_score_html = f"<div style='background-color: {TIE_COLOR}; color: white; text-align: center; padding: 6px; font-weight: bold; border-radius: 5px; width: 100%; box-sizing: border-box;'>{tied_text}</div>"
    else:
        lb_score_html = f"<div style='padding: 6px; visibility: hidden; width: 100%;'>Spacer</div>"
        
    if p['leader'] == 'Opposition':
        opp_score_html = f"<div style='background-color: {OPP_COLOR}; color: white; text-align: center; padding: 6px; font-weight: bold; border-radius: 5px; width: 100%; box-sizing: border-box;'>{p['score'].replace('Down', 'Up')}</div>"
    elif p['leader'] == 'Tied':
        opp_score_html = f"<div style='background-color: {TIE_COLOR}; color: white; text-align: center; padding: 6px; font-weight: bold; border-radius: 5px; width: 100%; box-sizing: border-box;'>{tied_text}</div>"
    else:
        opp_score_html = f"<div style='padding: 6px; visibility: hidden; width: 100%;'>Spacer</div>"
        
    hole_val = str(p.get('hole', '1'))
    p_status_color = "gray" if p['status'] == "Not Started" else ("darkred" if p['status'] == "FINISHED" else "#8bc34a")
    
    should_show = (view_mode == "manager") or show_venue
    venue_html = f"<div style='font-size: 12px; opacity: 0.6; margin-top: 6px;'>📍 {p.get('venue', 'Unknown')}</div>" if should_show else ""
    
    # Conditionally display the hole and THRU text only if the match has started
    if p.get('status', '').strip().lower() != "not started":
        hole_html = f"<div style='font-size: 10px; opacity: 0.6; font-weight: bold; text-transform: uppercase; line-height: 1; margin-bottom: 4px;'>Thru</div><div style='background-color: black; color: white; padding: 6px; font-size: 14px; font-weight: bold; border-radius: 4px; line-height: 1;'>{hole_val}</div>"
    else:
        hole_html = f"<div style='padding: 6px; visibility: hidden;'>Spacer</div>"

    # Match Level Updated Time
    match_updated = get_formatted_time(p.get('updated_at'))
    updated_html = f"<div style='font-size: 10px; opacity: 0.6; margin-top: 5px; font-weight: normal;'>Updated {match_updated}</div>" if match_updated != "N/A" else ""
        
    # DECOUPLED ALIGNMENT: 
    # Top row perfectly aligns the Score and Hole boxes to the bottom edge.
    # Bottom row perfectly aligns the Names and Status to the top edge.
    top_row = f"""
    <div style='display: flex; justify-content: space-between; align-items: flex-end; width: 100%;'>
        <div style='flex: 1; text-align: center; padding: 0 4px;'>{lb_score_html}</div>
        <div style='flex: 1; text-align: center; padding: 0 4px;'>{hole_html}</div>
        <div style='flex: 1; text-align: center; padding: 0 4px;'>{opp_score_html}</div>
    </div>
    """
    
    bottom_row = f"""
    <div style='display: flex; justify-content: space-between; align-items: flex-start; width: 100%; margin-top: 8px; margin-bottom: 15px;'>
        <div style='flex: 1; text-align: center; padding: 0 4px;'>
            <div style='font-weight: bold; font-size: 15px; line-height: 1.2;'>{lb_name_display}</div>
            {venue_html}
        </div>
        <div style='flex: 1; text-align: center; padding: 0 4px;'>
            <div style='background-color: {p_status_color}; color: white; padding: 4px; font-size: 12px; font-weight: bold; border-radius: 4px;'>{p['status']}</div>
            {updated_html}
        </div>
        <div style='flex: 1; text-align: center; padding: 0 4px;'>
            <div style='font-weight: bold; font-size: 15px; line-height: 1.2;'>{opp_name_display}</div>
        </div>
    </div>
    """
    
    return top_row + bottom_row

# --- LIST DEFINITIONS ---
HOLE_OPTIONS = [str(i) for i in range(1, 19)] + [f"Extra Hole {i}" for i in range(1, 10)]
SCORE_OPTIONS = [f"{i} Up" for i in range(10, 0, -1)] + ["All Square"] + [f"{i} Down" for i in range(1, 11)]
VENUE_OPTIONS = ["Home", "Away"]
CATEGORY_OPTIONS = ["Mens", "Womens", "Boys", "Girls", "Mixed"]
ROUND_OPTIONS = ["Round 1", "Round 2", "Round 3", "Round 4", "Quarter-Final", "Semi-Final", "Final"]

# --- DATA FETCHING ---
@st.cache_data(ttl=10)
def fetch_all():
    try:
        comps = supabase.table("competitions").select("*").execute().data
        pairings = supabase.table("pairings").select("*").execute().data
        try:
            masters = supabase.table("competitions_master").select("*").execute().data
        except Exception:
            masters = []
        return comps, pairings, masters
    except:
        return [], [], []

comps, pairings, masters = fetch_all()

# Get unique years from the 'year' column for filtering
all_years = sorted(list(set([c.get('year', datetime.now(ireland_tz).year) for c in comps if c.get('year')])), reverse=True)
if not all_years: 
    all_years = [datetime.now(ireland_tz).year]

# --- SECURE URL ROUTING ---
query_params = st.query_params
role = query_params.get("role", "public")

# --- VIEW 1: PUBLIC SCOREBOARD ---
if role == "public":
    logo_base64 = get_base64_image("app/static/lb_logo.png") or get_base64_image("static/lb_logo.png")
    # Added white background & rounded corners to perfectly support iOS Dark Mode
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" width="120" style="background-color: white; border-radius: 12px; padding: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 10px; margin-top: 15px;"/>' if logo_base64 else ""

    st.markdown(f"<div style='text-align: center;'>{logo_html}<h2 style='font-weight: 700; margin-top: 0px;'>L&B Match Centre</h2></div>", unsafe_allow_html=True)
    st.divider()
    
    active_comps = [c for c in comps if not c.get('archived', False)]
    
    if active_comps:
        st.write("") # Mobile spacing
        
        # 1. State Persistence via URL query parameters
        q_cat = st.query_params.get("cat", "All")
        cat_opts = ["All"] + CATEGORY_OPTIONS
        try:
            cat_idx = cat_opts.index(q_cat)
        except ValueError:
            cat_idx = 0

        # Note: Year removed from public view per request. Using current year as default constraint.
        current_year = datetime.now(ireland_tz).year
        filter_cat = st.radio("Category", cat_opts, index=cat_idx, horizontal=True, label_visibility="collapsed")
        if filter_cat != q_cat:
            st.query_params["cat"] = filter_cat
            
        filtered_comps = [
            c for c in active_comps 
            if c.get('year') == current_year and (filter_cat == "All" or c['category'] == filter_cat)
        ]
                
        if not filtered_comps:
            st.info("No active competitions match your filters.")
        else:
            # Pre-calculate if any filtered comp is LIVE for the Auto-Refresh Timer
            any_live_matches = False
            for comp in filtered_comps:
                c_pairings = [p for p in pairings if p["competition_id"] == comp["id"]]
                if get_comp_status(c_pairings) == "LIVE":
                    any_live_matches = True
                    break
                    
            if any_live_matches:
                # Safe Auto-Refresh Implementation
                # Renders the visual box natively in Streamlit, then drives it via components.html script
                st.markdown("""
                <div style="text-align: center; color: #8bc34a; font-size: 14px; font-weight: bold; margin-bottom: 25px; margin-top: 10px; background-color: rgba(139, 195, 74, 0.1); padding: 8px; border-radius: 8px;">
                    🔴 LIVE: Auto-refreshing in <span id="timer-span">120</span>s
                </div>
                """, unsafe_allow_html=True)

                components.html(
                    """
                    <script>
                    if (window.parent && window.parent.document) {
                        if (window.parent.liveRefreshInterval) {
                            clearInterval(window.parent.liveRefreshInterval);
                        }
                        let time = 120;
                        window.parent.liveRefreshInterval = setInterval(function() {
                            time--;
                            let span = window.parent.document.getElementById('timer-span');
                            if (span) {
                                span.innerText = time;
                            }
                            if (time <= 0) {
                                clearInterval(window.parent.liveRefreshInterval);
                                window.parent.location.reload();
                            }
                        }, 1000);
                    }
                    </script>
                    """,
                    height=0,
                    width=0
                )

            for comp in filtered_comps:
                comp_pairings = sorted([p for p in pairings if p["competition_id"] == comp["id"]], 
                                       key=lambda x: x.get('display_order', 0))
                
                lb, opp = calculate_overall_score(comp_pairings)
                status = get_comp_status(comp_pairings)
                hide_names, reveal_time = should_hide_names(comp)
                comp_updated_time = get_comp_updated_time(comp_pairings)
                
                st.markdown(f"<h3 style='text-align: center; font-weight: 700; margin-bottom: 8px; margin-top: 20px;'>{get_comp_display_name(comp)}</h3>", unsafe_allow_html=True)
                
                # Big, obvious Native Refresh Button
                c1, c2, c3 = st.columns([1, 2, 1])
                with c2:
                    if st.button("↻ Refresh Scores", key=f"refresh_{comp['id']}", use_container_width=True):
                        fetch_all.clear()
                        st.rerun()

                match_dt = f"📅 {format_date_display(comp.get('match_date', 'TBD'))}"
                if comp.get('start_time'): match_dt += f" | 🕒 {comp.get('start_time')}"
                st.markdown(f"<p style='text-align: center; opacity: 0.7; font-size: 15px; margin-top: -5px;'>{match_dt}</p>", unsafe_allow_html=True)
                
                st.markdown(f"<div style='text-align: center; margin-bottom: 15px;'><span style='background-color: {'#8bc34a' if status=='LIVE' else 'gray'}; color: white; padding: 6px 16px; border-radius: 6px; font-weight: bold;'>{status}</span></div>", unsafe_allow_html=True)
                
                st.markdown(generate_scoreboard_html(lb, opp, comp['opposition_team']), unsafe_allow_html=True)
                
                # Auto-expand the pairings if the match is LIVE so it doesn't collapse on refresh
                is_live_comp = (status == "LIVE")
                with st.expander(f"View Pairings (Updated: {comp_updated_time})", expanded=is_live_comp):
                    if not comp_pairings:
                        st.write("Pairings to be announced.")
                    for i, p in enumerate(comp_pairings, start=1):
                        st.markdown(f"<div style='text-align:center; font-size:14px; font-weight: bold; opacity: 0.6; margin-bottom: 8px;'>Match {i}</div>", unsafe_allow_html=True)
                        st.markdown(generate_pairing_html(p, "public", hide_names, reveal_time, show_venue=True, match_index=i), unsafe_allow_html=True)
                        if i < len(comp_pairings):
                            st.write("---")
                st.divider()

    else:
        st.info("No active competitions.")

# --- VIEW 2: MANAGER PORTAL ---
elif role == "manager":
    raw_comp_param = query_params.get("comp", "")
    if "_" in raw_comp_param:
        parts = raw_comp_param.rsplit('_', 1)
        provided_id, provided_code = parts[0], parts[1]
    else:
        provided_id, provided_code = raw_comp_param, None

    comp = next((c for c in comps if generate_comp_id(c) == provided_id and c.get('access_code') == provided_code), None)
    
    if comp:
        st.markdown(f"<h3 style='text-align: center; font-weight: 700; margin-top: 15px;'>Manage:<br>{get_comp_display_name(comp)}</h3>", unsafe_allow_html=True)
        
        # Big, obvious Native Refresh Button
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            if st.button("↻ Refresh Scores", key=f"mgr_refresh_{comp['id']}", use_container_width=True):
                fetch_all.clear()
                st.rerun()

        match_dt = f"📅 {format_date_display(comp.get('match_date', 'TBD'))}"
        if comp.get('start_time'): match_dt += f" | 🕒 {comp.get('start_time')}"
        st.markdown(f"<p style='text-align: center; opacity: 0.7; font-size: 15px;'>{match_dt}</p>", unsafe_allow_html=True)
        
        comp_pairings = sorted([p for p in pairings if p["competition_id"] == comp["id"]], 
                               key=lambda x: x.get('display_order', 0))
        
        lb, opp = calculate_overall_score(comp_pairings)
        status = get_comp_status(comp_pairings)
        
        st.markdown(f"<p style='text-align: center; margin-bottom: 8px; font-size: 18px;'>Live Score: L&B <b>{lb}</b> - <b>{opp}</b> {comp['opposition_team']}</p>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align: center; margin-bottom: 25px;'><span style='background-color: {'#8bc34a' if status=='LIVE' else 'gray'}; color: white; padding: 6px 16px; border-radius: 6px; font-weight: bold; font-size: 14px;'>{status}</span></div>", unsafe_allow_html=True)
        st.divider()
        
        if not comp_pairings: st.info("No matches added to this competition yet.")
            
        for i, p in enumerate(comp_pairings, start=1):
            st.markdown(f"<div style='text-align:center; font-size:14px; font-weight:bold; opacity: 0.6; margin-bottom: 8px;'>Match {i}</div>", unsafe_allow_html=True)
            st.markdown(generate_pairing_html(p, "manager", hide_names=False, match_index=i), unsafe_allow_html=True)
            
            with st.expander(f"UPDATE MATCH {i} ({p['landb_player']})", expanded=False):
                # Stacking inputs vertically slightly improves mobile touch accuracy over columns
                h = st.selectbox("Hole", HOLE_OPTIONS, index=safe_index(HOLE_OPTIONS, str(p['hole'])), key=f"h_{p['id']}")
                sc = st.selectbox("Score (Relative to L&B)", SCORE_OPTIONS, index=safe_index(SCORE_OPTIONS, p['score']), key=f"sc_{p['id']}")
                
                st.write("")
                fin = st.checkbox("Match Finished (Check to lock final score)", value=(p['status'] == "FINISHED"), key=f"fin_{p['id']}")
                st.write("")
                
                if st.button("SAVE SCORE", key=f"btn_{p['id']}", type="primary", use_container_width=True):
                    new_leader = get_leader_from_score(sc)
                    
                    # Ensure timestamp saves strictly as UTC timezone aware so it corrects perfectly for Irish Summer Time
                    now_str = datetime.now(ZoneInfo("UTC")).isoformat()
                    
                    supabase.table("pairings").update({
                        "hole": h, "score": sc, "status": "FINISHED" if fin else "LIVE", "leader": new_leader, "updated_at": now_str
                    }).eq("id", p['id']).execute()
                    fetch_all.clear() 
                    st.success("Match Updated Successfully!"); time.sleep(1.5); st.rerun()
            st.divider()
    else:
        st.error("Invalid Manager Link. Competition not found or access code is incorrect.")

# --- VIEW 3: ADMIN CONSOLE ---
elif role == "admin":
    if "admin_auth" not in st.session_state:
        st.session_state.admin_auth = False

    if not st.session_state.admin_auth:
        st.markdown("<h2 style='text-align: center; margin-top: 30px;'>Admin Login</h2>", unsafe_allow_html=True)
        
        with st.form("admin_login_form"):
            pwd = st.text_input("Enter Admin Password", type="password")
            st.write("")
            submit_button = st.form_submit_button("Login", use_container_width=True)
            
            if submit_button:
                correct_password = st.secrets.get("ADMIN_PASSWORD", "")
                if pwd == correct_password and pwd != "":
                    st.session_state.admin_auth = True
                    st.rerun()
                else:
                    st.error("Incorrect password or ADMIN_PASSWORD secret not set.")
    else:
        st.header("Admin Console")
        c1, c2 = st.columns([3, 1])
        with c1:
            admin_year = st.selectbox("Global Admin View Year", all_years, index=0)
        with c2:
            st.write("") 
            st.write("") 
            if st.button("Logout", use_container_width=True):
                st.session_state.admin_auth = False
                st.rerun()
            
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Create Comp", "Edit Comp", "Add Match", "Edit Match", "Access Links", "Master List"])
        
        # TAB 1: CREATE COMPETITION
        with tab1:
            st.subheader("Create New Competition")
            if masters:
                master_opts = {f"{m['category']} - {m['comp_name']}": m for m in masters}
                selected_master = st.selectbox("Select from Master List", list(master_opts.keys()))
                m_data = master_opts[selected_master]
                
                with st.form("create_comp_form", clear_on_submit=True):
                    new_opp_team = st.text_input("Opposition Team")
                    new_round = st.selectbox("Round", ROUND_OPTIONS)
                    
                    new_date = st.date_input("Match Date", format="DD/MM/YYYY")
                    new_start_time = st.time_input("Start Time (Optional)", value=None)
                    
                    new_hide_mins = st.number_input("Hide Player Names Until (Mins before start)", min_value=0, value=60, step=15)
                    new_always_hide = st.checkbox("Always Hide Player Names (e.g. U18s)", value=False)
                    
                    st.write("")
                    if st.form_submit_button("Create Competition", use_container_width=True):
                        if new_opp_team:
                            secure_access_code = generate_random_code()
                            time_string = new_start_time.strftime("%H:%M") if new_start_time else None
                            round_val = new_round if new_round != "Not Applicable" else None
                            
                            match_year = new_date.year

                            supabase.table('competitions').insert({
                                "comp_name": m_data['comp_name'], 
                                "category": m_data['category'],
                                "opposition_team": new_opp_team, 
                                "round": round_val,
                                "match_date": str(new_date),
                                "year": match_year,
                                "start_time": time_string,
                                "hide_mins": new_hide_mins,
                                "always_hide_names": new_always_hide,
                                "archived": False,
                                "access_code": secure_access_code  
                            }).execute()
                            
                            fetch_all.clear() 
                            st.success(f"Created {m_data['category']} {m_data['comp_name']}!"); time.sleep(3); st.rerun()
                        else:
                            st.error("Please fill out the Opposition Team.")
            else:
                st.info("No master competitions found. Please add them in the 'Master List' tab first.")
                                  
        # TAB 2: EDIT COMP
        with tab2:
            st.subheader("Edit/Delete Competition")
            if comps:
                filter_cat = st.radio("Filter Category", ["All"] + CATEGORY_OPTIONS, horizontal=True, key="filter_edit_comp")
                
                # Filter by Year and Category
                filtered_comps = [
                    c for c in comps 
                    if c.get('year') == admin_year and (filter_cat == "All" or c['category'] == filter_cat)
                ]
                
                if filtered_comps:
                    comp_names_dict = {get_comp_display_name(c): c for c in filtered_comps}
                    edit_comp_name = st.selectbox("Select Competition", list(comp_names_dict.keys()), key="edit_comp_sel")
                    c_data = comp_names_dict[edit_comp_name]
                    
                    with st.form("edit_comp_form"):
                        e_cat = st.selectbox("Category", CATEGORY_OPTIONS, index=safe_index(CATEGORY_OPTIONS, c_data['category']))
                        e_name = st.text_input("Competition Name", value=c_data['comp_name'])
                        
                        e_opp = st.text_input("Opposition Team", value=c_data['opposition_team'])
                        
                        current_round = c_data.get('round')
                        e_round = st.selectbox("Round", ROUND_OPTIONS, index=safe_index(ROUND_OPTIONS, current_round if current_round else "Not Applicable"))
                        
                        try: parsed_date = datetime.strptime(c_data['match_date'], "%Y-%m-%d").date() if c_data.get('match_date') else datetime.now(ireland_tz).date()
                        except: parsed_date = datetime.now(ireland_tz).date()
                            
                        e_date = st.date_input("Match Date", value=parsed_date, format="DD/MM/YYYY")
                        parsed_time = safe_time_parse(c_data.get('start_time', ''))
                        e_time = st.time_input("Start Time", value=parsed_time)
                        
                        hide_val = c_data.get('hide_mins')
                        hide_val = int(hide_val) if hide_val is not None else 60
                        e_hide_mins = st.number_input("Hide Player Names Until (Mins before)", min_value=0, value=hide_val, step=15)
                        
                        st.write("")
                        e_always_hide = st.checkbox("Always Hide Player Names (e.g. U18s)", value=c_data.get('always_hide_names', False))
                        e_archived = st.checkbox("Archive Competition (Hide from Public)", value=c_data.get('archived', False))
                        st.write("")
                        
                        if st.form_submit_button("Update Competition", use_container_width=True):
                            updated_time_str = e_time.strftime("%H:%M") if e_time else None
                            updated_round_str = e_round if e_round != "Not Applicable" else None
                            
                            updated_year = e_date.year

                            try:
                                supabase.table('competitions').update({
                                    "comp_name": e_name, "category": e_cat, "opposition_team": e_opp, 
                                    "round": updated_round_str, "match_date": str(e_date), "year": updated_year, "start_time": updated_time_str,
                                    "hide_mins": e_hide_mins, "always_hide_names": e_always_hide, "archived": e_archived
                                }).eq('id', c_data['id']).execute()
                                
                                fetch_all.clear()
                                st.success("Updated!"); time.sleep(3); st.rerun()
                            except Exception as e:
                                st.error(f"Database Error: {e}")
                                
                    with st.popover(f"🚨 Delete {edit_comp_name} 🚨", key=f"del_comp_{c_data['id']}", use_container_width=True):
                        st.warning(f"Confirm deletion of {edit_comp_name}?")
                        del_comp_placeholder = st.empty()
                        if del_comp_placeholder.button("Yes, Delete", key=f"btn_del_comp_{c_data['id']}", type="primary", use_container_width=True):
                            del_comp_placeholder.empty()
                            supabase.table('competitions').delete().eq('id', c_data['id']).execute()
                            fetch_all.clear()
                            st.success("Deleted.")
                            time.sleep(1.5)
                            st.rerun()
                else:
                    st.info(f"No {filter_cat} competitions found for {admin_year}.")
                    
        # TAB 3: ADD MATCH
        with tab3:
            st.subheader("Add Match to Competition")
            if comps:
                filter_cat_add = st.radio("Filter Category", ["All"] + CATEGORY_OPTIONS, horizontal=True, key="filter_add_match")
                
                # Filter by Year and Category
                filtered_comps_add = [
                    c for c in comps 
                    if c.get('year') == admin_year and (filter_cat_add == "All" or c['category'] == filter_cat_add)
                ]
                
                if filtered_comps_add:
                    comp_names_dict_add = {get_comp_display_name(c): c['id'] for c in filtered_comps_add}
                    target_comp_title = st.selectbox("Select Competition", list(comp_names_dict_add.keys()), key="add_match_sel")
                    
                    target_comp_data = next((c for c in filtered_comps_add if get_comp_display_name(c) == target_comp_title), None)
                    default_opp_name = target_comp_data["opposition_team"] if target_comp_data else ""
                    
                    with st.form("create_pairing_form", clear_on_submit=True):
                        lb_player_input = st.text_input("L&B Player Name")
                        opp_player_input = st.text_input("Opposition Player Name", value=default_opp_name)
                        match_venue = st.selectbox("Venue", VENUE_OPTIONS)
                        
                        st.write("")
                        if st.form_submit_button("Add Match Pairing", use_container_width=True):
                            if lb_player_input and opp_player_input:
                                target_comp_id = comp_names_dict_add[target_comp_title]
                                existing = [p for p in pairings if p["competition_id"] == target_comp_id]
                                next_order = (max([p.get('display_order', 0) for p in existing], default=0)) + 1
                                
                                now_str = datetime.now(ZoneInfo("UTC")).isoformat()
                                supabase.table('pairings').insert({
                                    "competition_id": target_comp_id,
                                    "landb_player": lb_player_input, 
                                    "opposition_player": opp_player_input,
                                    "venue": match_venue, "hole": "1", "score": "All Square",
                                    "status": "Not Started", "leader": "Tied",
                                    "display_order": next_order,
                                    "updated_at": now_str
                                }).execute()
                                
                                fetch_all.clear()
                                st.success("Match added!"); time.sleep(1.5); st.rerun()
                            else:
                                st.error("Please enter both player names.") 
                else:
                    st.info(f"No {filter_cat_add} competitions found for {admin_year}.")

        # TAB 4: EDIT MATCH
        with tab4:
            st.subheader("Edit/Delete Match")
            if comps:
                filter_cat_m = st.radio("Filter Category", ["All"] + CATEGORY_OPTIONS, horizontal=True, key="filter_edit_match")
                
                # Filter by Year and Category
                filtered_comps_m = [
                    c for c in comps 
                    if c.get('year') == admin_year and (filter_cat_m == "All" or c['category'] == filter_cat_m)
                ]
                
                if filtered_comps_m:
                    comp_names_dict_m = {get_comp_display_name(c): c['id'] for c in filtered_comps_m}
                    t_comp = st.selectbox("Competition", list(comp_names_dict_m.keys()), key="edit_m_c")
                    
                    p_list = sorted([p for p in pairings if p["competition_id"] == comp_names_dict_m[t_comp]], 
                                    key=lambda x: x.get('display_order', 0))
                    
                    if p_list:
                        p_opts = {f"{p.get('landb_player')} vs {p.get('opposition_player')}": p for p in p_list}
                        sel_p = st.selectbox("Match to Edit", list(p_opts.keys()))
                        p_data = p_opts[sel_p]
                        
                        with st.form("edit_match_form"):
                            e_lb = st.text_input("L&B Player", value=p_data.get('landb_player', ''))
                            e_opp = st.text_input("Opposition Player", value=p_data.get('opposition_player', ''))
                            
                            e_venue = st.selectbox("Venue", VENUE_OPTIONS, index=safe_index(VENUE_OPTIONS, p_data.get('venue', 'Home')))
                            e_order = st.number_input("Display Order", value=p_data.get('display_order', 0), step=1)
                            
                            st.write("")
                            if st.form_submit_button("Update Match", use_container_width=True):
                                now_str = datetime.now(ZoneInfo("UTC")).isoformat()
                                supabase.table('pairings').update({
                                    "landb_player": e_lb, 
                                    "opposition_player": e_opp, 
                                    "venue": e_venue,
                                    "display_order": e_order,
                                    "updated_at": now_str
                                }).eq('id', p_data['id']).execute()
                                
                                fetch_all.clear() 
                                st.success("Updated!"); time.sleep(1.5); st.rerun()
                        
                        with st.popover("🚨 Delete Match 🚨", key=f"del_match_{p_data['id']}", use_container_width=True):
                            st.warning("Confirm deletion of this match?")
                            del_match_placeholder = st.empty()
                            if del_match_placeholder.button("Yes, Delete", key=f"btn_del_match_{p_data['id']}", type="primary", use_container_width=True):
                                del_match_placeholder.empty()
                                supabase.table('pairings').delete().eq('id', p_data['id']).execute()
                                fetch_all.clear()
                                st.success("Deleted.")
                                time.sleep(1.5)
                                st.rerun()
                    else:
                        st.info("No matches in this competition.")
                else:
                    st.info(f"No {filter_cat_m} competitions found for {admin_year}.")
                    
        # TAB 5: ACCESS LINKS
        with tab5:
            st.subheader("System Access Links")
            st.write("Save these links or send them to your team managers.")
            
            st.markdown("**Admin Console Link** (Password Required):")
            st.code(f"{APP_BASE_URL}/?role=admin", language="text")
            
            st.divider()
            st.markdown("**Manager Portal Links**:")
            
            filter_cat_links = st.radio("Filter Category", ["All"] + CATEGORY_OPTIONS, horizontal=True, key="filter_links")
            show_archived = st.checkbox("Show Archived Competitions")
            
            # Apply filters for year, category, and archive status
            filtered_comps_links = [
                c for c in comps 
                if c.get('year') == admin_year 
                and (filter_cat_links == "All" or c['category'] == filter_cat_links)
                and (show_archived or not c.get('archived', False))
            ]
            
            if filtered_comps_links:
                for c in filtered_comps_links:
                    comp_id = generate_comp_id(c)
                    secure_comp_id = f"{comp_id}_{c.get('access_code', '000000')}"
                    
                    display_title = f"{get_comp_display_name(c)} {'(Archived)' if c.get('archived') else ''}"
                    
                    st.markdown(f"**{display_title}**")
                    st.code(f"{APP_BASE_URL}/?role=manager&comp={secure_comp_id}", language="text")
            else:
                st.info(f"No links found for the selected filters in {admin_year}.")

        # TAB 6: MASTER LIST MANAGEMENT
        with tab6:
            st.subheader("Manage Master Competition List")
            m_action = st.radio("Action", ["Add to Master", "Edit/Delete Master"], horizontal=True)
            
            if m_action == "Add to Master":
                with st.form("add_master_form", clear_on_submit=True):
                    m_name = st.text_input("Competition Name (e.g., Barton Shield)")
                    m_cat = st.selectbox("Category", CATEGORY_OPTIONS)
                    
                    st.write("")
                    if st.form_submit_button("Add to Master", use_container_width=True):
                        if m_name:
                            supabase.table("competitions_master").insert({
                                "comp_name": m_name, "category": m_cat
                            }).execute()
                            fetch_all.clear()
                            st.success(f"Added {m_name} to Master List!"); time.sleep(1.5); st.rerun()
                        else:
                            st.error("Competition Name is required.")

            elif m_action == "Edit/Delete Master":
                if masters:
                    # Filter and sort the Master List for easier editing
                    filter_cat_master = st.radio("Filter Category", ["All"] + CATEGORY_OPTIONS, horizontal=True, key="filter_master")
                    filtered_masters = [m for m in masters if filter_cat_master == "All" or m.get('category') == filter_cat_master]
                    
                    # Sort Alphabetically by Category, then by Competition Name
                    filtered_masters = sorted(filtered_masters, key=lambda x: (x.get('category', ''), x.get('comp_name', '')))
                    
                    if filtered_masters:
                        m_opts = {f"{m['category']} - {m['comp_name']}": m for m in filtered_masters}
                        sel_m = st.selectbox("Select Master Template to Edit", list(m_opts.keys()))
                        m_data = m_opts[sel_m]
                        
                        with st.form("edit_master_form"):
                            e_name = st.text_input("Name", value=m_data['comp_name'])
                            e_cat = st.selectbox("Category", CATEGORY_OPTIONS, index=safe_index(CATEGORY_OPTIONS, m_data['category']))
                            
                            st.write("")
                            if st.form_submit_button("Update Master Template", use_container_width=True):
                                supabase.table("competitions_master").update({
                                    "comp_name": e_name, "category": e_cat
                                }).eq("id", m_data['id']).execute()
                                fetch_all.clear()
                                st.success("Updated Template!"); time.sleep(1.5); st.rerun()
                        
                        with st.popover(f"🚨 Delete {m_data['comp_name']} 🚨", use_container_width=True):
                            st.warning(f"Confirm deletion of {m_data['comp_name']} from Master List?")
                            del_master_placeholder = st.empty()
                            if del_master_placeholder.button("Yes, Delete", key=f"btn_del_master_{m_data['id']}", type="primary", use_container_width=True):
                                del_master_placeholder.empty()
                                supabase.table("competitions_master").delete().eq("id", m_data['id']).execute()
                                fetch_all.clear()
                                st.success("Deleted from Master List.")
                                time.sleep(1.5)
                                st.rerun()
                    else:
                        st.info("No master competitions match this filter.")
                else:
                    st.info("No master competitions found to edit.")
