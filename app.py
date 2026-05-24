import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import time
from supabase import create_client
import urllib.parse

# --- CONFIGURATION ---
st.set_page_config(page_title="L&B Live Scoring", layout="centered", initial_sidebar_state="expanded")

# --- TIMEZONE SETUP ---
ireland_tz = ZoneInfo("Europe/Dublin")

# --- LIST DEFINITIONS ---
HOLE_OPTIONS = [str(i) for i in range(1, 19)] + [f"Extra Hole {i}" for i in range(1, 10)]
SCORE_OPTIONS = ["All Square"] + [f"{i} Up" for i in range(1, 10)] + [f"{i} Down" for i in range(1, 10)]
VENUE_OPTIONS = ["Home", "Away"]
CATEGORY_OPTIONS = ["Men", "Ladies", "Mixed"]

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
            category = comp.get("category", "Mixed")
            comp_name = comp["comp_name"]
            display_name = f"{category} {comp_name}"
            
            match_dict[display_name] = {
                "id": comp["id"],
                "raw_comp_name": comp_name,
                "date": comp["match_date"],
                "category": category,
                "start_time": comp.get("start_time", ""),
                "opposition_team": comp.get("opposition_team", "Unknown"),
                "status": comp.get("status", "Not Started"),
                "pairings": []
            }
            
            for pairing in all_pairings:
                if pairing["competition_id"] == comp["id"]:
                    match_dict[display_name]["pairings"].append(pairing)
            
            match_dict[display_name]["pairings"] = sorted(match_dict[display_name]["pairings"], key=lambda x: x['id'])
                    
        return match_dict
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return {}

matches_data = fetch_matches()

# --- HELPER FUNCTIONS ---
def calculate_overall_score(competition_name, data_source):
    """Calculates LIVE projected points (1 for lead, 0.5 for tie) for started matches."""
    lb_score = 0.0
    opp_score = 0.0
    
    if competition_name not in data_source:
        return lb_score, opp_score

    for pairing in data_source[competition_name]["pairings"]:
        if pairing["status"] in ["LIVE", "FINISHED"]:
            if pairing["leader"] == "L&B":
                lb_score += 1.0
            elif pairing["leader"] == "Opposition":
                opp_score += 1.0
            else: 
                lb_score += 0.5
                opp_score += 0.5
    return lb_score, opp_score

def get_leader_from_score(score_string):
    if "Up" in score_string: return "L&B"
    elif "Down" in score_string: return "Opposition"
    return "Tied"

def safe_index(options_list, value, default=0):
    return options_list.index(value) if value in options_list else default

# --- ROUTING & NAVIGATION ---
query_params = st.query_params
url_role = query_params.get("role", None)
url_comp = query_params.get("comp", None)

has_comps = len(matches_data) > 0

if url_role == "manager" and url_comp in matches_data:
    st.sidebar.success(f"Manager Access Granted")
    st.sidebar.info(f"You are managing:\n**{url_comp}**")
    view = "Manager Portal"
    selected_comp = url_comp
else:
    st.sidebar.title("Navigation")
    view = st.sidebar.radio("Mode", ["Public Scoreboard", "Manager Portal", "Admin Console"])
    if view == "Manager Portal" and has_comps:
        selected_comp = st.sidebar.selectbox("Select Competition to Manage", list(matches_data.keys()))
    else:
        selected_comp = None

