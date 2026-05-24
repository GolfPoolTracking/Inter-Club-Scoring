import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client

# --- CONFIGURATION ---
st.set_page_config(page_title="L&B Live Scoring", layout="centered")

# --- LIST DEFINITIONS ---
HOLE_OPTIONS = [str(i) for i in range(1, 19)] + [f"Extra Hole {i}" for i in range(1, 10)]
SCORE_OPTIONS = ["All Square"] + [f"{i} Up" for i in range(1, 10)] + [f"{i} Down" for i in range(1, 10)]
STATUS_OPTIONS = ["Not Started", "LIVE", "FINISHED"]
VENUE_OPTIONS = ["Home", "Away"]

# --- DATABASE CONNECTION ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- FETCH LIVE DATA ---
def fetch_matches():
    try:
        comp_response = supabase.table("competitions").select("*").execute()
        competitions = comp_response.data

        pairings_response = supabase.table("pairings").select("*").execute()
        all_pairings = pairings_response.data

        match_dict = {}
        for comp in competitions:
            comp_name = comp["comp_name"]
            match_dict[comp_name] = {
                "id": comp["id"],
                "date": comp["match_date"],
                "opposition_team": comp.get("opposition_team", "Unknown"),
                "status": comp.get("status", "Not Started"),
                "pairings": []
            }
            
            for pairing in all_pairings:
                if pairing["competition_id"] == comp["id"]:
                    match_dict[comp_name]["pairings"].append(pairing)
            
            match_dict[comp_name]["pairings"] = sorted(match_dict[comp_name]["pairings"], key=lambda x: x['id'])
                    
        return match_dict
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return {}

matches_data = fetch_matches()

# --- HELPER FUNCTIONS ---
def calculate_overall_score(competition_name, data_source):
    lb_score = 0.0
    opp_score = 0.0
    
    if competition_name not in data_source:
        return lb_score, opp_score

    for pairing in data_source[competition_name]["pairings"]:
        if pairing["status"] == "FINISHED":
            if pairing["leader"] == "L&B":
                lb_score += 1
            elif pairing["leader"] == "Opposition":
                opp_score += 1
            else:
                lb_score += 0.5
                opp_score += 0.5
    return lb_score, opp_score

def get_leader_from_score(score_string):
    if "Up" in score_string:
        return "L&B"
    elif "Down" in score_string:
        return "Opposition"
    return "Tied"

def safe_index(options_list, value, default=0):
    """Safely find the index of a value in a list, return default if not found."""
    return options_list.index(value) if value in options_list else default

# --- UI NAVIGATION ---
st.sidebar.title("Navigation")
view = st.sidebar.radio("Go to", ["Match Overview", "Live Scoring (Admin)", "Create & Manage"])

# Determine if we have competitions to select
has_comps = len(matches_data) > 0
if has_comps:
    selected_comp = st.sidebar.selectbox("Select Competition", list(matches_data.keys()))
else:
    selected_comp = None

