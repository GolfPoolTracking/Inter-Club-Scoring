import streamlit as st
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="L&B Live Scoring", layout="centered")

# --- MOCK DATABASE (Replace with Supabase/Firebase) ---
# In a real app, this data fetches from your database on load
if 'matches' not in st.session_state:
    st.session_state.matches = {
        "Junior Cup": {
            "date": "2026-05-23",
            "home_team": "Headfort Golf Club",
            "away_team": "Laytown Bettystown",
            "pairings": [
                {"id": 1, "home_player": "Jamie Lynch", "away_player": "Laytown Bettystown", "status": "FINISHED", "hole": 16, "score": "3 Up", "leader": "away"},
                {"id": 2, "home_player": "Joe Hannigan", "away_player": "Laytown Bettystown", "status": "FINISHED", "hole": 18, "score": "2 Up", "leader": "home"},
                {"id": 3, "home_player": "Dean O'Rourke", "away_player": "Laytown Bettystown", "status": "FINISHED", "hole": 15, "score": "4 Up", "leader": "home"},
                {"id": 4, "home_player": "Kyle McGuiness", "away_player": "Laytown Bettystown", "status": "FINISHED", "hole": 15, "score": "4 Up", "leader": "away"},
                {"id": 5, "home_player": "Nigel Watts", "away_player": "Laytown Bettystown", "status": "LIVE", "hole": 17, "score": "ALL SQUARE", "leader": "tied"},
            ]
        },
        "Barton Shield": {
            "date": "2026-05-23",
            "home_team": "Headfort Golf Club",
            "away_team": "Forrest Little",
            "pairings": [] # Add pairings here
        }
    }

# --- HELPER FUNCTIONS ---
def calculate_overall_score(competition_name):
    """Calculates the overall match score based on individual pairings."""
    home_score = 0.0
    away_score = 0.0
    
    for pairing in st.session_state.matches[competition_name]["pairings"]:
        if pairing["status"] == "FINISHED":
            if pairing["leader"] == "home":
                home_score += 1
            elif pairing["leader"] == "away":
                away_score += 1
            else:
                home_score += 0.5
                away_score += 0.5
    return home_score, away_score

def update_score(comp_name, pairing_id, new_hole, new_score, new_status, new_leader):
    """Updates the state. THIS IS WHERE YOU ADD YOUR DATABASE UPDATE LOGIC."""
    for pairing in st.session_state.matches[comp_name]["pairings"]:
        if pairing["id"] == pairing_id:
            pairing["hole"] = new_hole
            pairing["score"] = new_score
            pairing["status"] = new_status
            pairing["leader"] = new_leader
            break
    # e.g., supabase.table('pairings').update({'score': new_score}).eq('id', pairing_id).execute()

# --- UI NAVIGATION ---
st.sidebar.title("Navigation")
view = st.sidebar.radio("Go to", ["Competitions", "Match Overview", "Live Scoring (Admin)"])

selected_comp = st.sidebar.selectbox("Select Competition", list(st.session_state.matches.keys()))

# --- VIEW 1: COMPETITION LIST (Screenshot 1) ---
if view == "Competitions":
    st.header("Select Competition")
    
    for comp, data in st.session_state.matches.items():
        home_score, away_score = calculate_overall_score(comp)
        
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

# --- VIEW 2: MATCH OVERVIEW (Screenshot 2) ---
elif view == "Match Overview":
    data = st.session_state.matches[selected_comp]
    home_score, away_score = calculate_overall_score(selected_comp)
    
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

# --- VIEW 3: LIVE SCORING ADMIN (Screenshot 3) ---
elif view == "Live Scoring (Admin)":
    data = st.session_state.matches[selected_comp]
    home_score, away_score = calculate_overall_score(selected_comp)
    
    st.markdown(f"<h3 style='text-align: center;'>{selected_comp}</h3>", unsafe_allow_html=True)
    
    # Top Score Header
    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
    col1.write(f"<div style='text-align: right; padding-top:10px;'>{data['home_team']}</div>", unsafe_allow_html=True)
    col2.markdown(f"<div style='background-color: darkred; color: white; padding: 10px; text-align: center; border-radius: 5px;'>{home_score}</div>", unsafe_allow_html=True)
    col3.markdown(f"<div style='background-color: darkblue; color: white; padding: 10px; text-align: center; border-radius: 5px;'>{away_score}</div>", unsafe_allow_html=True)
    col4.write(f"<div style='text-align: left; padding-top:10px;'>{data['away_team']}</div>", unsafe_allow_html=True)
    st.divider()
    
    # Individual Matches
    for i, pairing in enumerate(data["pairings"]):
        pc1, pc2, pc3 = st.columns([1, 1, 1])
        
        # Player 1 Col
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
            
        # Player 2 Col
        with pc3:
             st.write(f"**{pairing['away_player']}**")
             if pairing['leader'] == 'away':
                st.markdown(f"<div style='background-color: darkblue; color: white; text-align: center; padding: 5px;'>{pairing['score']}</div>", unsafe_allow_html=True)
             elif pairing['leader'] == 'tied':
                st.markdown(f"<div style='background-color: black; color: white; text-align: center; padding: 5px;'>ALL SQUARE</div>", unsafe_allow_html=True)

        # Admin Controls (Expandable to keep UI clean)
        with st.expander(f"Update Match {i+1}"):
            uc1, uc2, uc3 = st.columns(3)
            new_hole = uc1.number_input("Hole", min_value=1, max_value=19, value=pairing['hole'], key=f"hole_{i}")
            new_score = uc2.text_input("Score (e.g. 2 Up)", value=pairing['score'], key=f"score_{i}")
            new_status = uc3.selectbox("Status", ["LIVE", "FINISHED"], index=0 if pairing['status']=="LIVE" else 1, key=f"status_{i}")
            new_leader = st.radio("Who is leading?", ["home", "away", "tied"], index=["home", "away", "tied"].index(pairing['leader']), key=f"leader_{i}")
            
            if st.button("Save Update", key=f"btn_{i}"):
                update_score(selected_comp, pairing['id'], new_hole, new_score, new_status, new_leader)
                st.rerun() # Refreshes the UI instantly
        
        st.divider()
