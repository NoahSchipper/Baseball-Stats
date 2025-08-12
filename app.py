from flask import Flask, request, jsonify, send_from_directory
from pybaseball import playerid_lookup, batting_stats, cache
from pybaseball import pitching_stats
import sqlite3
import pandas as pd
import os
import datetime

app = Flask(__name__, static_folder="static")
cache.enable()

DB_PATH = r"C:\Users\noahs\OneDrive\Documents\Baseball Stats\lahman2024.db"

KNOWN_TWO_WAY_PLAYERS = {
    # Modern era two-way players
    'ohtansh01': 'Shohei Ohtani',
    
    # Historical two-way players (primarily known for both)
    'ruthba01': 'Babe Ruth',
    
    # Players who had significant time as both (adjust as needed)
    'rickmri01': 'Rick Ankiel',  # Started as pitcher, became position player
    'martipe02': 'Pedro Martinez',  # Some hitting early in career
    
    # Add more as you identify them
    # Format: 'playerid': 'Display Name'
}

def is_predefined_two_way_player(playerid):
    """Check if player is in our predefined list of two-way players"""
    return playerid in KNOWN_TWO_WAY_PLAYERS

def detect_two_way_player_simple(playerid, conn):
    """Simplified two-way detection using only predefined list"""
    if is_predefined_two_way_player(playerid):
        return "two-way"
    
    # For all other players, use the original detection logic
    return detect_player_type(playerid, conn)

def get_career_war(playerid):
    """Get career WAR from JEFFBAGWELL database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT SUM(WAR162) as career_war 
            FROM jeffbagwell_war 
            WHERE key_bbref = ?
        """, (playerid,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] is not None:
            return float(result[0])
        return 0.0
        
    except Exception as e:
        print(f"Error getting career WAR: {e}")
        return 0.0


def get_season_war_history(playerid):
    """Get season-by-season WAR from JEFFBAGWELL database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("""
            SELECT year_ID, WAR162 as war
            FROM jeffbagwell_war 
            WHERE key_bbref = ?
            ORDER BY year_ID DESC
        """, conn, params=(playerid,))
        conn.close()
        return df
        
    except Exception as e:
        print(f"Error getting season WAR history: {e}")
        return pd.DataFrame()


def detect_player_type(playerid, conn):
    """Detect if player is primarily a pitcher or hitter based on their stats"""
    pitching_query = """
    SELECT COUNT(*) as pitch_seasons, SUM(g) as total_games_pitched, SUM(gs) as total_starts
    FROM lahman_pitching WHERE playerid = ?
    """
    cursor = conn.cursor()
    cursor.execute(pitching_query, (playerid,))
    pitch_result = cursor.fetchone()
    
    batting_query = """
    SELECT COUNT(*) as bat_seasons, SUM(g) as total_games_batted, SUM(ab) as total_at_bats
    FROM lahman_batting WHERE playerid = ?
    """
    cursor.execute(batting_query, (playerid,))
    bat_result = cursor.fetchone()
    
    pitch_seasons = pitch_result[0] if pitch_result else 0
    total_games_pitched = pitch_result[1] if pitch_result and pitch_result[1] else 0
    total_starts = pitch_result[2] if pitch_result and pitch_result[2] else 0
    
    bat_seasons = bat_result[0] if bat_result else 0
    total_games_batted = bat_result[1] if bat_result and bat_result[1] else 0
    total_at_bats = bat_result[2] if bat_result and bat_result[2] else 0
    
    if pitch_seasons >= 3 or total_games_pitched >= 50 or total_starts >= 10:
        return "pitcher"
    elif bat_seasons >= 3 or total_at_bats >= 300:
        return "hitter"
    else:
        return "pitcher" if pitch_seasons > 0 else "hitter"
'''
def detect_two_way_player(playerid, conn):
    """Detect if player is a significant two-way player (both pitcher and hitter)"""
    cursor = conn.cursor()
    
    # Get pitching stats
    pitching_query = """
    SELECT COUNT(*) as pitch_seasons, SUM(g) as total_games_pitched, 
           SUM(gs) as total_starts, SUM(ipouts) as total_outs
    FROM lahman_pitching WHERE playerid = ?
    """
    cursor.execute(pitching_query, (playerid,))
    pitch_result = cursor.fetchone()
    
    # Get batting stats  
    batting_query = """
    SELECT COUNT(*) as bat_seasons, SUM(g) as total_games_batted, 
           SUM(ab) as total_at_bats, SUM(h) as total_hits
    FROM lahman_batting WHERE playerid = ?
    """
    cursor.execute(batting_query, (playerid,))
    bat_result = cursor.fetchone()
    
    pitch_seasons = pitch_result[0] if pitch_result else 0
    total_games_pitched = pitch_result[1] if pitch_result and pitch_result[1] else 0
    total_starts = pitch_result[2] if pitch_result and pitch_result[2] else 0
    total_innings = (pitch_result[3] or 0) / 3.0
    
    bat_seasons = bat_result[0] if bat_result else 0
    total_games_batted = bat_result[1] if bat_result and bat_result[1] else 0
    total_at_bats = bat_result[2] if bat_result and bat_result[2] else 0
    total_hits = bat_result[3] if bat_result and bat_result[3] else 0
    
    # Define thresholds for significant two-way players
    significant_pitcher = (
        pitch_seasons >= 3 or 
        total_games_pitched >= 50 or 
        total_starts >= 10 or
        total_innings >= 100
    )
    
    significant_hitter = (
        bat_seasons >= 3 or 
        total_at_bats >= 500 or
        total_hits >= 100
    )
    
    if significant_pitcher and significant_hitter:
        return "two-way"
    elif significant_pitcher:
        return "pitcher"
    elif significant_hitter:
        return "hitter"
    else:
        return "pitcher" if pitch_seasons > 0 else "hitter"
        ''' 

# Add this new route for two-way player handling
@app.route("/player-two-way")
def get_player_with_two_way():
    """Enhanced player endpoint that handles two-way players"""
    name = request.args.get("name", "")
    mode = request.args.get("mode", "career").lower()
    player_type = request.args.get("player_type", "").lower()  # "pitcher" or "hitter"

    if " " not in name:
        return jsonify({"error": "Enter full name"}), 400

    # Try improved lookup with disambiguation
    playerid, suggestions = improved_player_lookup_with_disambiguation(name)
    
    if playerid is None and suggestions:
        return jsonify({
            "error": "Multiple players found",
            "suggestions": suggestions,
            "message": f"Found {len(suggestions)} players named '{name.split(' Jr.')[0].split(' Sr.')[0]}'. Please specify which player:"
        }), 422
    
    if playerid is None:
        return jsonify({"error": "Player not found"}), 404
    
    conn = sqlite3.connect(DB_PATH)
    detected_type = detect_two_way_player_simple(playerid, conn)
    
    # Get player's actual name for display
    cursor = conn.cursor()
    cursor.execute("SELECT namefirst, namelast FROM lahman_people WHERE playerid = ?", (playerid,))
    name_result = cursor.fetchone()
    first, last = name_result if name_result else ("Unknown", "Unknown")
    
    # Handle two-way players
    if detected_type == "two-way" and not player_type:
        # Return options for user to choose
        conn.close()
        return jsonify({
            "error": "Two-way player detected",
            "player_type": "two-way",
            "options": [
                {"type": "pitcher", "label": f"{first} {last} (Pitching Stats)"},
                {"type": "hitter", "label": f"{first} {last} (Hitting Stats)"}
            ],
            "message": f"{first} {last} is a known two-way player. Please select which stats to display:"
        }), 423  # Using 423 for two-way player selection
    
    # Use specified player_type or detected type
    final_type = player_type if player_type in ["pitcher", "hitter"] else detected_type
    if final_type == "two-way":
        final_type = "hitter"  # Default fallback
    
    # Get photo URL
    mlb_id = None
    try:
        lookup = playerid_lookup(last, first)
        if not lookup.empty and not pd.isna(lookup.iloc[0]['key_mlbam']):
            mlb_id = int(lookup.iloc[0]['key_mlbam'])
    except Exception:
        pass

    photo_url = None
    if mlb_id:
        photo_url = f"https://img.mlbstatic.com/mlb-photos/image/upload/v1/people/{mlb_id}/headshot/67/current.jpg"

    # Process stats based on final type
    if final_type == "pitcher":
        return handle_pitcher_stats(playerid, conn, mode, photo_url, first, last)
    else:
        conn.close()
        return handle_hitter_stats(playerid, mode, photo_url, first, last)


# Add these routes to your existing Flask app
@app.route('/search-players')
def search_players():
    """Search for players with fuzzy matching"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([])
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Clean the query for better matching
        query_clean = query.lower().strip()
        search_term = f"%{query_clean}%"
        
        # Search in lahman_people table with multiple matching strategies
        search_query = """
        SELECT DISTINCT 
            namefirst || ' ' || namelast as full_name,
            playerid,
            CASE 
                WHEN LOWER(namefirst || ' ' || namelast) LIKE ? THEN 1
                WHEN LOWER(namelast) LIKE ? THEN 2
                WHEN LOWER(namefirst) LIKE ? THEN 3
                ELSE 4
            END as priority
        FROM lahman_people 
        WHERE LOWER(namefirst || ' ' || namelast) LIKE ?
           OR LOWER(namelast) LIKE ?
           OR LOWER(namefirst) LIKE ?
        ORDER BY priority, namelast, namefirst
        LIMIT 15
        """
        
        cursor.execute(search_query, (
            f"{query_clean}%",  # Full name starts with query (highest priority)
            f"{query_clean}%",  # Last name starts with query
            f"{query_clean}%",  # First name starts with query  
            search_term,        # Full name contains query anywhere
            search_term,        # Last name contains query anywhere
            search_term         # First name contains query anywhere
        ))
        
        results = cursor.fetchall()
        conn.close()
        
        # Format results - just return player names for simple implementation
        players = [row[0] for row in results]
        
        return jsonify(players)
        
    except Exception as e:
        print(f"Database search failed: {e}")
        return jsonify([])

