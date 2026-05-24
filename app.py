import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import time
from supabase import create_client
import urllib.parse
import base64

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
ireland_tz = ZoneInfo("Europe/Dublin")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- HELPERS ---
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
    return lb, opp

def safe_index(lst, val): return lst.index(val) if val in lst else 0

# --- HTML GENERATORS (FOR MOBILE-SAFE SIDE-BY-SIDE LAYOUTS) ---
def generate_scoreboard_html(lb_score, opp_score, opp_team_name):
    return f"""
    <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; margin-bottom: 20px; max-width: 600px; margin-left: auto; margin-right: auto;">
        <div style="flex: 2; text-align: center; padding: 0 10px;">
            <div style="font-weight: bold; margin-bottom: 5px; font-size: 16px;">L&B</div>
            <div style="background-color: {LB_COLOR}; color: white; padding: 12px; border-radius: 5px; font-weight: bold; font-size: 24px;">{lb_score}</div>
        </div>
        <div style="flex: 1; text-align: center; font-size: 35px; font-weight: bold; padding-top: 25px;">
            :
        </div>
        <div style="flex: 2; text-align: center; padding: 0 10px;">
            <div style="font-weight: bold; margin-bottom: 5px; font-size: 16px;">{opp_team_name}</div>
            <div style="background-color: {OPP_COLOR}; color: white; padding: 12px; border-radius: 5px; font-weight: bold; font-size: 24px;">{opp_score}</div>
        </div>
    </div>
    """

def generate_pairing_html(p, view_mode="public"):
    # L&B Score Block
    if p['leader'] == 'L&B':
        lb_score_html = f"<div style='background-color: {LB_COLOR}; color: white; text-align: center; padding: 4px; font-weight: bold; border-radius: 3px;'>{p['score']}</div>"
    elif p['leader'] == 'Tied':
        lb_score_html = f"<div style='background-color: {TIE_COLOR}; color: white; text-align: center; padding: 4px; font-weight: bold; border-radius: 3px;'>ALL SQUARE</div>"
    else:
        # Invisible spacer maintains exact height to keep names perfectly aligned
        lb_score_html = f"<div style='padding: 4px; visibility: hidden;'>Spacer</div>"
        
    # Opp Score Block
    if p['leader'] == 'Opposition':
        opp_score_html = f"<div style='background-color: {OPP_COLOR}; color: white; text-align: center; padding: 4px; font-weight: bold; border-radius: 3px;'>{p['score'].replace('Down', 'Up')}</div>"
    elif p['leader'] == 'Tied':
        opp_score_html = f"<div style='background-color: {TIE_COLOR}; color: white; text-align: center; padding: 4px; font-weight: bold; border-radius: 3px;'>ALL SQUARE</div>"
    else:
        opp_score_html = f"<div style='padding: 4px; visibility: hidden;'>Spacer</div>"
        
    hole_val = str(p.get('hole', '1'))
    hole_display = f"Hole {hole_val}" if hole_val.isdigit() else hole_val 
    p_status_color = "gray" if p['status'] == "Not Started" else ("darkred" if p['status'] == "FINISHED" else "#8bc34a")
    
    venue_html = f"<div style='font-size: 11px; color: gray; margin-top: 4px;'>📍 {p.get('venue', 'Unknown')}</div>" if view_mode == "manager" else ""
    
    return f"""
    <div style="display: flex; justify-content: space-between; align-items: flex-start; width: 100%; margin-bottom: 10px;">
        <div style="flex: 1; text-align: center; padding: 0 4px; width: 33%;">
            {lb_score_html}
            <div style="font-weight: bold; font-size: 15px; margin-top: 6px; line-height: 1.2;">{p.get('landb_player', 'TBD')}</div>
            {venue_html}
        </div>
        <div style="flex: 1; text-align: center; padding: 0 4px; width: 33%;">
            <div style="background-color: black; color: white; padding: 2px; font-size: 13px; border-radius: 3px; margin-bottom: 4px;">{hole_display}</div>
            <div style="background-color: {p_status_color}; color: white; padding: 2px; font-size: 11px; font-weight: bold; border-radius: 3px;">{p['status']}</div>
        </div>
        <div style="flex: 1; text-align: center; padding: 0 4px; width: 33%;">
            {opp_score_html}
            <div style="font-weight: bold; font-size: 15px; margin-top: 6px; line-height: 1.2;">{p.get('opposition_player', 'TBD')}</div>
        </div>
    </div>
    """

