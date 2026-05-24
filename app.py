import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client

# --- CONFIGURATION ---
st.set_page_config(page_title="L&B Live Scoring", layout="centered")

# --- DATABASE CONNECTION ---
@st.cache_resource
def init_connection():
    """Initializes the connection to Supabase using secrets."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- FETCH LIVE DATA ---
def fetch_matches():
    """Fetches all competitions and pairings from Supabase."""
    try:
        # 1. Get all competitions
        comp_response = supabase.table("competitions").select("*").execute()
        competitions = comp_response.data

        # 2. Get all pairings
        pairings_response = supabase.table("pairings").select("*").execute()
        all_pairings = pairings_response.data

        # 3. Organize into a dictionary for the UI
        match_dict = {}
        for comp in competitions:
            comp_name = comp["comp_name"]
            match_dict[comp_name] = {
                "id": comp["id"],
                "date": comp["match_date"],
                "home_team": comp["home_team"],
                "away_team": comp["away_team"],
                "pairings": []
            }
            
            # Add the relevant pairings to this competition
            for pairing in all_pairings:
                if pairing["competition_id"] == comp["id"]:
                    # Sort by pairing ID so they stay in consistent order (Match 1, Match 2, etc.)
                    match_dict[comp_name]["pairings"].append(pairing)
            
            # Sort the pairings list to ensure consistent display order
            match_dict[comp_name]["pairings"] = sorted(match_dict[comp_name]["pairings"], key=lambda x: x['id'])
                    
        return match_dict
    except Exception as e:
        st.error(f"Error fetching data from database: {e}")
        return {}

# Load the fresh data every time the page refreshes
matches_data = fetch_matches()

# --- HELPER FUNCTIONS ---
def calculate_overall_score(competition_name, data_source):
    """Calculates the overall match score based on individual pairings."""
    home_score = 0.0
    away_score = 0.0
    
    if competition_name not in data_source:
        return home_score, away_score

    for pairing in data_source[competition_name]["pairings"]:
        if pairing["status"] == "FINISHED":
            if pairing["leader"] == "home":
                home_score += 1
            elif pairing["leader"] == "away":
                away_score += 1
            else:
                home_score += 0.5
                away_score += 0.5
    return home_score, away_score

def update_score(pairing_id, new_hole, new_score, new_status, new_leader):
    """Pushes updates directly to the Supabase database."""
    try:
        supabase.table('pairings').update({
            'hole': new_hole,
            'score': new_score,
            'status': new_status,
            'leader': new_leader
        }).eq('id', pairing_id).execute()
        st.success("Score updated successfully!")
    except Exception as e:
        st.error(f"Failed to update database: {e}")

# --- UI NAVIGATION ---
st.sidebar.title("Navigation")
view = st.sidebar.radio("Go to", ["Competitions", "Match Overview", "Live Scoring (Admin)"])

# Only show the selectbox if there is data available
if not matches_data:
    st.warning("No competitions found in the database. Please add data to Supabase.")
    st.stop()

selected_comp = st.sidebar.selectbox("Select Competition", list(matches_data.keys()))

# --- VIEW 1: COMPETITION LIST ---
if view == "Competitions":
    st.header("Select Competition")
    
    for comp, data in matches_data.items():
        home_score, away_score = calculate_overall_score(comp, matches_data)
        
        with st.container():
            st.subheader(comp)
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**LIVE:**\n{data['home_team']} vs {data['away_team']}")
            with col2:
                st.markdown(f"<div style='background-color: darkred; color: white; padding: 10px; text-align: center; border-radius: 5px;'>{home_score}</div>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<div style='background-color: darkblue; color: white; padding: 10px; text-align: center; border-radius: 5px;'>{away_score}</div>", unsafe_allow_html=True)
            st.divider()

# --- VIEW 2: MATCH OVERVIEW ---
elif view == "Match Overview":
    data = matches_data[selected_comp]
    home_score, away_score = calculate_overall_score(selected_comp, matches_data)
    
    st.markdown(f"<h2 style='text-align: center;'>{selected_comp}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center;'>{data['home_team']} vs {data['away_team']}<br>{data['date']}</p>", unsafe_allow_html=True)
    
    st.markdown("<h4 style='text-align: center;'>Score</h4>", unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns([1, 2, 1, 2, 1])
    with col2:
        st.markdown(f"<div style='background-color: darkred; color: white; padding: 15px; font-size: 24px; text-align: center; border-radius: 5px;'><b>{home_score}</b></div>", unsafe_allow_html=True)
    with col3:
        st.markdown("<h2 style='text-align: center;'>:</h2>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div style='background-color: darkblue; color: white; padding: 15px; font-size: 24px; text-align: center; border-radius: 5px;'><b>{away_score}</b></div>", unsafe_allow_html=True)
        
    st.markdown("<br><div style='text-align: center;'><span style='background-color: #8bc34a; color: white; padding: 5px 15px; border-radius: 3px;'>LIVE</span></div>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; font-size: 12px; color: gray;'>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>", unsafe_allow_html=True)
    
    if st.button("↻ Refresh Scores"):
        st.rerun()

# --- VIEW 3: LIVE SCORING ADMIN ---
elif view == "Live Scoring (Admin)":
    data = matches_data[selected_comp]
    home_score, away_score = calculate_overall_score(selected_comp, matches_data)
    
    st.markdown(f"<h3 style='text-align: center;'>{selected_comp}</h3>", unsafe_allow_html=True)
    
    # Top Score Header
    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
    col1.write(f"<div style='text-align: right; padding-top:10px;'>{data['home_team']}</div>", unsafe_allow_html=True)
    col2.markdown(f"<div style='background-color: darkred; color: white; padding: 10px; text-align: center; border-radius: 5px;'>{home_score}</div>", unsafe_allow_html=True)
    col3.markdown(f"<div style='background-color: darkblue; color: white; padding: 10px; text-align: center; border-radius: 5px;'>{away_score}</div>", unsafe_allow_html=True)
    col4.write(f"<div style='text-align: left; padding-top:10px;'>{data['away_team']}</div>", unsafe_allow_html=True)
    st.divider()
    
    if not data["pairings"]:
        st.info("No pairings found for this competition.")
        
    # Individual Matches
    for i, pairing in enumerate(data["pairings"]):
        pc1, pc2, pc3 = st.columns([1, 1, 1])
        
        # Player 1 Col (Home)
        with pc1:
            st.write(f"**{pairing['home_player']}**")
            if pairing['leader'] == 'home':
                st.markdown(f"<div style='background-color: darkred; color: white; text-align: center; padding: 5px;'>{pairing['score']}</div>", unsafe_allow_html=True)
            elif pairing['leader'] == 'tied':
                st.markdown(f"<div style='background-color: black; color: white; text-align: center; padding: 5px;'>ALL SQUARE</div>", unsafe_allow_html=True)
        
        # Center Status Col
        with pc2:
            st.markdown(f"<div style='background-color: black; color: white; text-align: center; padding: 2px;'>Hole {pairing['hole']}</div>", unsafe_allow_html=True)
            status_color = "red" if pairing['status'] == "FINISHED" else "#8bc34a"
            st.markdown(f"<div style='background-color: {status_color}; color: white; text-align: center; padding: 2px;'>{pairing['status']}</div>", unsafe_allow_html=True)
            
        # Player 2 Col (Away)
        with pc3:
             st.write(f"**{pairing['away_player']}**")
             if pairing['leader'] == 'away':
                st.markdown(f"<div style='background-color: darkblue; color: white; text-align: center; padding: 5px;'>{pairing['score']}</div>", unsafe_allow_html=True)
             elif pairing['leader'] == 'tied':
                st.markdown(f"<div style='background-color: black; color: white; text-align: center; padding: 5px;'>ALL SQUARE</div>", unsafe_allow_html=True)

        # Admin Controls
        with st.expander(f"Update Match {i+1}"):
            uc1, uc2, uc3 = st.columns(3)
            # Use safe defaults to avoid KeyErrors if data is malformed
            current_hole = int(pairing.get('hole', 1))
            current_score = str(pairing.get('score', 'ALL SQUARE'))
            current_status = str(pairing.get('status', 'LIVE'))
            current_leader = str(pairing.get('leader', 'tied'))
            
            new_hole = uc1.number_input("Hole", min_value=1, max_value=19, value=current_hole, key=f"hole_{pairing['id']}")
            new_score = uc2.text_input("Score (e.g. 2 Up)", value=current_score, key=f"score_{pairing['id']}")
            new_status = uc3.selectbox("Status", ["LIVE", "FINISHED"], index=0 if current_status=="LIVE" else 1, key=f"status_{pairing['id']}")
            
            # Map the leader string from the DB to an index for the radio button
            leader_options = ["home", "away", "tied"]
            leader_index = leader_options.index(current_leader) if current_leader in leader_options else 2
            new_leader = st.radio("Who is leading?", leader_options, index=leader_index, key=f"leader_{pairing['id']}")
            
            if st.button("Save Update", key=f"btn_{pairing['id']}"):
                update_score(pairing['id'], new_hole, new_score, new_status, new_leader)
                st.rerun() # Refresh immediately to show the new data
        
        st.divider()