@app.route('/search-players-enhanced')
def search_players_enhanced():
    """Enhanced search that handles father/son players and provides disambiguation"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([])
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query_clean = query.lower().strip()
        search_term = f"%{query_clean}%"
        
        # Enhanced search with birth year and additional info for disambiguation
        search_query = """
        SELECT DISTINCT 
            p.namefirst || ' ' || p.namelast as full_name,
            p.playerid,
            p.debut,
            p.finalgame,
            p.birthyear,
            p.birthmonth,
            p.birthday,
            CASE 
                WHEN LOWER(p.namefirst || ' ' || p.namelast) LIKE ? THEN 1
                WHEN LOWER(p.namelast) LIKE ? THEN 2
                WHEN LOWER(p.namefirst) LIKE ? THEN 3
                ELSE 4
            END as priority,
            -- Get primary position
            (SELECT pos FROM lahman_fielding f 
             WHERE f.playerid = p.playerid 
             GROUP BY pos 
             ORDER BY SUM(g) DESC 
             LIMIT 1) as primary_pos,
            -- Check if this player has stats (to filter out coaches, etc.)
            CASE WHEN EXISTS (
                SELECT 1 FROM lahman_batting b WHERE b.playerid = p.playerid
            ) OR EXISTS (
                SELECT 1 FROM lahman_pitching pt WHERE pt.playerid = p.playerid
            ) THEN 1 ELSE 0 END as has_stats
        FROM lahman_people p
        WHERE (LOWER(p.namefirst || ' ' || p.namelast) LIKE ?
           OR LOWER(p.namelast) LIKE ?
           OR LOWER(p.namefirst) LIKE ?)
        AND p.birthyear IS NOT NULL  -- Filter out entries without birth year
        ORDER BY priority, has_stats DESC, p.debut DESC, p.namelast, p.namefirst
        LIMIT 15
        """
        
        cursor.execute(search_query, (
            f"{query_clean}%", f"{query_clean}%", f"{query_clean}%",
            search_term, search_term, search_term
        ))
        
        results = cursor.fetchall()
        
        # Group players by name to detect duplicates
        name_groups = {}
        for row in results:
            full_name, playerid, debut, final_game, birth_year, birth_month, birth_day, priority, position, has_stats = row
            
            if full_name not in name_groups:
                name_groups[full_name] = []
            
            name_groups[full_name].append({
                'full_name': full_name,
                'playerid': playerid,
                'debut': debut,
                'final_game': final_game,
                'birth_year': birth_year,
                'birth_month': birth_month,
                'birth_day': birth_day,
                'position': position,
                'has_stats': has_stats
            })
        
        conn.close()
        
        # Process results and add disambiguation
        players = []
        for name, player_list in name_groups.items():
            if len(player_list) == 1:
                # Single player with this name
                player = player_list[0]
                debut_year = player['debut'][:4] if player['debut'] else "Unknown"
                
                if player['position']:
                    display_name = f"{name} ({player['position']}, {debut_year})"
                else:
                    display_name = f"{name} ({debut_year})"
                
                players.append({
                    'name': name,
                    'display': display_name,
                    'playerid': player['playerid'],
                    'debut_year': debut_year,
                    'position': player['position'] or 'Unknown',
                    'disambiguation': None
                })
            else:
                # Multiple players with same name - add disambiguation
                # Sort by debut year (older first)
                player_list.sort(key=lambda x: x['debut'] or '9999')
                
                for i, player in enumerate(player_list):
                    debut_year = player['debut'][:4] if player['debut'] else "Unknown"
                    birth_year = player['birth_year'] or "Unknown"
                    
                    # Determine suffix (Sr./Jr. or I/II based on debut order)
                    if len(player_list) == 2:
                        suffix = "Sr." if i == 0 else "Jr."
                    else:
                        suffix = ["Sr.", "Jr.", "III"][i] if i < 3 else f"({i+1})"
                    
                    # Create display name with disambiguation
                    base_display = f"{name} {suffix}"
                    if player['position']:
                        display_name = f"{base_display} ({player['position']}, {debut_year})"
                    else:
                        display_name = f"{base_display} ({debut_year})"
                    
                    players.append({
                        'name': name,
                        'display': display_name,
                        'playerid': player['playerid'],
                        'debut_year': debut_year,
                        'birth_year': str(birth_year),
                        'position': player['position'] or 'Unknown',
                        'disambiguation': suffix,
                        'original_name': name
                    })
        
        return jsonify(players)
        
    except Exception as e:
        print(f"Enhanced search failed: {e}")
        return jsonify([])


def improved_player_lookup_with_disambiguation(name):
    """
    Improved player lookup that handles common father/son cases
    and provides suggestions when multiple players exist
    """
    # Handle common suffixes
    suffixes = {
        'jr': 'Jr.',
        'jr.': 'Jr.',
        'junior': 'Jr.',
        'sr': 'Sr.',
        'sr.': 'Sr.',
        'senior': 'Sr.',
        'ii': 'II',
        'iii': 'III',
        '2nd': 'II',
        '3rd': 'III'
    }
    
    name_lower = name.lower().strip()
    suffix = None
    clean_name = name
    
    # Check if name contains a suffix
    for suffix_variant, standard_suffix in suffixes.items():
        if name_lower.endswith(' ' + suffix_variant):
            suffix = standard_suffix
            clean_name = name[:-(len(suffix_variant) + 1)].strip()
            break
    
    if " " not in clean_name:
        return None, []
    
    first, last = clean_name.split(" ", 1)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Find all players with this name
    all_players_query = """
    SELECT playerid, namefirst, namelast, debut, finalgame, birthyear
    FROM lahman_people
    WHERE LOWER(namefirst) = ? AND LOWER(namelast) = ?
    ORDER BY debut
    """
    
    cursor.execute(all_players_query, (first.lower(), last.lower()))
    all_matches = cursor.fetchall()
    conn.close()
    
    if not all_matches:
        return None, []
    
    if len(all_matches) == 1:
        return all_matches[0][0], []
    
    # Multiple players found
    suggestions = []
    target_player = None
    
    for i, (playerid, fname, lname, debut, final_game, birth_year) in enumerate(all_matches):
        full_name = f"{fname} {lname}"
        debut_year = debut[:4] if debut else "Unknown"
        
        # Create suggestion with disambiguation
        if len(all_matches) == 2:
            player_suffix = "Sr." if i == 0 else "Jr."
        else:
            player_suffix = ["Sr.", "Jr.", "III"][i] if i < 3 else f"({i+1})"
        
        suggestion = {
            'name': f"{full_name} {player_suffix}",
            'playerid': playerid,
            'debut_year': debut_year,
            'birth_year': birth_year or "Unknown"
        }
        suggestions.append(suggestion)
        
        # If user specified a suffix, try to match it
        if suffix:
            if suffix == player_suffix:
                target_player = playerid
    
    return target_player, suggestions


@app.route("/player-disambiguate")
def get_player_with_disambiguation():
    """Enhanced player endpoint that handles disambiguation"""
    name = request.args.get("name", "")
    mode = request.args.get("mode", "career").lower()
    player_type = request.args.get("player_type", "").lower()

    if " " not in name:
        return jsonify({"error": "Enter full name"}), 400

    # Try improved lookup
    playerid, suggestions = improved_player_lookup_with_disambiguation(name)
    
    if playerid is None and suggestions:
        # Multiple players found, return suggestions
        return jsonify({
            "error": "Multiple players found",
            "suggestions": suggestions,
            "message": f"Found {len(suggestions)} players named '{name.split(' Jr.')[0].split(' Sr.')[0]}'. Please specify which player:"
        }), 422
    
    if playerid is None:
        return jsonify({"error": "Player not found"}), 404
    
    # Continue with existing logic using the found playerid
    conn = sqlite3.connect(DB_PATH)
    detected_type = detect_two_way_player_simple(playerid, conn)
    
    # Get player's actual name for display
    cursor = conn.cursor()
    cursor.execute("SELECT namefirst, namelast FROM lahman_people WHERE playerid = ?", (playerid,))
    name_result = cursor.fetchone()
    first, last = name_result if name_result else ("Unknown", "Unknown")
    
    # Handle two-way players
    if detected_type == "two-way" and not player_type:
        conn.close()
        return jsonify({
            "error": "Two-way player detected",
            "player_type": "two-way", 
            "options": [
                {"type": "pitcher", "label": f"{first} {last} (Pitching Stats)"},
                {"type": "hitter", "label": f"{first} {last} (Hitting Stats)"}
            ],
            "message": f"{first} {last} is a known two-way player. Please select which stats to display:"
        }), 423
    
    # Continue with existing logic using specified or detected type
    final_type = player_type if player_type in ["pitcher", "hitter"] else detected_type
    if final_type == "two-way":
        final_type = "hitter"  # Default fallback
    # Rest of the logic remains the same...
    # [Include your existing photo URL and stats logic here]
    
    mlb_id = None
    try:
        lookup = playerid_lookup(last, first)
        if not lookup.empty and not pd.isna(lookup.iloc[0]['key_mlbam']):
            mlb_id = int(lookup.iloc[0]['key_mlbam'])
    except Exception:
        pass

    photo_url = None
    if mlb_id:
        photo_url = f"https://img.mlbstatic.com/mlb-photos/image/upload/v1/people/{mlb_id}/headshot/67/current.jpg"

    if player_type == "pitcher":
        return handle_pitcher_stats(playerid, conn, mode, photo_url, first, last)
    else:
        conn.close()
        return handle_hitter_stats(playerid, mode, photo_url, first, last)

@app.route('/search-players-detailed')  
def search_players_detailed():
    """Search for players with additional info like debut year and position"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([])
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query_clean = query.lower().strip()
        search_term = f"%{query_clean}%"
        
        # Enhanced search with additional player info
        search_query = """
        SELECT DISTINCT 
            p.namefirst || ' ' || p.namelast as full_name,
            p.playerid,
            p.debut,
            p.finalgame,
            CASE 
                WHEN LOWER(p.namefirst || ' ' || p.namelast) LIKE ? THEN 1
                WHEN LOWER(p.namelast) LIKE ? THEN 2
                WHEN LOWER(p.namefirst) LIKE ? THEN 3
                ELSE 4
            END as priority,
            -- Try to get primary position from fielding data
            (SELECT pos FROM lahman_fielding f 
             WHERE f.playerid = p.playerid 
             GROUP BY pos 
             ORDER BY SUM(g) DESC 
             LIMIT 1) as primary_pos
        FROM lahman_people p
        WHERE LOWER(p.namefirst || ' ' || p.namelast) LIKE ?
           OR LOWER(p.namelast) LIKE ?
           OR LOWER(p.namefirst) LIKE ?
        ORDER BY priority, p.namelast, p.namefirst
        LIMIT 12
        """
        
        cursor.execute(search_query, (
            f"{query_clean}%", f"{query_clean}%", f"{query_clean}%",
            search_term, search_term, search_term
        ))
        
        results = cursor.fetchall()
        conn.close()
        
        players = []
        for row in results:
            full_name, playerid, debut, final_game, priority, position = row
            
            # Format debut year for display
            debut_year = debut[:4] if debut else "Unknown"
            final_year = final_game[:4] if final_game else "Present"
            
            # Create display string with additional context
            if position:
                display_name = f"{full_name} ({position}, {debut_year})"
            else:
                display_name = f"{full_name} ({debut_year})"
            
            players.append({
                'name': full_name,
                'display': display_name,
                'playerid': playerid,
                'debut_year': debut_year,
                'position': position or 'Unknown'
            })
        
        return jsonify(players)
        
    except Exception as e:
        print(f"Detailed search failed: {e}")
        return jsonify([])