# --- LIST DEFINITIONS ---
HOLE_OPTIONS = [str(i) for i in range(1, 19)] + [f"Extra Hole {i}" for i in range(1, 10)]
SCORE_OPTIONS = ["All Square"] + [f"{i} Up" for i in range(1, 10)] + [f"{i} Down" for i in range(1, 10)]
VENUE_OPTIONS = ["Home", "Away"]
CATEGORY_OPTIONS = ["Men", "Ladies", "Mixed"]

# --- DATA FETCHING ---
@st.cache_data(ttl=10) # Refreshes cache every 10 seconds
def fetch_all():
    try:
        comps = supabase.table("competitions").select("*").execute().data
        pairings = supabase.table("pairings").select("*").execute().data
        return comps, pairings
    except:
        return [], []

comps, pairings = fetch_all()

# --- SECURE URL ROUTING ---
query_params = st.query_params
role = query_params.get("role", "public")

# --- VIEW 1: PUBLIC SCOREBOARD ---
if role == "public":
    st.markdown("""<div style="text-align: center;"><img src="app/static/lb_logo.png" width="120" onerror="this.style.display='none'"/><h2 style='font-weight: 700; margin-top: 5px;'>L&B Match Centre</h2></div>""", unsafe_allow_html=True)
    st.divider()
    
    if not comps:
        st.info("No active competitions.")
        st.stop()
        
    if st.button("↻ Refresh Scores", use_container_width=True): st.rerun()
    
    for comp in comps:
        comp_pairings = [p for p in pairings if p["competition_id"] == comp["id"]]
        comp_pairings = sorted(comp_pairings, key=lambda x: x['id'])
        
        lb, opp = calculate_overall_score(comp_pairings)
        status = get_comp_status(comp_pairings)
        
        st.markdown(f"<h3 style='text-align: center; font-weight: 700;'>{comp['category']} {comp['comp_name']}</h3>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align: center;'><span style='background-color: {'#8bc34a' if status=='LIVE' else 'gray'}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold;'>{status}</span></div>", unsafe_allow_html=True)
        
        st.markdown(generate_scoreboard_html(lb, opp, comp['opposition_team']), unsafe_allow_html=True)
        
        with st.expander(f"View Pairings (Last updated: {datetime.now(ireland_tz).strftime('%H:%M')})"):
            for p in comp_pairings:
                st.markdown(generate_pairing_html(p, "public"), unsafe_allow_html=True)
                st.write("---")
        st.divider()