# --- VIEW 1: PUBLIC SCOREBOARD (Read Only) ---
if view == "Public Scoreboard":
    st.markdown("<h2 style='text-align: center;'>L&B Match Centre</h2>", unsafe_allow_html=True)
    st.divider()
    
    if not has_comps:
        st.info("No active competitions.")
        st.stop()
        
    if st.button("↻ Refresh All Scores", use_container_width=True):
        st.rerun()
        
    for comp_name, data in matches_data.items():
        lb_score, opp_score = calculate_overall_score(comp_name, matches_data)
        
        # Clean up the category name for display
        display_category = "Mens" if data['category'] == "Men" else data['category']
        full_title = f"{display_category} {data['raw_comp_name']}".strip()
        
        st.markdown(f"<h3 style='text-align: center; margin-bottom: 25px;'>{full_title}</h3>", unsafe_allow_html=True)
        
        col1, col2, col3, col4, col5 = st.columns([1, 4, 1, 4, 1])
        with col2:
            st.write("<div style='text-align: center;'><b>L&B</b></div>", unsafe_allow_html=True)
            st.markdown(f"<div style='background-color: darkblue; color: white; padding: 15px; font-size: 24px; text-align: center; border-radius: 5px;'><b>{lb_score}</b></div>", unsafe_allow_html=True)
        with col3:
            # Replaced header tag with a perfectly centered div
            st.markdown("<div style='text-align: center; font-size: 40px; font-weight: bold; padding-top: 22px;'>:</div>", unsafe_allow_html=True)
        with col4:
            st.write(f"<div style='text-align: center;'><b>{data['opposition_team']}</b></div>", unsafe_allow_html=True)
            st.markdown(f"<div style='background-color: darkred; color: white; padding: 15px; font-size: 24px; text-align: center; border-radius: 5px;'><b>{opp_score}</b></div>", unsafe_allow_html=True)
        
        st.write("&nbsp;") 
        
        current_time_str = datetime.now(ireland_tz).strftime('%H:%M')
        with st.expander(f"View Pairings (Last updated: {current_time_str})"):
            if not data["pairings"]:
                st.write("Pairings to be announced.")
            else:
                for pairing in data["pairings"]:
                    pc1, pc2, pc3 = st.columns([1, 1, 1])
                    with pc1:
                        st.write(f"**{pairing.get('landb_player', 'TBD')}**")
                        if pairing['leader'] == 'L&B':
                            st.markdown(f"<div style='background-color: darkblue; color: white; text-align: center; padding: 3px;'>{pairing['score']}</div>", unsafe_allow_html=True)
                        elif pairing['leader'] == 'Tied':
                            st.markdown(f"<div style='background-color: gray; color: white; text-align: center; padding: 3px;'>ALL SQUARE</div>", unsafe_allow_html=True)
                    with pc2:
                        hole_val = str(pairing.get('hole', '1'))
                        hole_display = f"Hole {hole_val}" if hole_val.isdigit() else hole_val 
                        st.markdown(f"<div style='background-color: black; color: white; text-align: center; padding: 2px; margin-top: 5px;'>{hole_display}</div>", unsafe_allow_html=True)
                        status_color = "gray" if pairing['status'] == "Not Started" else ("darkred" if pairing['status'] == "FINISHED" else "#8bc34a")
                        st.markdown(f"<div style='background-color: {status_color}; color: white; text-align: center; padding: 2px;'>{pairing['status']}</div>", unsafe_allow_html=True)
                    with pc3:
                         st.write(f"**{pairing.get('opposition_player', 'TBD')}**")
                         if pairing['leader'] == 'Opposition':
                            display_score = pairing['score'].replace("Down", "Up") 
                            st.markdown(f"<div style='background-color: darkred; color: white; text-align: center; padding: 3px;'>{display_score}</div>", unsafe_allow_html=True)
                         elif pairing['leader'] == 'Tied':
                            st.markdown(f"<div style='background-color: gray; color: white; text-align: center; padding: 3px;'>ALL SQUARE</div>", unsafe_allow_html=True)
                    st.write("---")
        st.divider()

