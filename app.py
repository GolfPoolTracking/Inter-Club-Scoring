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

# --- Random code generator for unique keys ---
def generate_random_code(length=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

# --- CONFIGURATION & STYLING ---
st.set_page_config(page_title="L&B Match Centre", layout="centered", initial_sidebar_state="collapsed")

# Inject Noto Serif font safely and hide default menus
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif:wght@400;700&display=swap');
div, p, h1, h2, h3, h4, h5, h6, .stMarkdown, .stButton, .stRadio, .stCheckbox { 
    font-family: 'Noto Serif', serif !important; 
}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
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

def should_hide_names(comp):
    """Calculates if the current time is before the reveal window."""
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
    return f"<div style='display: flex; justify-content: space-between; align-items: center; width: 100%; margin-bottom: 20px; max-width: 600px; margin-left: auto; margin-right: auto;'><div style='flex: 2; text-align: center; padding: 0 10px;'><div style='font-weight: bold; margin-bottom: 5px; font-size: 16px;'>L&B</div><div style='background-color: {LB_COLOR}; color: white; padding: 12px; border-radius: 5px; font-weight: bold; font-size: 24px;'>{lb_score}</div></div><div style='flex: 1; text-align: center; font-size: 35px; font-weight: bold; padding-top: 25px;'>:</div><div style='flex: 2; text-align: center; padding: 0 10px;'><div style='font-weight: bold; margin-bottom: 5px; font-size: 16px;'>{opp_team_name}</div><div style='background-color: {OPP_COLOR}; color: white; padding: 12px; border-radius: 5px; font-weight: bold; font-size: 24px;'>{opp_score}</div></div></div>"

def generate_pairing_html(p, view_mode="public", hide_names=False, reveal_time=None, show_venue=False):
    if hide_names and reveal_time:
        lb_name_display = f"Reveals {reveal_time.strftime('%H:%M')}"
        opp_name_display = "TBD"
    else:
        lb_name_display = p.get('landb_player', 'TBD')
        opp_name_display = p.get('opposition_player', 'TBD')

    is_started = p['status'] in ["LIVE", "FINISHED"]
    tied_text = "&nbsp;" if is_started else "ALL SQUARE"

    if p['leader'] == 'L&B':
        lb_score_html = f"<div style='background-color: {LB_COLOR}; color: white; text-align: center; padding: 4px; font-weight: bold; border-radius: 3px;'>{p['score']}</div>"
    elif p['leader'] == 'Tied':
        lb_score_html = f"<div style='background-color: {TIE_COLOR}; color: white; text-align: center; padding: 4px; font-weight: bold; border-radius: 3px;'>{tied_text}</div>"
    else:
        lb_score_html = f"<div style='padding: 4px; visibility: hidden;'>Spacer</div>"
        
    if p['leader'] == 'Opposition':
        opp_score_html = f"<div style='background-color: {OPP_COLOR}; color: white; text-align: center; padding: 4px; font-weight: bold; border-radius: 3px;'>{p['score'].replace('Down', 'Up')}</div>"
    elif p['leader'] == 'Tied':
        opp_score_html = f"<div style='background-color: {TIE_COLOR}; color: white; text-align: center; padding: 4px; font-weight: bold; border-radius: 3px;'>{tied_text}</div>"
    else:
        opp_score_html = f"<div style='padding: 4px; visibility: hidden;'>Spacer</div>"
        
    hole_val = str(p.get('hole', '1'))
    hole_display = f"Hole {hole_val}" if hole_val.isdigit() else hole_val 
    p_status_color = "gray" if p['status'] == "Not Started" else ("darkred" if p['status'] == "FINISHED" else "#8bc34a")
    
    should_show = (view_mode == "manager") or show_venue
    venue_html = f"<div style='font-size: 11px; color: gray; margin-top: 4px;'>📍 {p.get('venue', 'Unknown')}</div>" if should_show else ""
    return f"<div style='display: flex; justify-content: space-between; align-items: flex-start; width: 100%; margin-bottom: 10px;'><div style='flex: 1; text-align: center; padding: 0 4px; width: 33%;'>{lb_score_html}<div style='font-weight: bold; font-size: 15px; margin-top: 6px; line-height: 1.2;'>{lb_name_display}</div>{venue_html}</div><div style='flex: 1; text-align: center; padding: 0 4px; width: 33%;'><div style='background-color: black; color: white; padding: 2px; font-size: 13px; border-radius: 3px; margin-bottom: 4px;'>{hole_display}</div><div style='background-color: {p_status_color}; color: white; padding: 2px; font-size: 11px; font-weight: bold; border-radius: 3px;'>{p['status']}</div></div><div style='flex: 1; text-align: center; padding: 0 4px; width: 33%;'>{opp_score_html}<div style='font-weight: bold; font-size: 15px; margin-top: 6px; line-height: 1.2;'>{opp_name_display}</div></div></div>"

# --- LIST DEFINITIONS ---
HOLE_OPTIONS = [str(i) for i in range(1, 19)] + [f"Extra Hole {i}" for i in range(1, 10)]
SCORE_OPTIONS = [f"{i} Up" for i in range(10, 0, -1)] + ["All Square"] + [f"{i} Down" for i in range(1, 11)]
VENUE_OPTIONS = ["Home", "Away"]
CATEGORY_OPTIONS = ["Mens", "Womens", "Boys", "Girls", "Mixed"]

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

# --- SECURE URL ROUTING ---
query_params = st.query_params
role = query_params.get("role", "public")

# --- VIEW 1: PUBLIC SCOREBOARD ---
if role == "public":
    logo_base64 = get_base64_image("app/static/lb_logo.png") or get_base64_image("static/lb_logo.png")
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" width="120" style="margin-bottom: 5px;"/>' if logo_base64 else ""

    st.markdown(f"<div style='text-align: center;'>{logo_html}<h2 style='font-weight: 700; margin-top: 0px;'>L&B Match Centre</h2></div>", unsafe_allow_html=True)
    st.divider()
    
    active_comps = [c for c in comps if not c.get('archived', False)]
    
    if active_comps:
        if st.button("↻ Refresh Scores", use_container_width=True): 
            fetch_all.clear()
            st.rerun()
            
        # Get unique years from the 'year' column, default to current if empty
        years = sorted(list(set([c.get('year', datetime.now(ireland_tz).year) for c in active_comps if c.get('year')])), reverse=True)
        if not years: years = [datetime.now(ireland_tz).year]
        
        c_yr, c_cat = st.columns([1, 3])
        with c_yr:
            sel_year = st.selectbox("Year", years)
        with c_cat:
            filter_cat = st.radio("Category", ["All"] + CATEGORY_OPTIONS, horizontal=True)
            
        # Efficiently filter using the database 'year' column
        filtered_comps = [
            c for c in active_comps 
            if c.get('year') == sel_year and (filter_cat == "All" or c['category'] == filter_cat)
        ]
                
        if not filtered_comps:
            st.info("No competitions match your filters.")
            
        for comp in filtered_comps:
            # Sort pairings by display_order
            comp_pairings = sorted([p for p in pairings if p["competition_id"] == comp["id"]], 
                                   key=lambda x: x.get('display_order', 0))
            
            lb, opp = calculate_overall_score(comp_pairings)
            status = get_comp_status(comp_pairings)
            hide_names, reveal_time = should_hide_names(comp)
            
            # Header with Date and Time
            st.markdown(f"<h3 style='text-align: center; font-weight: 700; margin-bottom: 2px;'>{get_comp_display_name(comp)}</h3>", unsafe_allow_html=True)
            match_dt = f"📅 {format_date_display(comp.get('match_date', 'TBD'))}"
            if comp.get('start_time'): match_dt += f" | 🕒 {comp.get('start_time')}"
            st.markdown(f"<p style='text-align: center; color: #555; font-size: 14px;'>{match_dt}</p>", unsafe_allow_html=True)
            
            st.markdown(f"<div style='text-align: center;'><span style='background-color: {'#8bc34a' if status=='LIVE' else 'gray'}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold;'>{status}</span></div>", unsafe_allow_html=True)
            
            st.markdown(generate_scoreboard_html(lb, opp, comp['opposition_team']), unsafe_allow_html=True)
            
            with st.expander(f"View Pairings (Last updated: {datetime.now(ireland_tz).strftime('%H:%M')})"):
                if not comp_pairings:
                    st.write("Pairings to be announced.")
                for i, p in enumerate(comp_pairings, start=1):
                    st.markdown(f"<div style='text-align:center; font-size:12px; color:gray;'>Match {i}</div>", unsafe_allow_html=True)
                    st.markdown(generate_pairing_html(p, "public", hide_names, reveal_time, show_venue=True), unsafe_allow_html=True)
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
        st.markdown(f"<h3 style='text-align: center; font-weight: 700;'>Manage: {get_comp_display_name(comp)}</h3>", unsafe_allow_html=True)
        # Date/Time for Manager
        match_dt = f"📅 {format_date_display(comp.get('match_date', 'TBD'))}"
        if comp.get('start_time'): match_dt += f" | 🕒 {comp.get('start_time')}"
        st.markdown(f"<p style='text-align: center; color: #555; font-size: 14px;'>{match_dt}</p>", unsafe_allow_html=True)
        
        comp_pairings = sorted([p for p in pairings if p["competition_id"] == comp["id"]], 
                               key=lambda x: x.get('display_order', 0))
        
        lb, opp = calculate_overall_score(comp_pairings)
        status = get_comp_status(comp_pairings)
        
        st.markdown(f"<p style='text-align: center; margin-bottom: 5px;'>Live Score: L&B <b>{lb}</b> - <b>{opp}</b> {comp['opposition_team']}</p>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align: center; margin-bottom: 20px;'><span style='background-color: {'#8bc34a' if status=='LIVE' else 'gray'}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 12px;'>{status}</span></div>", unsafe_allow_html=True)
        st.divider()
        
        if not comp_pairings: st.info("No matches added to this competition yet.")
            
        for i, p in enumerate(comp_pairings, start=1):
            st.markdown(f"<div style='text-align:center; font-size:12px; color:gray;'>Match {i}</div>", unsafe_allow_html=True)
            st.markdown(generate_pairing_html(p, "manager", hide_names=False), unsafe_allow_html=True)
            
            with st.expander(f"Update Match {i}: {p['landb_player']} vs {p['opposition_player']}", expanded=False):
                uc1, uc2 = st.columns(2)
                h = uc1.selectbox("Hole", HOLE_OPTIONS, index=safe_index(HOLE_OPTIONS, str(p['hole'])), key=f"h_{p['id']}")
                sc = uc2.selectbox("Score (Relative to L&B)", SCORE_OPTIONS, index=safe_index(SCORE_OPTIONS, p['score']), key=f"sc_{p['id']}")
                fin = st.checkbox("Match Finished (Check to lock final score)", value=(p['status'] == "FINISHED"), key=f"fin_{p['id']}")
                
                if st.button("Save Match Update", key=f"btn_{p['id']}", type="primary"):
                    new_leader = get_leader_from_score(sc)
                    supabase.table("pairings").update({
                        "hole": h, "score": sc, "status": "FINISHED" if fin else "LIVE", "leader": new_leader
                    }).eq("id", p['id']).execute()
                    fetch_all.clear() 
                    st.success("Updated!"); time.sleep(1.5); st.rerun()
            st.divider()
    else:
        st.error("Invalid Manager Link. Competition not found or access code is incorrect.")

# --- VIEW 3: ADMIN CONSOLE ---
elif role == "admin":
    if "admin_auth" not in st.session_state:
        st.session_state.admin_auth = False

    if not st.session_state.admin_auth:
        st.markdown("<h2 style='text-align: center;'>Admin Login</h2>", unsafe_allow_html=True)
        
        with st.form("admin_login_form"):
            pwd = st.text_input("Enter Admin Password", type="password")
            submit_button = st.form_submit_button("Login", use_container_width=True)
            
            if submit_button:
                # Fallback to empty string to prevent crashes if secret is missing
                correct_password = st.secrets.get("ADMIN_PASSWORD")
                if pwd == correct_password and pwd != "":
                    st.session_state.admin_auth = True
                    st.rerun()
                else:
                    st.error("Incorrect password or ADMIN_PASSWORD secret not set.")
    else:
        st.header("Admin Console")
        if st.button("Logout of Admin"):
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
                    col1, col2 = st.columns(2)
                    # Opposition team is manually entered since it's no longer in the master table
                    new_opp_team = col1.text_input("Opposition Team")
                    new_round = col2.text_input("Round (e.g., Semi-Final)")
                    
                    col3, col4 = st.columns(2)
                    new_date = col3.date_input("Match Date", format="DD/MM/YYYY")
                    new_start_time = col4.time_input("Start Time (Optional)", value=None)
                    
                    new_hide_mins = st.number_input("Hide Player Names Until (Mins before start)", min_value=0, value=60, step=15)
                    
                    if st.form_submit_button("Create Competition"):
                        if new_opp_team:
                            secure_access_code = generate_random_code()
                            time_string = new_start_time.strftime("%H:%M") if new_start_time else None
                            round_val = new_round if new_round.strip() else None
                            
                            # EXTRACT YEAR
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
                filtered_comps = [c for c in comps if filter_cat == "All" or c['category'] == filter_cat]
                
                if filtered_comps:
                    comp_names_dict = {get_comp_display_name(c): c for c in filtered_comps}
                    edit_comp_name = st.selectbox("Select Competition", list(comp_names_dict.keys()), key="edit_comp_sel")
                    c_data = comp_names_dict[edit_comp_name]
                    
                    with st.form("edit_comp_form"):
                        e_c1, e_c2 = st.columns(2)
                        e_cat = e_c1.selectbox("Category", CATEGORY_OPTIONS, index=safe_index(CATEGORY_OPTIONS, c_data['category']))
                        e_name = e_c2.text_input("Competition Name", value=c_data['comp_name'])
                        
                        e_c3, e_c4 = st.columns(2)
                        e_opp = e_c3.text_input("Opposition Team", value=c_data['opposition_team'])
                        e_round = e_c4.text_input("Round", value=c_data.get('round', ''))
                        
                        e_c5, e_c6 = st.columns(2)
                        try: parsed_date = datetime.strptime(c_data['match_date'], "%Y-%m-%d").date() if c_data.get('match_date') else datetime.now(ireland_tz).date()
                        except: parsed_date = datetime.now(ireland_tz).date()
                            
                        e_date = e_c5.date_input("Match Date", value=parsed_date, format="DD/MM/YYYY")
                        parsed_time = safe_time_parse(c_data.get('start_time', ''))
                        e_time = e_c6.time_input("Start Time", value=parsed_time)
                        
                        hide_val = c_data.get('hide_mins')
                        hide_val = int(hide_val) if hide_val is not None else 60
                        e_hide_mins = st.number_input("Hide Player Names Until (Mins before)", min_value=0, value=hide_val, step=15)
                        e_archived = st.checkbox("Archive Competition (Hide from Public)", value=c_data.get('archived', False))
                        
                        if st.form_submit_button("Update Competition"):
                            updated_time_str = e_time.strftime("%H:%M") if e_time else None
                            updated_round_str = e_round if e_round.strip() else None
                            
                            # EXTRACT YEAR
                            updated_year = e_date.year

                            try:
                                supabase.table('competitions').update({
                                    "comp_name": e_name, "category": e_cat, "opposition_team": e_opp, 
                                    "round": updated_round_str, "match_date": str(e_date), "year": updated_year, "start_time": updated_time_str,
                                    "hide_mins": e_hide_mins, "archived": e_archived
                                }).eq('id', c_data['id']).execute()
                                
                                fetch_all.clear()
                                st.success("Updated!"); time.sleep(3); st.rerun()
                            except Exception as e:
                                st.error(f"Database Error: {e}")
                                
                    with st.popover(f"🚨 Delete {edit_comp_name} 🚨", key=f"del_comp_{c_data['id']}"):
                        st.warning(f"Confirm deletion of {edit_comp_name}?")
                        if st.button("Yes, Delete", key=f"btn_del_comp_{c_data['id']}", type="primary"):
                            supabase.table('competitions').delete().eq('id', c_data['id']).execute()
                            fetch_all.clear()
                            st.success("Deleted.")
                            time.sleep(3)
                            st.rerun()
                else:
                    st.info(f"No {filter_cat} competitions found.")
                    

        # TAB 3: ADD MATCH
        with tab3:
            st.subheader("Add Match to Competition")
            if comps:
                filter_cat_add = st.radio("Filter Category", ["All"] + CATEGORY_OPTIONS, horizontal=True, key="filter_add_match")
                filtered_comps_add = [c for c in comps if filter_cat_add == "All" or c['category'] == filter_cat_add]
                
                if filtered_comps_add:
                    comp_names_dict_add = {get_comp_display_name(c): c['id'] for c in filtered_comps_add}
                    target_comp_title = st.selectbox("Select Competition", list(comp_names_dict_add.keys()), key="add_match_sel")
                    
                    target_comp_data = next((c for c in filtered_comps_add if get_comp_display_name(c) == target_comp_title), None)
                    default_opp_name = target_comp_data["opposition_team"] if target_comp_data else ""
                    
                    with st.form("create_pairing_form", clear_on_submit=True):
                        col1, col2 = st.columns(2)
                        lb_player_input = col1.text_input("L&B Player Name")
                        opp_player_input = col2.text_input("Opposition Player Name", value=default_opp_name)
                        match_venue = st.selectbox("Venue", VENUE_OPTIONS)
                        
                        if st.form_submit_button("Add Match Pairing"):
                            if lb_player_input and opp_player_input:
                                target_comp_id = comp_names_dict_add[target_comp_title]
                                # Get existing matches to find next display_order
                                existing = [p for p in pairings if p["competition_id"] == target_comp_id]
                                next_order = (max([p.get('display_order', 0) for p in existing], default=0)) + 1
                                
                                supabase.table('pairings').insert({
                                    "competition_id": target_comp_id,
                                    "landb_player": lb_player_input, 
                                    "opposition_player": opp_player_input,
                                    "venue": match_venue, "hole": "1", "score": "All Square",
                                    "status": "Not Started", "leader": "Tied",
                                    "display_order": next_order
                                }).execute()
                                
                                fetch_all.clear()
                                st.success("Match added!"); time.sleep(1.5); st.rerun()
                            else:
                                st.error("Please enter both player names.") 
        
        # TAB 4: EDIT MATCH
        with tab4:
            st.subheader("Edit/Delete Match")
            if comps:
                filter_cat_m = st.radio("Filter Category", ["All"] + CATEGORY_OPTIONS, horizontal=True, key="filter_edit_match")
                filtered_comps_m = [c for c in comps if filter_cat_m == "All" or c['category'] == filter_cat_m]
                
                if filtered_comps_m:
                    comp_names_dict_m = {get_comp_display_name(c): c['id'] for c in filtered_comps_m}
                    t_comp = st.selectbox("Competition", list(comp_names_dict_m.keys()), key="edit_m_c")
                    # Sort by display_order for the selection list
                    p_list = sorted([p for p in pairings if p["competition_id"] == comp_names_dict_m[t_comp]], 
                                    key=lambda x: x.get('display_order', 0))
                    
                    if p_list:
                        p_opts = {f"{p.get('landb_player')} vs {p.get('opposition_player')}": p for p in p_list}
                        sel_p = st.selectbox("Match to Edit", list(p_opts.keys()))
                        p_data = p_opts[sel_p]
                        
                        with st.form("edit_match_form"):
                            col1, col2 = st.columns(2)
                            e_lb = col1.text_input("L&B Player", value=p_data.get('landb_player', ''))
                            e_opp = col2.text_input("Opposition Player", value=p_data.get('opposition_player', ''))
                            
                            e_c3, e_c4 = st.columns(2)
                            e_venue = e_c3.selectbox("Venue", VENUE_OPTIONS, index=safe_index(VENUE_OPTIONS, p_data.get('venue', 'Home')))
                            e_order = e_c4.number_input("Display Order", value=p_data.get('display_order', 0), step=1)
                            
                            if st.form_submit_button("Update Match"):
                                supabase.table('pairings').update({
                                    "landb_player": e_lb, 
                                    "opposition_player": e_opp, 
                                    "venue": e_venue,
                                    "display_order": e_order
                                }).eq('id', p_data['id']).execute()
                                
                                fetch_all.clear() 
                                st.success("Updated!"); time.sleep(1.5); st.rerun()
                        
                        # Confirmation popover before deleting a match
                        with st.popover("🚨 Delete Match 🚨", key=f"del_match_{p_data['id']}", use_container_width=True):
                            st.warning("Confirm deletion of this match?")
                            if st.button("Yes, Delete", key=f"btn_del_match_{p_data['id']}", type="primary"):
                                supabase.table('pairings').delete().eq('id', p_data['id']).execute()
                                fetch_all.clear()
                                st.success("Deleted.")
                                time.sleep(1.5)
                                st.rerun()
                    else:
                        st.info("No matches in this competition.")
                else:
                    st.info(f"No {filter_cat_m} competitions found.")
                    
        # TAB 5: ACCESS LINKS
        with tab5:
            st.subheader("System Access Links")
            st.write("Save these links or send them to your team managers.")
            
            st.markdown("**Admin Console Link** (Password Required):")
            st.code(f"{APP_BASE_URL}/?role=admin", language="text")
            
            st.divider()
            st.markdown("**Manager Portal Links** (Locks user to specific competition):")
            
            filter_cat_links = st.radio("Filter Category", ["All"] + CATEGORY_OPTIONS, horizontal=True, key="filter_links")
            filtered_comps_links = [c for c in comps if filter_cat_links == "All" or c['category'] == filter_cat_links]
            
            if filtered_comps_links:
                for c in filtered_comps_links:
                    comp_id = generate_comp_id(c)
                    # Append the access code to the existing ID
                    secure_comp_id = f"{comp_id}_{c.get('access_code', '000000')}"
                    
                    display_title = get_comp_display_name(c)
                    
                    st.markdown(f"**{display_title}**")
                    st.code(f"{APP_BASE_URL}/?role=manager&comp={secure_comp_id}", language="text")
            else:
                st.info(f"No {filter_cat_links} competitions found.")

        # TAB 6: MASTER LIST MANAGEMENT
        with tab6:
            st.subheader("Manage Master Competition List")
            m_action = st.radio("Action", ["Add to Master", "Edit/Delete Master"], horizontal=True)
            
            if m_action == "Add to Master":
                with st.form("add_master_form"):
                    m_name = st.text_input("Competition Name (e.g., Barton Shield)")
                    m_cat = st.selectbox("Category", CATEGORY_OPTIONS)
                    if st.form_submit_button("Add to Master"):
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
                    m_opts = {f"{m['category']} - {m['comp_name']}": m for m in masters}
                    sel_m = st.selectbox("Select Master Template to Edit", list(m_opts.keys()))
                    m_data = m_opts[sel_m]
                    
                    with st.form("edit_master_form"):
                        e_name = st.text_input("Name", value=m_data['comp_name'])
                        e_cat = st.selectbox("Category", CATEGORY_OPTIONS, index=safe_index(CATEGORY_OPTIONS, m_data['category']))
                        if st.form_submit_button("Update Master Template"):
                            supabase.table("competitions_master").update({
                                "comp_name": e_name, "category": e_cat
                            }).eq("id", m_data['id']).execute()
                            fetch_all.clear()
                            st.success("Updated Template!"); time.sleep(1.5); st.rerun()
                    
                    with st.popover(f"🚨 Delete {m_data['comp_name']} 🚨", use_container_width=True):
                        st.warning(f"Confirm deletion of {m_data['comp_name']} from Master List?")
                        if st.button("Yes, Delete", key=f"btn_del_master_{m_data['id']}", type="primary"):
                            supabase.table("competitions_master").delete().eq("id", m_data['id']).execute()
                            fetch_all.clear()
                            st.success("Deleted from Master List.")
                            time.sleep(1.5)
                            st.rerun()
                else:
                    st.info("No master competitions found to edit.")