# --- VIEW 2: MANAGER PORTAL ---
elif role == "manager":
    selected_comp_name = urllib.parse.unquote(query_params.get("comp", ""))
    comp = next((c for c in comps if f"{c['category']} {c['comp_name']}" == selected_comp_name), None)
    
    if comp:
        st.markdown(f"<h3 style='text-align: center; font-weight: 700;'>Manage: {selected_comp_name}</h3>", unsafe_allow_html=True)
        comp_pairings = sorted([p for p in pairings if p["competition_id"] == comp["id"]], key=lambda x: x['id'])
        
        lb, opp = calculate_overall_score(comp_pairings)
        status = get_comp_status(comp_pairings)
        
        st.markdown(f"<p style='text-align: center; margin-bottom: 5px;'>Live Score: L&B <b>{lb}</b> - <b>{opp}</b> {comp['opposition_team']}</p>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align: center; margin-bottom: 20px;'><span style='background-color: {'#8bc34a' if status=='LIVE' else 'gray'}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 12px;'>{status}</span></div>", unsafe_allow_html=True)
        st.divider()
        
        if not comp_pairings:
            st.info("No matches added to this competition yet.")
            
        for p in comp_pairings:
            st.markdown(generate_pairing_html(p, "manager"), unsafe_allow_html=True)
            
            with st.expander(f"Update: {p['landb_player']} vs {p['opposition_player']}", expanded=False):
                uc1, uc2 = st.columns(2)
                h = uc1.selectbox("Hole", HOLE_OPTIONS, index=safe_index(HOLE_OPTIONS, str(p['hole'])), key=f"h_{p['id']}")
                sc = uc2.selectbox("Score (Relative to L&B)", SCORE_OPTIONS, index=safe_index(SCORE_OPTIONS, p['score']), key=f"sc_{p['id']}")
                fin = st.checkbox("Match Finished (Check to lock final score)", value=(p['status'] == "FINISHED"), key=f"fin_{p['id']}")
                
                if st.button("Save Match Update", key=f"btn_{p['id']}", type="primary"):
                    new_leader = get_leader_from_score(sc)
                    supabase.table("pairings").update({
                        "hole": h, "score": sc, "status": "FINISHED" if fin else "LIVE", "leader": new_leader
                    }).eq("id", p['id']).execute()
                    st.success("Updated!"); time.sleep(1.5); st.rerun()
            st.divider()
    else:
        st.error("Invalid Manager Link. Competition not found.")