# --- VIEW 2: MANAGER PORTAL (Live Scoring Updates) ---
elif view == "Manager Portal":
    if not has_comps:
        st.warning("No competitions available.")
        st.stop()
        
    data = matches_data[selected_comp]
    lb_score, opp_score = calculate_overall_score(selected_comp, matches_data)

    st.markdown(f"<h3 style='text-align: center;'>Manage: {selected_comp}</h3>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center;'>Live Score: L&B <b>{lb_score}</b> - <b>{opp_score}</b> {data['opposition_team']}</p>", unsafe_allow_html=True)
    st.divider()
    
    if not data["pairings"]:
        st.info("No matches added to this competition yet.")
        
    for i, pairing in enumerate(data["pairings"]):
        pc1, pc2, pc3 = st.columns([1, 1, 1])
        
        with pc1:
            st.write(f"**{pairing.get('landb_player', 'TBD')}**")
            st.caption(f"📍 {pairing.get('venue', 'Unknown')}")
            if pairing['leader'] == 'L&B':
                st.markdown(f"<div style='background-color: darkblue; color: white; text-align: center; padding: 5px;'>{pairing['score']}</div>", unsafe_allow_html=True)
            elif pairing['leader'] == 'Tied':
                st.markdown(f"<div style='background-color: gray; color: white; text-align: center; padding: 5px;'>ALL SQUARE</div>", unsafe_allow_html=True)
        
        with pc2:
            st.write("&nbsp;")
            hole_val = str(pairing.get('hole', '1'))
            hole_display = f"Hole {hole_val}" if hole_val.isdigit() else hole_val 
            st.markdown(f"<div style='background-color: black; color: white; text-align: center; padding: 2px;'>{hole_display}</div>", unsafe_allow_html=True)
            status_color = "gray" if pairing['status'] == "Not Started" else ("darkred" if pairing['status'] == "FINISHED" else "#8bc34a")
            st.markdown(f"<div style='background-color: {status_color}; color: white; text-align: center; padding: 2px;'>{pairing['status']}</div>", unsafe_allow_html=True)
            
        with pc3:
             st.write(f"**{pairing.get('opposition_player', 'TBD')}**")
             st.caption("&nbsp;") 
             if pairing['leader'] == 'Opposition':
                display_score = pairing['score'].replace("Down", "Up") 
                st.markdown(f"<div style='background-color: darkred; color: white; text-align: center; padding: 5px;'>{display_score}</div>", unsafe_allow_html=True)
             elif pairing['leader'] == 'Tied':
                st.markdown(f"<div style='background-color: gray; color: white; text-align: center; padding: 5px;'>ALL SQUARE</div>", unsafe_allow_html=True)

        with st.expander(f"Update: {pairing.get('landb_player')} vs {pairing.get('opposition_player')}", expanded=False):
            uc1, uc2 = st.columns(2)
            
            current_hole = str(pairing.get('hole', '1'))
            current_score = str(pairing.get('score', 'All Square'))
            
            new_hole = uc1.selectbox("Hole", HOLE_OPTIONS, index=safe_index(HOLE_OPTIONS, current_hole), key=f"hole_{pairing['id']}")
            new_score = uc2.selectbox("Score (Relative to L&B)", SCORE_OPTIONS, index=safe_index(SCORE_OPTIONS, current_score), key=f"score_{pairing['id']}")
            
            is_finished = st.checkbox("Match Finished (Check to lock final score)", value=(pairing['status'] == "FINISHED"), key=f"fin_{pairing['id']}")
            
            if st.button("Save Update", key=f"btn_{pairing['id']}", type="primary"):
                new_leader = get_leader_from_score(new_score)
                auto_status = "FINISHED" if is_finished else "LIVE" 
                try:
                    supabase.table('pairings').update({
                        'hole': new_hole,
                        'score': new_score,
                        'status': auto_status,
                        'leader': new_leader
                    }).eq('id', pairing['id']).execute()
                    
                    if data['status'] == "Not Started":
                         supabase.table('competitions').update({'status': 'LIVE'}).eq('id', data['id']).execute()
                         
                    st.success("Match updated!")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Database Error: {e}")
        st.divider()