# --- VIEW 1: MATCH OVERVIEW ---
if view == "Match Overview":
    if not has_comps:
        st.info("No competitions created yet. Go to 'Create & Manage' to start.")
        st.stop()
        
    data = matches_data[selected_comp]
    lb_score, opp_score = calculate_overall_score(selected_comp, matches_data)
    
    st.markdown(f"<h2 style='text-align: center;'>{selected_comp}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center;'>Laytown & Bettystown vs {data['opposition_team']}<br>{data['date']}</p>", unsafe_allow_html=True)
    
    # Competition Status Badge
    status_colors = {"Not Started": "gray", "LIVE": "#8bc34a", "FINISHED": "darkred"}
    comp_color = status_colors.get(data['status'], "gray")
    st.markdown(f"<div style='text-align: center; margin-bottom: 20px;'><span style='background-color: {comp_color}; color: white; padding: 5px 15px; border-radius: 3px;'>{data['status']}</span></div>", unsafe_allow_html=True)
    
    st.markdown("<h4 style='text-align: center;'>Overall Score</h4>", unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns([1, 2, 1, 2, 1])
    with col2:
        st.write("<div style='text-align: center;'><b>L&B</b></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background-color: darkblue; color: white; padding: 15px; font-size: 24px; text-align: center; border-radius: 5px;'><b>{lb_score}</b></div>", unsafe_allow_html=True)
    with col3:
        st.markdown("<h2 style='text-align: center; padding-top:20px;'>:</h2>", unsafe_allow_html=True)
    with col4:
        st.write(f"<div style='text-align: center;'><b>{data['opposition_team']}</b></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background-color: darkred; color: white; padding: 15px; font-size: 24px; text-align: center; border-radius: 5px;'><b>{opp_score}</b></div>", unsafe_allow_html=True)
        
    st.markdown(f"<p style='text-align: center; font-size: 12px; color: gray; margin-top:20px;'>Last updated: {datetime.now().strftime('%H:%M:%S')}</p>", unsafe_allow_html=True)
    
    if st.button("↻ Refresh Scores"):
        st.rerun()

# --- VIEW 2: LIVE SCORING ADMIN ---
elif view == "Live Scoring (Admin)":
    if not has_comps:
        st.warning("No competitions available.")
        st.stop()
        
    data = matches_data[selected_comp]
    lb_score, opp_score = calculate_overall_score(selected_comp, matches_data)
    
    # Competition Level Admin
    with st.expander("⚙️ Edit Competition Status", expanded=False):
        new_comp_status = st.selectbox("Overall Status", STATUS_OPTIONS, index=safe_index(STATUS_OPTIONS, data['status']))
        if st.button("Update Comp Status"):
            supabase.table('competitions').update({'status': new_comp_status}).eq('id', data['id']).execute()
            st.success("Competition updated!")
            st.rerun()

    st.markdown(f"<h3 style='text-align: center;'>{selected_comp}</h3>", unsafe_allow_html=True)
    st.divider()
    
    if not data["pairings"]:
        st.info("No matches added to this competition yet.")
        
    # Individual Matches
    for i, pairing in enumerate(data["pairings"]):
        pc1, pc2, pc3 = st.columns([1, 1, 1])
        
        # Player 1 Col (L&B)
        with pc1:
            st.write(f"**{pairing.get('landb_player', 'TBD')}**")
            st.caption(f"📍 {pairing.get('venue', 'Unknown')}")
            if pairing['leader'] == 'L&B':
                st.markdown(f"<div style='background-color: darkblue; color: white; text-align: center; padding: 5px;'>{pairing['score']}</div>", unsafe_allow_html=True)
            elif pairing['leader'] == 'Tied':
                st.markdown(f"<div style='background-color: gray; color: white; text-align: center; padding: 5px;'>ALL SQUARE</div>", unsafe_allow_html=True)
        
        # Center Status Col
        with pc2:
            st.markdown(f"<div style='text-align: center; font-size:12px;'>Start: {pairing.get('start_time', 'TBD')}</div>", unsafe_allow_html=True)
            
            hole_val = str(pairing.get('hole', '1'))
            if hole_val.isdigit():
                hole_display = f"Hole {hole_val}"
            else:
                hole_display = hole_val # For "Extra Hole X"
                
            st.markdown(f"<div style='background-color: black; color: white; text-align: center; padding: 2px;'>{hole_display}</div>", unsafe_allow_html=True)
            
            status_color = "gray" if pairing['status'] == "Not Started" else ("darkred" if pairing['status'] == "FINISHED" else "#8bc34a")
            st.markdown(f"<div style='background-color: {status_color}; color: white; text-align: center; padding: 2px;'>{pairing['status']}</div>", unsafe_allow_html=True)
            
        # Player 2 Col (Opposition)
        with pc3:
             st.write(f"**{pairing.get('opposition_player', 'TBD')}**")
             st.caption("&nbsp;") # Spacing alignment
             if pairing['leader'] == 'Opposition':
                # Convert "Down" to "Up" visually for the opposition side
                display_score = pairing['score'].replace("Down", "Up") 
                st.markdown(f"<div style='background-color: darkred; color: white; text-align: center; padding: 5px;'>{display_score}</div>", unsafe_allow_html=True)
             elif pairing['leader'] == 'Tied':
                st.markdown(f"<div style='background-color: gray; color: white; text-align: center; padding: 5px;'>ALL SQUARE</div>", unsafe_allow_html=True)

        # Admin Controls for Pairing
        with st.expander(f"Update Match: {pairing.get('landb_player')} vs {pairing.get('opposition_player')}"):
            uc1, uc2, uc3 = st.columns(3)
            
            current_hole = str(pairing.get('hole', '1'))
            current_score = str(pairing.get('score', 'All Square'))
            current_status = str(pairing.get('status', 'Not Started'))
            
            new_hole = uc1.selectbox("Hole", HOLE_OPTIONS, index=safe_index(HOLE_OPTIONS, current_hole), key=f"hole_{pairing['id']}")
            new_score = uc2.selectbox("Score (Relative to L&B)", SCORE_OPTIONS, index=safe_index(SCORE_OPTIONS, current_score), key=f"score_{pairing['id']}")
            new_status = uc3.selectbox("Status", STATUS_OPTIONS, index=safe_index(STATUS_OPTIONS, current_status), key=f"status_{pairing['id']}")
            
            if st.button("Save Update", key=f"btn_{pairing['id']}"):
                new_leader = get_leader_from_score(new_score)
                try:
                    supabase.table('pairings').update({
                        'hole': new_hole,
                        'score': new_score,
                        'status': new_status,
                        'leader': new_leader
                    }).eq('id', pairing['id']).execute()
                    st.success("Match updated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")
        
        st.divider()

# --- VIEW 3: CREATE & MANAGE ---
elif view == "Create & Manage":
    st.header("Database Management")
    
    st.subheader("1. Create New Competition")
    with st.form("create_comp_form", clear_on_submit=True):
        new_comp_name = st.text_input("Competition Name (e.g., Junior Cup)")
        new_opp_team = st.text_input("Opposition Team")
        new_date = st.date_input("Match Date")
        
        if st.form_submit_button("Create Competition"):
            if new_comp_name and new_opp_team:
                supabase.table('competitions').insert({
                    "comp_name": new_comp_name,
                    "opposition_team": new_opp_team,
                    "match_date": str(new_date),
                    "status": "Not Started"
                }).execute()
                st.success(f"Created {new_comp_name}!")
                st.rerun()
            else:
                st.error("Please fill out all fields.")
                
    st.divider()
    
    st.subheader("2. Add Match to Competition")
    if not has_comps:
        st.info("Create a competition first.")
    else:
        with st.form("create_pairing_form", clear_on_submit=True):
            # We map comp names to their IDs for the database insert
            comp_options = {name: data['id'] for name, data in matches_data.items()}
            target_comp = st.selectbox("Select Competition", list(comp_options.keys()))
            
            # --- NEW LOGIC: Get the opposition team name for the default value ---
            default_opp_name = matches_data[target_comp]["opposition_team"] if target_comp else ""
            
            col1, col2 = st.columns(2)
            lb_player_input = col1.text_input("L&B Player Name")
            
            # --- NEW LOGIC: Inject the default value into the text box ---
            opp_player_input = col2.text_input("Opposition Player Name", value=default_opp_name)
            
            col3, col4 = st.columns(2)
            match_venue = col3.selectbox("Venue", VENUE_OPTIONS)
            match_time = col4.text_input("Start Time (e.g., 09:30)")
            
            if st.form_submit_button("Add Match Pairing"):
                if lb_player_input and opp_player_input:
                    supabase.table('pairings').insert({
                        "competition_id": comp_options[target_comp],
                        "landb_player": lb_player_input,
                        "opposition_player": opp_player_input,
                        "venue": match_venue,
                        "start_time": match_time,
                        "hole": "1",
                        "score": "All Square",
                        "status": "Not Started",
                        "leader": "Tied"
                    }).execute()
                    st.success("Match added!")
                    st.rerun()
                else:
                    st.error("Please enter both player names.")