@app.route('/popular-players')
def popular_players():
    fallback_players = [
        "Mike Trout", "Aaron Judge", "Mookie Betts", "Ronald Acuna Jr.",
        "Juan Soto", "Vladimir Guerrero Jr.", "Fernando Tatis Jr.", 
        "Gerrit Cole", "Jacob deGrom", "Shane Bieber", "Spencer Strider",
        "Freddie Freeman", "Manny Machado", "Jose Altuve", "Kyle Tucker"
    ]
    return jsonify(fallback_players)


# Optional: Add a route to get all unique player names (for advanced frontend caching)
@app.route('/all-players')
def all_players():
    """Get all player names - useful for client-side caching if needed"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all players who have batting or pitching stats
        all_players_query = """
        SELECT DISTINCT p.namefirst || ' ' || p.namelast as full_name
        FROM lahman_people p
        WHERE EXISTS (
            SELECT 1 FROM lahman_batting b WHERE b.playerid = p.playerid
        ) OR EXISTS (
            SELECT 1 FROM lahman_pitching pt WHERE pt.playerid = p.playerid
        )
        ORDER BY p.namelast, p.namefirst
        """
        
        cursor.execute(all_players_query)
        results = cursor.fetchall()
        conn.close()
        
        players = [row[0] for row in results]
        return jsonify(players)
        
    except Exception as e:
        print(f"All players query failed: {e}")
        return jsonify([])

# Also add this helper function to improve your existing player lookup
def improved_player_lookup(name):
    """Improved player lookup with better fuzzy matching"""
    if " " not in name:
        return None
        
    first, last = name.split(" ", 1)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Try exact match first
    exact_query = """
    SELECT playerid FROM lahman_people
    WHERE LOWER(namefirst) = ? AND LOWER(namelast) = ?
    LIMIT 1
    """
    cursor.execute(exact_query, (first.lower(), last.lower()))
    result = cursor.fetchone()
    
    if result:
        conn.close()
        return result[0]
    
    # Try fuzzy matching
    fuzzy_query = """
    SELECT playerid, namefirst, namelast,
           CASE 
               WHEN LOWER(namelast) = ? THEN 1
               WHEN LOWER(namefirst) = ? THEN 2  
               WHEN LOWER(namelast) LIKE ? THEN 3
               WHEN LOWER(namefirst) LIKE ? THEN 4
               ELSE 5
           END as match_quality
    FROM lahman_people
    WHERE LOWER(namelast) LIKE ? OR LOWER(namefirst) LIKE ?
    ORDER BY match_quality
    LIMIT 1
    """
    
    search_pattern = f"%{last.lower()}%"
    first_pattern = f"%{first.lower()}%"
    
    cursor.execute(fuzzy_query, (
        last.lower(), first.lower(), 
        search_pattern, first_pattern,
        search_pattern, first_pattern
    ))
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None

@app.route("/")
def serve_index():
    return send_from_directory("static", "index.html")


@app.route("/player")
def get_player_stats():
    name = request.args.get("name", "")
    mode = request.args.get("mode", "career").lower()

    if " " not in name:
        return jsonify({"error": "Enter full name"}), 400

    first, last = name.split(" ", 1)

    conn = sqlite3.connect(DB_PATH)
    query_id = """
    SELECT playerid FROM lahman_people
    WHERE LOWER(namefirst) = ? AND LOWER(namelast) = ?
    LIMIT 1
    """
    cur = conn.cursor()
    cur.execute(query_id, (first.lower(), last.lower()))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Player not found"}), 404

    playerid = row[0]

    player_type = detect_player_type(playerid, conn)

    mlb_id = None
    try:
        lookup = playerid_lookup(last, first)
        if not lookup.empty and not pd.isna(lookup.iloc[0]['key_mlbam']):
            mlb_id = int(lookup.iloc[0]['key_mlbam'])
    except Exception:
        pass

    photo_url = None
    if mlb_id:
        photo_url = f"https://img.mlbstatic.com/mlb-photos/image/upload/v1/people/{mlb_id}/headshot/67/current.jpg"

    if player_type == "pitcher":
        return handle_pitcher_stats(playerid, conn, mode, photo_url, first, last)
    else:
        conn.close()
        return handle_hitter_stats(playerid, mode, photo_url, first, last)


def handle_pitcher_stats(playerid, conn, mode, photo_url, first, last):
    stats_query = """
    SELECT yearid, teamid, w, l, g, gs, cg, sho, sv, ipouts, h, er, hr, bb, so, era
    FROM lahman_pitching WHERE playerid = ?
    """
    df_lahman = pd.read_sql_query(stats_query, conn, params=(playerid,))
    conn.close()

    current_year = datetime.date.today().year
    live_row = pd.DataFrame()
    
    try:
        df_live = pitching_stats(current_year, qual=0)
        live_row = find_live_player_match(df_live, first, last)

        
        if not df_live.empty:
            df_live['Name'] = df_live['Name'].str.strip()
            df_live['Name_lower'] = df_live['Name'].str.lower()
            
            search_patterns = [
                f"{first.lower()} {last.lower()}",
                f"{last.lower()}, {first.lower()}",
                f"{first.lower()}.{last.lower()}",
                f"{first[0].lower()}.{last.lower()}",
                f"{last.lower()}"
            ]
            
            for pattern in search_patterns:
                live_row = df_live[df_live['Name_lower'] == pattern]
                if not live_row.empty:
                    break
            
            if live_row.empty:
                last_name_matches = df_live[df_live['Name_lower'].str.contains(last.lower(), na=False)]
                if not last_name_matches.empty:
                    for _, row in last_name_matches.iterrows():
                        if first.lower() in row['Name_lower']:
                            live_row = last_name_matches[last_name_matches['Name'] == row['Name']]
                            break
                    
                    if live_row.empty:
                        live_row = last_name_matches.head(1)
        
    except Exception as e:
        live_row = pd.DataFrame()

    if mode == "career":
        if df_lahman.empty:
            return jsonify({"error": "No pitching stats found"}), 404

        totals = df_lahman.agg({
            "w": "sum", "l": "sum", "g": "sum", "gs": "sum", "cg": "sum",
            "sho": "sum", "sv": "sum", "ipouts": "sum", "h": "sum", "er": "sum",
            "hr": "sum", "bb": "sum", "so": "sum"
        }).to_dict()

        innings_pitched = totals["ipouts"] / 3.0 if totals["ipouts"] > 0 else 0
        era = (totals["er"] * 9) / innings_pitched if innings_pitched > 0 else 0
        whip = (totals["h"] + totals["bb"]) / innings_pitched if innings_pitched > 0 else 0
        
        career_war = get_career_war(playerid)

        result = {
            "war": round(career_war, 1),
            "wins": int(totals["w"]),
            "losses": int(totals["l"]),
            "games": int(totals["g"]),
            "games_started": int(totals["gs"]),
            "complete_games": int(totals["cg"]),
            "shutouts": int(totals["sho"]),
            "saves": int(totals["sv"]),
            "innings_pitched": round(innings_pitched, 1),
            "hits_allowed": int(totals["h"]),
            "earned_runs": int(totals["er"]),
            "home_runs_allowed": int(totals["hr"]),
            "walks": int(totals["bb"]),
            "strikeouts": int(totals["so"]),
            "era": round(era, 2),
            "whip": round(whip, 2)
        }

        return jsonify({
            "mode": "career",
            "player_type": "pitcher",
            "totals": result,
            "photo_url": photo_url
        })

    elif mode == "season":
        if df_lahman.empty:
            return jsonify({"error": "No pitching stats found"}), 404

        df_war_history = get_season_war_history(playerid)

        df = df_lahman.copy()
        df["innings_pitched"] = df["ipouts"] / 3.0
        df["era_calc"] = df.apply(lambda row: (row["er"] * 9) / (row["ipouts"] / 3.0) if row["ipouts"] > 0 else 0, axis=1)
        df["whip"] = df.apply(lambda row: (row["h"] + row["bb"]) / (row["ipouts"] / 3.0) if row["ipouts"] > 0 else 0, axis=1)

        df["era_final"] = df.apply(lambda row: row["era"] if row["era"] > 0 else row["era_calc"], axis=1)

        if not df_war_history.empty:
            df = df.merge(df_war_history, left_on='yearid', right_on='year_ID', how='left')
            df['war'] = df['war'].fillna(0)
        else:
            df['war'] = 0

        df_result = df[[
            "yearid", "teamid", "w", "l", "g", "gs", "cg", "sho", "sv", 
            "innings_pitched", "h", "er", "hr", "bb", "so", "era_final", "whip", "war"
        ]].rename(columns={
            "yearid": "year", "w": "wins", "l": "losses", "g": "games", 
            "gs": "games_started", "cg": "complete_games", "sho": "shutouts", 
            "sv": "saves", "h": "hits_allowed", "er": "earned_runs", 
            "hr": "home_runs_allowed", "bb": "walks", "so": "strikeouts", "era_final": "era"
        })

        return jsonify({
            "mode": "season",
            "player_type": "pitcher",
            "stats": df_result.to_dict(orient="records"),
            "photo_url": photo_url
        })

    elif mode == "live":
        if live_row.empty:
            return jsonify({"error": f"No live pitching stats found for {first} {last}"}), 404

        live_stats = live_row.to_dict(orient="records")[0]

        war_value = 0
        for war_col in ['WAR', 'war', 'War', 'fWAR', 'bWAR', 'rWAR']:
            if war_col in live_stats and not pd.isna(live_stats[war_col]):
                war_value = float(live_stats[war_col])
                break

        def safe_get_stat(stat_names, default=0):
            for name in stat_names:
                if name in live_stats and not pd.isna(live_stats[name]):
                    return live_stats[name]
            return default

        wins = int(safe_get_stat(['W', 'Wins']))
        losses = int(safe_get_stat(['L', 'Losses'])) 
        games = int(safe_get_stat(['G', 'Games', 'GP']))
        games_started = int(safe_get_stat(['GS', 'Games Started']))
        complete_games = int(safe_get_stat(['CG', 'Complete Games']))
        shutouts = int(safe_get_stat(['SHO', 'Shutouts']))
        saves = int(safe_get_stat(['SV', 'Saves']))
        
        ip_raw = safe_get_stat(['IP', 'Innings Pitched', 'InningsPitched'])
        if isinstance(ip_raw, str):
            try:
                if '/' in ip_raw:
                    parts = ip_raw.split()
                    innings = float(parts[0])
                    if len(parts) > 1 and '/' in parts[1]:
                        frac_parts = parts[1].split('/')
                        innings += float(frac_parts[0]) / float(frac_parts[1])
                    innings_pitched = innings
                else:
                    innings_pitched = float(ip_raw)
            except:
                innings_pitched = 0.0
        else:
            innings_pitched = float(ip_raw) if ip_raw else 0.0
            
        hits_allowed = int(safe_get_stat(['H', 'Hits', 'Hits Allowed']))
        earned_runs = int(safe_get_stat(['ER', 'Earned Runs']))
        home_runs_allowed = int(safe_get_stat(['HR', 'Home Runs', 'HRA']))
        walks = int(safe_get_stat(['BB', 'Walks', 'Walk']))
        strikeouts = int(safe_get_stat(['SO', 'K', 'Strikeouts']))
        
        era = safe_get_stat(['ERA', 'era'])
        if era == 0 and innings_pitched > 0:
            era = (earned_runs * 9) / innings_pitched
        era = float(era)
        
        whip = safe_get_stat(['WHIP', 'whip'])
        if whip == 0 and innings_pitched > 0:
            whip = (hits_allowed + walks) / innings_pitched
        whip = float(whip)

        result = {
            "war": round(war_value, 1),
            "wins": wins,
            "losses": losses,
            "games": games,
            "games_started": games_started,
            "complete_games": complete_games,
            "shutouts": shutouts,
            "saves": saves,
            "innings_pitched": round(innings_pitched, 1),
            "hits_allowed": hits_allowed,
            "earned_runs": earned_runs,
            "home_runs_allowed": home_runs_allowed,
            "walks": walks,
            "strikeouts": strikeouts,
            "era": round(era, 2),
            "whip": round(whip, 3)
        }

        return jsonify({
            "mode": "live",
            "player_type": "pitcher",
            "stats": result,
            "photo_url": photo_url
        })

    elif mode == "combined":
        if df_lahman.empty:
            return jsonify({"error": "No career pitching stats found"}), 404

        totals = df_lahman.agg({
            "w": "sum", "l": "sum", "g": "sum", "gs": "sum", "cg": "sum",
            "sho": "sum", "sv": "sum", "ipouts": "sum", "h": "sum", "er": "sum",
            "hr": "sum", "bb": "sum", "so": "sum"
        }).to_dict()

        career_war = get_career_war(playerid)

        current_season_war = 0
        if not live_row.empty:
            live_stats = live_row.to_dict(orient="records")[0]
            totals["w"] += int(live_stats.get("W", 0))
            totals["l"] += int(live_stats.get("L", 0))
            totals["g"] += int(live_stats.get("G", 0))
            totals["gs"] += int(live_stats.get("GS", 0))
            totals["cg"] += int(live_stats.get("CG", 0))
            totals["sho"] += int(live_stats.get("SHO", 0))
            totals["sv"] += int(live_stats.get("SV", 0))
            live_ip = float(live_stats.get("IP", 0))
            totals["ipouts"] += int(live_ip * 3)
            totals["h"] += int(live_stats.get("H", 0))
            totals["er"] += int(live_stats.get("ER", 0))
            totals["hr"] += int(live_stats.get("HR", 0))
            totals["bb"] += int(live_stats.get("BB", 0))
            totals["so"] += int(live_stats.get("SO", 0))

            for war_col in ['WAR', 'war', 'War', 'fWAR', 'bWAR', 'rWAR']:
                if war_col in live_stats and not pd.isna(live_stats[war_col]):
                    current_season_war = float(live_stats[war_col])
                    break

        innings_pitched = totals["ipouts"] / 3.0 if totals["ipouts"] > 0 else 0
        era = (totals["er"] * 9) / innings_pitched if innings_pitched > 0 else 0
        whip = (totals["h"] + totals["bb"]) / innings_pitched if innings_pitched > 0 else 0
        combined_war = career_war + current_season_war

        result = {
            "war": round(combined_war, 1),
            "wins": int(totals["w"]),
            "losses": int(totals["l"]),
            "games": int(totals["g"]),
            "games_started": int(totals["gs"]),
            "complete_games": int(totals["cg"]),
            "shutouts": int(totals["sho"]),
            "saves": int(totals["sv"]),
            "innings_pitched": round(innings_pitched, 1),
            "hits_allowed": int(totals["h"]),
            "earned_runs": int(totals["er"]),
            "home_runs_allowed": int(totals["hr"]),
            "walks": int(totals["bb"]),
            "strikeouts": int(totals["so"]),
            "era": round(era, 2),
            "whip": round(whip, 2)
        }

        return jsonify({
            "mode": "combined",
            "player_type": "pitcher",
            "totals": result,
            "photo_url": photo_url
        })

    else:
        return jsonify({"error": "Invalid mode"}), 400


def handle_hitter_stats(playerid, mode, photo_url, first, last):
    conn = sqlite3.connect(DB_PATH)

    stats_query = """
    SELECT yearid, teamid, g, ab, h, hr, rbi, sb, bb, hbp, sf, sh, "2b", "3b"
    FROM lahman_batting WHERE playerid = ?
    """
    df_lahman = pd.read_sql_query(stats_query, conn, params=(playerid,))
    conn.close()

    current_year = datetime.date.today().year
    live_row = pd.DataFrame()
    
    try:
        df_live = batting_stats(current_year)
        live_row = find_live_player_match(df_live, first, last)
    except Exception as e:
        live_row = pd.DataFrame()

    if mode == "career":
        if df_lahman.empty:
            return jsonify({"error": "No batting stats found"}), 404

        totals = df_lahman.agg({
            "g": "sum", "ab": "sum", "h": "sum", "hr": "sum", "rbi": "sum",
            "sb": "sum", "bb": "sum", "hbp": "sum", "sf": "sum", "sh": "sum", "2b": "sum", "3b": "sum"
        }).to_dict()

        singles = totals["h"] - totals["2b"] - totals["3b"] - totals["hr"]
        total_bases = singles + 2*totals["2b"] + 3*totals["3b"] + 4*totals["hr"]
        ba = totals["h"] / totals["ab"] if totals["ab"] > 0 else 0
        obp_denominator = totals["ab"] + totals["bb"] + totals["hbp"] + totals["sf"]
        obp = (totals["h"] + totals["bb"] + totals["hbp"]) / obp_denominator if obp_denominator > 0 else 0
        slg = total_bases / totals["ab"] if totals["ab"] > 0 else 0
        ops = obp + slg

        plate_appearances = totals["ab"] + totals["bb"] + totals["hbp"] + totals["sf"] + totals["sh"]

        career_war = get_career_war(playerid)

        ops_plus = 0
        if not live_row.empty:
            live_stats_temp = live_row.iloc[0]
            for ops_plus_col in ['OPS+', 'OPS_plus', 'wRC+', 'ops_plus']:
                if ops_plus_col in live_stats_temp and not pd.isna(live_stats_temp[ops_plus_col]):
                    ops_plus = float(live_stats_temp[ops_plus_col])
                    break

        result = {
            "war": round(career_war, 1),
            "games": int(totals["g"]),
            "plate_appearances": int(plate_appearances),
            "hits": int(totals["h"]),
            "home_runs": int(totals["hr"]),
            "rbi": int(totals["rbi"]),
            "stolen_bases": int(totals["sb"]),
            "batting_average": round(ba, 3),
            "on_base_percentage": round(obp, 3),
            "slugging_percentage": round(slg, 3),
            "ops": round(ops, 3),
            "ops_plus": int(ops_plus)
        }

        return jsonify({
            "mode": "career",
            "player_type": "hitter",
            "totals": result,
            "photo_url": photo_url
        })

    elif mode == "season":
        if df_lahman.empty:
            return jsonify({"error": "No batting stats found"}), 404

        df_war_history = get_season_war_history(playerid)

        df = df_lahman.copy()
        df["singles"] = df["h"] - df["2b"] - df["3b"] - df["hr"]
        df["total_bases"] = df["singles"] + 2*df["2b"] + 3*df["3b"] + 4*df["hr"]
        df["ba"] = df.apply(lambda row: row["h"] / row["ab"] if row["ab"] > 0 else 0, axis=1)
        df["obp"] = df.apply(lambda row: (row["h"] + row["bb"] + row["hbp"]) / (row["ab"] + row["bb"] + row["hbp"] + row["sf"]) if (row["ab"] + row["bb"] + row["hbp"] + row["sf"]) > 0 else 0, axis=1)
        df["slg"] = df.apply(lambda row: row["total_bases"] / row["ab"] if row["ab"] > 0 else 0, axis=1)
        df["ops"] = df["obp"] + df["slg"]
        df["pa"] = df["ab"] + df["bb"] + df["hbp"] + df["sf"] + df["sh"]

        if not df_war_history.empty:
            df = df.merge(df_war_history, left_on='yearid', right_on='year_ID', how='left')
            df['war'] = df['war'].fillna(0)
        else:
            df['war'] = 0

        df_result = df[[
            "yearid", "teamid", "g", "pa","ab", "h", "hr", "rbi", "sb",
            "bb", "hbp", "sf", "2b", "3b", "ba", "obp", "slg", "ops", "war"
        ]].rename(columns={
            "yearid": "year", "g": "games", "ab": "at_bats", "h": "hits", 
            "hr": "home_runs", "rbi": "rbi", "sb": "stolen_bases", "bb": "walks",
            "hbp": "hit_by_pitch", "sf": "sacrifice_flies", "2b": "doubles", "3b": "triples"
        })

        return jsonify({
            "mode": "season",
            "player_type": "hitter",
            "stats": df_result.to_dict(orient="records"),
            "photo_url": photo_url
        })

    elif mode == "live":
        if live_row.empty:
            return jsonify({"error": "No live batting stats found for current season"}), 404

        live_stats = live_row.to_dict(orient="records")[0]

        war_value = 0
        for war_col in ['WAR', 'war', 'War', 'fWAR', 'bWAR', 'rWAR']:
            if war_col in live_stats and not pd.isna(live_stats[war_col]):
                war_value = float(live_stats[war_col])
                break
        
        ba_value = 0
        for ba_col in ['AVG', 'BA', 'avg', 'ba']:
            if ba_col in live_stats and not pd.isna(live_stats[ba_col]):
                ba_value = float(live_stats[ba_col])
                break
        
        ops_plus_value = 0
        for ops_plus_col in ['OPS+', 'OPS_plus', 'wRC+', 'ops_plus']:
            if ops_plus_col in live_stats and not pd.isna(live_stats[ops_plus_col]):
                ops_plus_value = int(float(live_stats[ops_plus_col]))
                break

        result = {
            "war": round(war_value, 1),
            "games": int(live_stats.get("G", 0)),
            "plate_appearances": int(live_stats.get("PA", 0)),
            "hits": int(live_stats.get("H", 0)),
            "home_runs": int(live_stats.get("HR", 0)),
            "rbi": int(live_stats.get("RBI", 0)),
            "stolen_bases": int(live_stats.get("SB", 0)),
            "batting_average": round(ba_value, 3),
            "on_base_percentage": round(float(live_stats.get("OBP", 0)), 3),
            "slugging_percentage": round(float(live_stats.get("SLG", 0)), 3),
            "ops": round(float(live_stats.get("OPS", 0)), 3),
            "ops_plus": ops_plus_value
        }

        return jsonify({
            "mode": "live",
            "player_type": "hitter",
            "stats": result,
            "photo_url": photo_url
        })

    elif mode == "combined":
        if df_lahman.empty:
            return jsonify({"error": "No career batting stats found"}), 404

        totals = df_lahman.agg({
            "g": "sum", "ab": "sum", "h": "sum", "hr": "sum", "rbi": "sum",
            "sb": "sum", "bb": "sum", "hbp": "sum", "sf": "sum", "sh": "sum", "2b": "sum", "3b": "sum"
        }).to_dict()

        career_war = get_career_war(playerid)

        current_season_war = 0
        if not live_row.empty:
            live_stats = live_row.to_dict(orient="records")[0]
            totals["g"] += int(live_stats.get("G", 0))
            totals["ab"] += int(live_stats.get("AB", 0))
            totals["h"] += int(live_stats.get("H", 0))
            totals["hr"] += int(live_stats.get("HR", 0))
            totals["rbi"] += int(live_stats.get("RBI", 0))
            totals["sb"] += int(live_stats.get("SB", 0))
            totals["bb"] += int(live_stats.get("BB", 0))
            totals["hbp"] += int(live_stats.get("HBP", 0))
            totals["sf"] += int(live_stats.get("SF", 0))
            totals["sh"] += int(live_stats.get("SH", 0))
            totals["2b"] += int(live_stats.get("2B", 0))
            totals["3b"] += int(live_stats.get("3B", 0))

            for war_col in ['WAR', 'war', 'War', 'fWAR', 'bWAR', 'rWAR']:
                if war_col in live_stats and not pd.isna(live_stats[war_col]):
                    current_season_war = float(live_stats[war_col])
                    break

        singles = totals["h"] - totals["2b"] - totals["3b"] - totals["hr"]
        total_bases = singles + 2*totals["2b"] + 3*totals["3b"] + 4*totals["hr"]
        ba = totals["h"] / totals["ab"] if totals["ab"] > 0 else 0
        obp_denominator = totals["ab"] + totals["bb"] + totals["hbp"] + totals["sf"]
        obp = (totals["h"] + totals["bb"] + totals["hbp"]) / obp_denominator if obp_denominator > 0 else 0
        slg = total_bases / totals["ab"] if totals["ab"] > 0 else 0
        ops = obp + slg

        plate_appearances = totals["ab"] + totals["bb"] + totals["hbp"] + totals["sf"] + totals["sh"]

        combined_war = career_war + current_season_war

        ops_plus = 0
        if not live_row.empty:
            for ops_plus_col in ['OPS+', 'OPS_plus', 'wRC+', 'ops_plus']:
                if ops_plus_col in live_stats and not pd.isna(live_stats[ops_plus_col]):
                    ops_plus = int(float(live_stats[ops_plus_col]))
                    break

        result = {
            "war": round(combined_war, 1),
            "games": int(totals["g"]),
            "plate_appearances": int(plate_appearances),
            "hits": int(totals["h"]),
            "home_runs": int(totals["hr"]),
            "rbi": int(totals["rbi"]),
            "stolen_bases": int(totals["sb"]),
            "batting_average": round(ba, 3),
            "on_base_percentage": round(obp, 3),
            "slugging_percentage": round(slg, 3),
            "ops": round(ops, 3),
            "ops_plus": ops_plus
        }

        return jsonify({
            "mode": "combined",
            "player_type": "hitter",
            "totals": result,
            "photo_url": photo_url
        })

    else:
        return jsonify({"error": "Invalid mode"}), 400
    
def get_live_stats_name_variations(first, last):
    """Generate name variations for live stats lookup"""
    variations = []
    
    # Base name
    variations.append((first, last))
    
    # Common Jr/Sr name patterns for live stats
    name_mappings = {
        # Key: (database_first, database_last) -> Live stats name variations
        ('fernando', 'tatis'): [
            'Fernando Tatis Jr.', 'Fernando Tatis', 'F. Tatis Jr.', 'Tatis Jr.'
        ],
        ('ken', 'griffey'): [
            'Ken Griffey Jr.', 'Ken Griffey', 'K. Griffey Jr.', 'Griffey Jr.'
        ],
        ('cal', 'ripken'): [
            'Cal Ripken Jr.', 'Cal Ripken', 'C. Ripken Jr.', 'Ripken Jr.'
        ],
        ('tim', 'raines'): [
            'Tim Raines Jr.', 'Tim Raines', 'T. Raines Jr.', 'Raines Jr.'
        ],
        ('sandy', 'alomar'): [
            'Sandy Alomar Jr.', 'Sandy Alomar', 'S. Alomar Jr.', 'Alomar Jr.'
        ],
        ('pete', 'rose'): [
            'Pete Rose Jr.', 'Pete Rose', 'P. Rose Jr.', 'Rose Jr.'
        ]
    }
    
    # Check if this is a known Jr/Sr case
    key = (first.lower(), last.lower())
    if key in name_mappings:
        return name_mappings[key]
    
    # General patterns to try
    base_patterns = [
        f"{first} {last}",
        f"{first} {last} Jr.",
        f"{first} {last} Sr.",
        f"{first[0]}. {last}",
        f"{first[0]}. {last} Jr.",
        f"{first[0]}. {last} Sr.",
        f"{last}",
        f"{last} Jr.",
        f"{last} Sr."
    ]
    
    return base_patterns

def find_live_player_match(df_live, first, last):
    """Find matching player in live stats with various name patterns"""
    if df_live.empty:
        return pd.DataFrame()
    
    # Clean the Name column
    df_live['Name'] = df_live['Name'].str.strip()
    df_live['Name_lower'] = df_live['Name'].str.lower()
    
    # Get name variations to try
    name_variations = get_live_stats_name_variations(first, last)
    
    # Try each variation
    for name_pattern in name_variations:
        # Exact match
        exact_match = df_live[df_live['Name_lower'] == name_pattern.lower()]
        if not exact_match.empty:
            return exact_match.head(1)
        
        # Partial match (contains)
        partial_match = df_live[df_live['Name_lower'].str.contains(name_pattern.lower(), na=False)]
        if not partial_match.empty:
            # If multiple matches, try to find the best one
            if len(partial_match) == 1:
                return partial_match.head(1)
            else:
                # Prefer exact matches in the partial results
                for _, row in partial_match.iterrows():
                    if name_pattern.lower() in row['Name_lower']:
                        return partial_match[partial_match['Name'] == row['Name']].head(1)
    
    # Last resort: fuzzy matching on last name only
    last_name_matches = df_live[df_live['Name_lower'].str.contains(last.lower(), na=False)]
    if not last_name_matches.empty:
        # Try to find one that also contains first name or first initial
        for _, row in last_name_matches.iterrows():
            name_lower = row['Name_lower']
            if (first.lower() in name_lower or 
                f"{first[0].lower()}." in name_lower or
                f"{first[0].lower()} " in name_lower):
                return last_name_matches[last_name_matches['Name'] == row['Name']].head(1)
        
        # If no first name match, return the first last name match
        return last_name_matches.head(1)
    
    return pd.DataFrame()



if __name__ == "__main__":
    app.run(debug=True)