# --- VIEW 3: ADMIN CONSOLE (Create & Manage) ---
elif view == "Admin Console":
    st.header("Admin Console")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Create Comp", "Add Match", "Edit Comp", "Edit Match", "Manager Links"])
    
    # --- TAB 1: CREATE COMPETITION ---
    with tab1:
        st.subheader("Create New Competition")
        with st.form("create_comp_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            new_category = col1.selectbox("Category", CATEGORY_OPTIONS)
            new_comp_name = col2.text_input("Competition Name (e.g., Junior Cup)")
            
            col3, col4 = st.columns(2)
            new_opp_team = col3.text_input("Opposition Team")
            new_start_time = col4.text_input("Start Time (Optional, e.g., 3:00 PM)")
            
            new_date = st.date_input("Match Date")
            
            if st.form_submit_button("Create Competition"):
                if new_comp_name and new_opp_team:
                    try:
                        supabase.table('competitions').insert({
                            "comp_name": new_comp_name,
                            "category": new_category,
                            "opposition_team": new_opp_team,
                            "match_date": str(new_date),
                            "start_time": new_start_time,
                            "status": "Not Started"
                        }).execute()
                        st.success(f"Created {new_category} {new_comp_name}!")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Database Error: {e}")
                else:
                    st.error("Please fill out the Competition Name and Opposition Team.")
                    
    # --- TAB 2: ADD MATCH ---
    with tab2:
        st.subheader("Add Match to Competition")
        if not has_comps:
            st.info("Create a competition first.")
        else:
            with st.form("create_pairing_form", clear_on_submit=True):
                comp_options = {name: data['id'] for name, data in matches_data.items()}
                target_comp = st.selectbox("Select Competition", list(comp_options.keys()))
                default_opp_name = matches_data[target_comp]["opposition_team"] if target_comp else ""
                
                col1, col2 = st.columns(2)
                lb_player_input = col1.text_input("L&B Player Name")
                opp_player_input = col2.text_input("Opposition Player Name", value=default_opp_name)
                
                match_venue = st.selectbox("Venue", VENUE_OPTIONS)
                
                if st.form_submit_button("Add Match Pairing"):
                    if lb_player_input and opp_player_input:
                        try:
                            supabase.table('pairings').insert({
                                "competition_id": comp_options[target_comp],
                                "landb_player": lb_player_input,
                                "opposition_player": opp_player_input,
                                "venue": match_venue,
                                "hole": "1",
                                "score": "All Square",
                                "status": "Not Started",
                                "leader": "Tied"
                            }).execute()
                            st.success("Match added!")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database Error: {e}")
                    else:
                        st.error("Please enter both player names.")

    # --- TAB 3: EDIT COMPETITION ---
    with tab3:
        st.subheader("Edit/Delete Competition")
        if not has_comps:
            st.info("No competitions available.")
        else:
            edit_comp_name = st.selectbox("Select Competition to Edit", list(matches_data.keys()), key="edit_comp_select")
            comp_data = matches_data[edit_comp_name]
            
            with st.form("edit_comp_form"):
                e_col1, e_col2 = st.columns(2)
                e_category = e_col1.selectbox("Category", CATEGORY_OPTIONS, index=safe_index(CATEGORY_OPTIONS, comp_data.get('category', 'Men')))
                e_comp_name_input = e_col2.text_input("Competition Name", value=comp_data['raw_comp_name'])
                
                e_col3, e_col4 = st.columns(2)
                e_opp_team = e_col3.text_input("Opposition Team", value=comp_data['opposition_team'])
                e_start_time = e_col4.text_input("Start Time", value=comp_data.get('start_time', ''))
                
                e_status = st.selectbox("Overall Status Override", ["Not Started", "LIVE", "FINISHED"], index=["Not Started", "LIVE", "FINISHED"].index(comp_data.get('status', 'Not Started')))
                
                e_date = st.date_input("Match Date", value=datetime.strptime(comp_data['date'], "%Y-%m-%d").date() if comp_data['date'] else datetime.now(ireland_tz).date())
                
                if st.form_submit_button("Update Competition"):
                    try:
                        supabase.table('competitions').update({
                            "comp_name": e_comp_name_input,
                            "category": e_category,
                            "opposition_team": e_opp_team,
                            "start_time": e_start_time,
                            "status": e_status,
                            "match_date": str(e_date)
                        }).eq('id', comp_data['id']).execute()
                        st.success("Competition Updated!")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Database Error: {e}")

            st.divider()
            if st.checkbox(f"I want to permanently delete {edit_comp_name}", key="del_comp_check"):
                if st.button("🚨 Delete Competition 🚨", type="primary"):
                    try:
                        supabase.table('competitions').delete().eq('id', comp_data['id']).execute()
                        st.success("Competition deleted.")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}. You may need to delete all matches in this competition first.")

    # --- TAB 4: EDIT MATCH ---
    with tab4:
        st.subheader("Edit/Delete Match")
        if not has_comps:
            st.info("No competitions available.")
        else:
            target_comp_for_match = st.selectbox("Select Competition", list(matches_data.keys()), key="edit_match_comp_select")
            pairings_list = matches_data[target_comp_for_match]["pairings"]
            
            if not pairings_list:
                st.info("No matches in this competition.")
            else:
                pairing_options = {f"{p.get('landb_player')} vs {p.get('opposition_player')}": p for p in pairings_list}
                selected_pairing_str = st.selectbox("Select Match to Edit", list(pairing_options.keys()))
                p_data = pairing_options[selected_pairing_str]
                
                with st.form("edit_match_form"):
                    col1, col2 = st.columns(2)
                    e_lb_player = col1.text_input("L&B Player", value=p_data.get('landb_player', ''))
                    e_opp_player = col2.text_input("Opposition Player", value=p_data.get('opposition_player', ''))
                    
                    e_venue = st.selectbox("Venue", VENUE_OPTIONS, index=safe_index(VENUE_OPTIONS, p_data.get('venue', 'Home')))
                    
                    if st.form_submit_button("Update Match Details"):
                        try:
                            supabase.table('pairings').update({
                                "landb_player": e_lb_player,
                                "opposition_player": e_opp_player,
                                "venue": e_venue
                            }).eq('id', p_data['id']).execute()
                            st.success("Match Updated!")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database Error: {e}")
                            
                st.divider()
                if st.checkbox(f"I want to permanently delete {selected_pairing_str}", key="del_match_check"):
                    if st.button("🚨 Delete Match 🚨", type="primary"):
                        try:
                            supabase.table('pairings').delete().eq('id', p_data['id']).execute()
                            st.success("Match deleted.")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database Error: {e}")

    # --- TAB 5: MANAGER LINKS ---
    with tab5:
        st.subheader("Distribute Manager Links")
        st.write("Send these links to your team managers. When they click the link, the app will lock them into their specific competition with no admin controls.")
        
        st.info("**Instructions:** Copy the text block below and add it to the very end of your main Streamlit App URL.")
        
        for comp_name in matches_data.keys():
            safe_comp_name = urllib.parse.quote(comp_name)
            link_extension = f"/?role=manager&comp={safe_comp_name}"
            
            st.markdown(f"**{comp_name}**")
            st.code(link_extension, language="text")