# --- VIEW 3: ADMIN CONSOLE ---
elif role == "admin":
    # Simple Session State Password Logic
    if "admin_auth" not in st.session_state:
        st.session_state.admin_auth = False

    if not st.session_state.admin_auth:
        st.markdown("<h2 style='text-align: center;'>Admin Login</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Enter Admin Password", type="password")
        if st.button("Login", use_container_width=True):
            correct_password = st.secrets.get("ADMIN_PASSWORD", "landb1909")
            if pwd == correct_password:
                st.session_state.admin_auth = True
                st.rerun()
            else:
                st.error("Incorrect password")
    else:
        st.header("Admin Console")
        if st.button("Logout of Admin"):
            st.session_state.admin_auth = False
            st.rerun()
            
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Create Comp", "Add Match", "Edit Comp", "Edit Match", "Access Links"])
        
        # TAB 1: CREATE COMPETITION
        with tab1:
            st.subheader("Create New Competition")
            with st.form("create_comp_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                new_category = col1.selectbox("Category", CATEGORY_OPTIONS)
                new_comp_name = col2.text_input("Competition Name (e.g., Junior Cup)")
                col3, col4 = st.columns(2)
                new_opp_team = col3.text_input("Opposition Team")
                new_start_time = col4.text_input("Start Time (Optional)")
                new_date = st.date_input("Match Date")
                
                if st.form_submit_button("Create Competition"):
                    if new_comp_name and new_opp_team:
                        supabase.table('competitions').insert({
                            "comp_name": new_comp_name, "category": new_category,
                            "opposition_team": new_opp_team, "match_date": str(new_date),
                            "start_time": new_start_time
                        }).execute()
                        st.success(f"Created {new_category} {new_comp_name}!"); time.sleep(1.5); st.rerun()
                    else:
                        st.error("Please fill out Name and Opposition.")
                        
        # TAB 2: ADD MATCH
        with tab2:
            st.subheader("Add Match to Competition")
            if comps:
                with st.form("create_pairing_form", clear_on_submit=True):
                    comp_names = {f"{c['category']} {c['comp_name']}": c['id'] for c in comps}
                    target_comp = st.selectbox("Select Competition", list(comp_names.keys()))
                    col1, col2 = st.columns(2)
                    lb_player_input = col1.text_input("L&B Player Name")
                    opp_player_input = col2.text_input("Opposition Player Name")
                    match_venue = st.selectbox("Venue", VENUE_OPTIONS)
                    
                    if st.form_submit_button("Add Match Pairing"):
                        if lb_player_input and opp_player_input:
                            supabase.table('pairings').insert({
                                "competition_id": comp_names[target_comp],
                                "landb_player": lb_player_input, "opposition_player": opp_player_input,
                                "venue": match_venue, "hole": "1", "score": "All Square",
                                "status": "Not Started", "leader": "Tied"
                            }).execute()
                            st.success("Match added!"); time.sleep(1.5); st.rerun()
                        else:
                            st.error("Please enter both player names.")
                            
        # TAB 3: EDIT COMP
        with tab3:
            st.subheader("Edit/Delete Competition")
            if comps:
                comp_names_dict = {f"{c['category']} {c['comp_name']}": c for c in comps}
                edit_comp_name = st.selectbox("Select Competition", list(comp_names_dict.keys()))
                c_data = comp_names_dict[edit_comp_name]
                
                with st.form("edit_comp_form"):
                    e_c1, e_c2 = st.columns(2)
                    e_cat = e_c1.selectbox("Category", CATEGORY_OPTIONS, index=safe_index(CATEGORY_OPTIONS, c_data['category']))
                    e_name = e_c2.text_input("Competition Name", value=c_data['comp_name'])
                    e_c3, e_c4 = st.columns(2)
                    e_opp = e_c3.text_input("Opposition Team", value=c_data['opposition_team'])
                    e_time = e_c4.text_input("Start Time", value=c_data.get('start_time', ''))
                    
                    if st.form_submit_button("Update Competition"):
                        supabase.table('competitions').update({
                            "comp_name": e_name, "category": e_cat, "opposition_team": e_opp, "start_time": e_time
                        }).eq('id', c_data['id']).execute()
                        st.success("Updated!"); time.sleep(1.5); st.rerun()
                        
                if st.button(f"🚨 Delete {edit_comp_name} 🚨", type="primary"):
                    supabase.table('competitions').delete().eq('id', c_data['id']).execute()
                    st.success("Deleted."); time.sleep(1.5); st.rerun()
                    
        # TAB 4: EDIT MATCH
        with tab4:
            st.subheader("Edit/Delete Match")
            if comps:
                comp_names_dict = {f"{c['category']} {c['comp_name']}": c['id'] for c in comps}
                t_comp = st.selectbox("Competition", list(comp_names_dict.keys()), key="edit_m_c")
                p_list = [p for p in pairings if p["competition_id"] == comp_names_dict[t_comp]]
                
                if p_list:
                    p_opts = {f"{p.get('landb_player')} vs {p.get('opposition_player')}": p for p in p_list}
                    sel_p = st.selectbox("Match to Edit", list(p_opts.keys()))
                    p_data = p_opts[sel_p]
                    
                    with st.form("edit_match_form"):
                        col1, col2 = st.columns(2)
                        e_lb = col1.text_input("L&B Player", value=p_data.get('landb_player', ''))
                        e_opp = col2.text_input("Opposition Player", value=p_data.get('opposition_player', ''))
                        if st.form_submit_button("Update Match"):
                            supabase.table('pairings').update({
                                "landb_player": e_lb, "opposition_player": e_opp
                            }).eq('id', p_data['id']).execute()
                            st.success("Updated!"); time.sleep(1.5); st.rerun()
                    if st.button("🚨 Delete Match 🚨", type="primary"):
                        supabase.table('pairings').delete().eq('id', p_data['id']).execute()
                        st.success("Deleted."); time.sleep(1.5); st.rerun()

        # TAB 5: ACCESS LINKS
        with tab5:
            st.subheader("System Access Links")
            st.write("Save these links or send them to your team managers.")
            
            st.markdown("**Admin Console Link** (Password Required):")
            st.code("/?role=admin", language="text")
            
            st.divider()
            st.markdown("**Manager Portal Links** (Locks user to specific competition):")
            for c in comps:
                safe_comp_name = urllib.parse.quote(f"{c['category']} {c['comp_name']}")
                st.markdown(f"**{c['category']} {c['comp_name']}**")
                st.code(f"/?role=manager&comp={safe_comp_name}", language="text")
