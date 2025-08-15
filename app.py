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

def get_photo_url_for_player(playerid, conn):
    """Get photo URL using the correct player info from database"""
    try:
        # Get the actual names and debut info from the database for this specific playerid
        cursor = conn.cursor()
        cursor.execute("""
            SELECT namefirst, namelast, debut, finalgame, birthyear 
            FROM lahman_people WHERE playerid = ?
        """, (playerid,))
        name_result = cursor.fetchone()
        
        if not name_result:
            print(f"No name found for playerid: {playerid}")
            return None
            
        db_first, db_last, debut, final_game, birth_year = name_result
        print(f"Getting photo for playerid: {playerid}, Database name: {db_first} {db_last}, Debut: {debut}")
        
        # Special handling for known tricky cases with direct MLB ID mappings
        direct_mlb_mappings = {
            # Format: playerid -> (search_name, mlb_id)
            'griffke01': ('Ken Griffey', None),         # Sr. - let lookup handle it
            'griffke02': ('Ken Griffey Jr.', None),     # Jr. - let lookup handle it
            'tatisfe01': ('Fernando Tatis', 123107),    # Sr. with direct MLB ID
            'tatisfe02': ('Fernando Tatis Jr.', 665487), # Jr. with direct MLB ID
            'ripkeca99': ('Cal Ripken Sr.', None),      # Sr. - was mostly coach/manager
            'ripkeca01': ('Cal Ripken Jr.', 121222),    # Jr. with direct MLB ID
            'raineti01': ('Tim Raines', 120891),        # Sr. with direct MLB ID
            'raineti02': ('Tim Raines Jr.', 406428),    # Jr. with direct MLB ID
            'alomasa01': ('Sandy Alomar Sr.', None),    # Sr.
            'alomasa02': ('Sandy Alomar Jr.', None),    # Jr.
            'rosepe01': ('Pete Rose', None),            # Sr. - let lookup handle it
            'rosepe02': ('Pete Rose Jr.', 121453),      # Jr. with direct MLB ID
            'baezja01': ('Javier Baez', 595879)      # Direct MLB ID for Baez
        }
        
        # Check if we have a direct mapping for this player
        if playerid in direct_mlb_mappings:
            search_name, direct_mlb_id = direct_mlb_mappings[playerid]
            print(f"Using direct mapping for {playerid}: {search_name}")
            
            # If we have a direct MLB ID, use it
            if direct_mlb_id:
                photo_url = f"https://img.mlbstatic.com/mlb-photos/image/upload/v1/people/{direct_mlb_id}/headshot/67/current.jpg"
                print(f"Using direct MLB ID {direct_mlb_id}: {photo_url}")
                return photo_url
        else:
            # Not a known special case, use database names
            search_name = f"{db_first} {db_last}"
        
        # For cases without direct MLB ID, do the lookup
        mlb_id = None
        try:
            print(f"Looking up MLB ID for: {search_name}")
            
            # Split the search name for the lookup function
            name_parts = search_name.replace(' Jr.', '').replace(' Sr.', '').replace(' III', '').replace(' II', '').split()
            lookup_first = name_parts[0]
            lookup_last = ' '.join(name_parts[1:])
            
            print(f"Lookup parts: first='{lookup_first}', last='{lookup_last}'")
            lookup = playerid_lookup(lookup_last, lookup_first)
            print(f"Lookup result shape: {lookup.shape if not lookup.empty else 'Empty'}")
            
            if not lookup.empty:
                print(f"Lookup results: {lookup[['name_last', 'name_first', 'key_mlbam', 'mlb_played_first', 'mlb_played_last']].to_dict('records')}")
                
                # For father/son cases, try to match by career years
                best_match = None
                if len(lookup) > 1:
                    debut_year = int(debut[:4]) if debut else None
                    final_year = int(final_game[:4]) if final_game else None
                    
                    for _, row in lookup.iterrows():
                        if pd.isna(row['key_mlbam']):
                            continue
                            
                        mlb_first = row.get('mlb_played_first')
                        mlb_last = row.get('mlb_played_last')
                        
                        # Try to match by career overlap
                        if debut_year and mlb_first and mlb_last:
                            mlb_first_year = int(mlb_first) if mlb_first else None
                            mlb_last_year = int(mlb_last) if mlb_last else None
                            
                            if (mlb_first_year and abs(mlb_first_year - debut_year) <= 1 and
                                mlb_last_year and final_year and abs(mlb_last_year - final_year) <= 1):
                                best_match = row
                                print(f"Found career year match: {mlb_first_year}-{mlb_last_year} vs {debut_year}-{final_year}")
                                break
                
                # Use best match or first available
                target_row = best_match if best_match is not None else lookup.iloc[0]
                
                if not pd.isna(target_row['key_mlbam']):
                    mlb_id = int(target_row['key_mlbam'])
                    print(f"Found MLB ID: {mlb_id}")
                else:
                    print("MLB ID is NaN")
            else:
                print("No lookup results found")
                
        except Exception as e:
            print(f"MLB ID lookup failed for {search_name}: {e}")

        if mlb_id:
            photo_url = f"https://img.mlbstatic.com/mlb-photos/image/upload/v1/people/{mlb_id}/headshot/67/current.jpg"
            print(f"Generated photo URL: {photo_url}")
            return photo_url
        
        print("No MLB ID found, returning None")
        return None
        
    except Exception as e:
        print(f"Error getting photo URL for playerid {playerid}: {e}")
        return None
    
def get_world_series_championships(playerid, conn):
    """Get World Series championships for a player"""
    try:
        cursor = conn.cursor()
        
        
        # Method 1: Check if player's team won World Series in years they played
        ws_query = """
        SELECT DISTINCT b.yearid, b.teamid, s.name as team_name
        FROM lahman_batting b
        JOIN lahman_seriespost sp ON b.yearid = sp.yearid AND b.teamid = sp.teamidwinner
        LEFT JOIN lahman_teams s ON b.teamid = s.teamid AND b.yearid = s.yearid
        WHERE b.playerid = ? AND sp.round = 'WS'
        
        UNION
        
        SELECT DISTINCT p.yearid, p.teamid, s.name as team_name
        FROM lahman_pitching p
        JOIN lahman_seriespost sp ON p.yearid = sp.yearid AND p.teamid = sp.teamidwinner
        LEFT JOIN lahman_teams s ON p.teamid = s.teamid AND p.yearid = s.yearid
        WHERE p.playerid = ? AND sp.round = 'WS'
        
        ORDER BY 1 DESC
        """
        
        cursor.execute(ws_query, (playerid, playerid))
        ws_results = cursor.fetchall()
        
        championships = []
        for row in ws_results:
            year, team_id, team_name = row
            championships.append({
                'year': year,
                'team': team_id,
                'team_name': team_name or team_id
            })
        
       
        
        return championships
        
    except Exception as e:
        print(f"Error getting World Series championships: {e}")
        # Fallback: check awards table for WS entries
        try:
            cursor.execute("""
                SELECT yearid, notes
                FROM lahman_awardsplayers 
                WHERE playerid = ? AND awardid = 'WS'
                ORDER BY yearid DESC
            """, (playerid,))
            
            fallback_results = cursor.fetchall()
            championships = []
            for year, notes in fallback_results:
                championships.append({
                    'year': year,
                    'team': 'Unknown',
                    'team_name': notes or 'World Series Champion'
                })
            
            return championships
            
        except Exception as e2:
            print(f"Fallback WS lookup also failed: {e2}")
            return []


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


        

def get_player_awards(playerid, conn):
    """Get all awards for a player from the lahman database"""
    try:
        print(f"Getting awards for playerid: {playerid}")
        cursor = conn.cursor()
        
        # print(f"DEBUG: Raw playerid from route: '{playerid}'", repr(playerid))

        # Query for all awards
        awards_query = """
        SELECT yearid, awardid, lgid, tie, notes
        FROM lahman_awardsplayers 
        WHERE playerid = ?
        ORDER BY yearid DESC, awardid
        """
        
        cursor.execute(awards_query, (playerid,))
        awards_data = cursor.fetchall()
        
        print(f"Found {len(awards_data)} award records for playerid {playerid}")
        
        awards = []
        for row in awards_data:
            year, award_id, league, tie, notes = row
            
            # Format award name for display
            award_display = format_award_name(award_id)
            
            award_info = {
                'year': year,
                'award': award_display,
                'award_id': award_id,
                'league': league,
                'tie': bool(tie) if tie else False,
                'notes': notes
            }
            awards.append(award_info)
            print(f"  Award: {award_id} ({award_display}) in {year}")
        
        # Group and summarize awards
        award_summary = summarize_awards(awards)
        print(f"Award summary: {award_summary}")
        
        #Get MLB All-Star Game appearances:
        allstar_games = get_allstar_appearances(playerid, conn)
        print(f"MLB All-Star Game appearances: {allstar_games}")

        #Get world series championships
        ws_championships = get_world_series_championships(playerid, conn)
        print(f"World Series championships: {ws_championships}")

        
        return {
            'awards': awards,
            'summary': award_summary,
            'mlbAllStar': allstar_games,
            'world_series_championships': ws_championships,
            'ws_count': len(ws_championships)
        }

    except Exception as e:
        print(f"Error getting player awards: {e}")
        return {
            'awards': [],
            'summary': {},
            'mlbAllStar': [],
            'world_series_championships': [],
            'ws_count': 0
        }

def format_award_name(award_id):
    """Convert award IDs to readable names"""
    award_names = {
        'MVP': 'Most Valuable Player',
        'CYA': 'Cy Young Award',  
        'CY': 'Cy Young Award',
        'ROY': 'Rookie of the Year',
        'GG': 'Gold Glove',
        'SS': 'Silver Slugger',
        'AS': 'TSN All-Star Team',
        'WSMVP': 'World Series MVP',
        'WS': 'World Series Champion',
        'ALCS MVP': 'ALCS MVP',
        'NLCS MVP': 'NLCS MVP', 
        'ASG MVP': 'All-Star Game MVP',
        'ASGMVP': 'All-Star Game MVP',
        'COMEB': 'Comeback Player of the Year',
        'Hutch': 'Hutch Award',
        'Lou Gehrig': 'Lou Gehrig Memorial Award',
        'Babe Ruth': 'Babe Ruth Award',
        'Roberto Clemente': 'Roberto Clemente Award',
        'Branch Rickey': 'Branch Rickey Award', 
        'Hank Aaron': 'Hank Aaron Award',
        'DHL Hometown Hero': 'DHL Hometown Hero',
        'Edgar Martinez': 'Edgar Martinez Outstanding DH Award',
        'Hutch Award': 'Hutch Award',
        'Man of the Year': 'Man of the Year',
        'Players Choice': 'Players Choice Award',
        'Reliever': 'Reliever of the Year',
        'TSN Fireman': 'The Sporting News Fireman Award',
        'TSN MVP': 'The Sporting News MVP',
        'TSN Pitcher': 'The Sporting News Pitcher of the Year', 
        'TSN Player': 'The Sporting News Player of the Year',
        'TSN Rookie': 'The Sporting News Rookie of the Year'
    }
    
    return award_names.get(award_id, award_id)


def summarize_awards(awards):
    """Create summary statistics for awards"""
    summary = {}
    
    print(f"Summarizing {len(awards)} awards")
    
    # Count by award type
    for award in awards:
        award_id = award['award_id']
        if award_id not in summary:
            summary[award_id] = {
                'count': 0,
                'years': [],
                'display_name': award['award']
            }
        summary[award_id]['count'] += 1
        summary[award_id]['years'].append(award['year'])
        print(f"  Added {award_id}: now {summary[award_id]['count']} total")
    
    # Sort years for each award
    for award_id in summary:
        summary[award_id]['years'].sort(reverse=True)
    
    print(f"Final summary: {summary}")
    return summary

def get_allstar_appearances(playerid, conn):
    """Get MLB All-Star Game appearances from AllstarFull table"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as allstar_games
            FROM lahman_allstarfull 
            WHERE playerid = ?
        """, (playerid,))
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception as e:
        print(f"Error getting All-Star appearances: {e}")
        return 0
    
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
    photo_url = get_photo_url_for_player(playerid, conn)

    # Process stats based on final type
    if final_type == "pitcher":
        return handle_pitcher_stats(playerid, conn, mode, photo_url, first, last)
    else:
        conn.close()
        return handle_hitter_stats(playerid, mode, photo_url, first, last)

@app.route('/search-players')
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
    print(f"Looking up player: {name}")
    
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
    photo_url = get_photo_url_for_player(playerid, conn)

    if player_type == "pitcher":
        return handle_pitcher_stats(playerid, conn, mode, photo_url, first, last)
    else:
        conn.close()
        return handle_hitter_stats(playerid, mode, photo_url, first, last)
    
@app.route('/popular-players')
def popular_players():
    fallback_players = [
        "Mike Trout", "Aaron Judge", "Mookie Betts", "Ronald Acuña",
        "Juan Soto", "Vladimir Guerrero Jr.", "Fernando Tatis Jr.", 
        "Gerrit Cole", "Jacob deGrom", "Tarik Skubal", "Spencer Strider",
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

    #get player photo
    photo_url = get_photo_url_for_player(playerid, conn)

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
    
    # get awards for this player
    awards_data = get_player_awards(playerid, conn)

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

        conn.close()
        return jsonify({
            "mode": "career",
            "player_type": "pitcher",
            "totals": result,
            "photo_url": photo_url,
            "awards": awards_data
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
            "photo_url": photo_url,
            "awards": awards_data
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
            "photo_url": photo_url,
            "awards": awards_data
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
            "photo_url": photo_url,
            "awards": awards_data
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

    awards_data = get_player_awards(playerid, conn)
    
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

        conn.close()
        return jsonify({
            "mode": "career",
            "player_type": "hitter",
            "totals": result,
            "photo_url": photo_url,
            "awards": awards_data
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
            "photo_url": photo_url,
            "awards": awards_data
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
            "photo_url": photo_url,
            "awards": awards_data
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
            "photo_url": photo_url,
            "awards": awards_data
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

# Team Stats Mode - Fixed with correct lahman_teams table name
@app.route("/team")
def get_team_stats():
    try:
        team = request.args.get("team", "").strip()
        mode = request.args.get("mode", "season").lower()
        stat_type = request.args.get("stat_type", "batting").lower()
        
        print(f"Team endpoint called with: team='{team}', mode='{mode}', stat_type='{stat_type}'")
        
        if not team:
            return jsonify({"error": "Enter team"}), 400
        
        team_id, year = parse_team_input(team)
        print(f"Parsed: team_id='{team_id}', year={year}")
        
        if stat_type == "batting":
            return handle_team_batting_stats(team_id, year, mode)
        elif stat_type == "pitching":
            return handle_team_pitching_stats(team_id, year, mode)
        else:
            return jsonify({"error": "Invalid stat type"}), 400
            
    except Exception as e:
        print(f"Error in get_team_stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

def get_team_code_from_search(search_term):
    """
    Convert team search terms (full names, cities, nicknames) to database team codes
    Returns the team code that should be used in database queries
    """
    search_term = search_term.lower().strip()
    
    # Direct team code mappings (if they search the exact code)
    team_codes = {
        # Angels - various historical codes
        'alt': 'ALT',    # Early Angels
        'cal': 'CAL',    # California Angels  
        'ana': 'ANA',    # Anaheim Angels
        'laa': 'LAA',    # Los Angeles Angels (current)
        
        # Diamondbacks
        'ari': 'ARI', 
        
        # Braves - historical codes
        'bsn': 'BSN',    # Boston Braves (historical)
        'ml1': 'ML1',    # Milwaukee Braves (historical) 
        'mla': 'MLA',    # Another Milwaukee code
        'atl': 'ATL',    # Atlanta Braves (current)
        
        # Orioles - historical St. Louis Browns
        'sla': 'SLA',    # St. Louis Browns (historical)
        'bal': 'BAL',    # Baltimore Orioles (current)
        
        # Red Sox
        'bs1': 'BS1',    # Historical Boston code
        'bos': 'BOS',    # Boston Red Sox (current)
        
        # Cubs
        'chn': 'CHN',    # Chicago Cubs (historical database code)
        'chc': 'CHC',    # Chicago Cubs (modern)
        
        # White Sox  
        'cha': 'CHA',    # Chicago White Sox (historical database code)
        'chw': 'CWS',    # Map CHW to CWS
        'cws': 'CWS',    # Chicago White Sox (current)
        
        # Reds
        'cn2': 'CN2',    # Historical Cincinnati code
        'cn3': 'CN3',    # Another historical Cincinnati code  
        'cin': 'CIN',    # Cincinnati Reds (current)
        
        # Indians/Guardians
        'cle': 'CLE',    # Cleveland (current - covers both Indians and Guardians)
        
        # Rockies
        'col': 'COL',
        
        # Tigers
        'det': 'DET',
        
        # Astros
        'hou': 'HOU',
        
        # Royals
        'kca': 'KCR',    # Map old code to current
        'kcr': 'KCR',    # Kansas City Royals
        
        # Dodgers
        'br1': 'BR1',    # Brooklyn Dodgers (very old)
        'br2': 'BR2',    # Brooklyn Dodgers (historical)  
        'br4': 'BR4',    # Brooklyn Dodgers (another historical)
        'bro': 'BRO',    # Brooklyn (if it exists)
        'lad': 'LAN',    # Map LAD to LAN (database uses LAN)
        'lan': 'LAN',    # Los Angeles Dodgers (database code)
        
        # Marlins
        'fla': 'FLA',    # Florida Marlins (historical)
        'mia': 'MIA',    # Miami Marlins (current)
        
        # Brewers
        'mil': 'MIL',
        
        # Twins
        'min': 'MIN',
        
        # Mets
        'nym': 'NYM',
        
        # Yankees
        'nyy': 'NYY',
        
        # Athletics
        'pha': 'PHA',    # Philadelphia Athletics (historical)
        'oak': 'OAK',    # Oakland Athletics (current)
        
        # Phillies
        'phn': 'PHN',    # Historical Philadelphia code
        'ph3': 'PH3',    # Another historical Philadelphia code
        'phi': 'PHI',    # Philadelphia Phillies (current)
        
        # Pirates
        'pit': 'PIT',
        
        # Padres
        'sdp': 'SDP',    # San Diego Padres (database code)
        'sd': 'SDP',     # Map SD to SDP
        
        # Mariners
        'sea': 'SEA',
        
        # Giants
        'ny1': 'NY1',    # New York Giants (historical, if it exists)
        'sfg': 'SFG',    # San Francisco Giants (database code)
        'sf': 'SFG',     # Map SF to SFG
        
        # Cardinals
        'stl': 'STL',
        
        # Rays
        'tbd': 'TBR',    # Map old code to current
        'tbr': 'TBR',    # Tampa Bay Rays
        'tb': 'TBR',     # Map TB to TBR
        
        # Rangers
        'was': 'WAS',    # Washington Senators (historical, became Rangers)
        'tex': 'TEX',    # Texas Rangers (current)
        
        # Blue Jays
        'tor': 'TOR',
        
        # Nationals
        'mon': 'MON',    # Montreal Expos (historical)
        'wsn': 'WSN',    # Washington Nationals (current)
        'was': 'WSN'     # Map WAS to WSN for Nationals
    }
    
    # Check if it's a direct team code match
    if search_term in team_codes:
        return team_codes[search_term]
    
    # Full team name and city mappings (keep your existing mappings)
    name_mappings = {
        # Angels
        'angels': 'LAA',
        'los angeles angels': 'LAA', 
        'anaheim angels': 'ANA',      # Use historical code for historical name
        'california angels': 'CAL',   # Use historical code for historical name
        
        # Diamondbacks  
        'diamondbacks': 'ARI',
        'arizona diamondbacks': 'ARI',
        'd-backs': 'ARI',
        'dbacks': 'ARI',
        
        # Braves
        'braves': 'ATL',
        'atlanta braves': 'ATL',
        'atlanta': 'ATL',
        'boston braves': 'BSN',       # Historical
        'milwaukee braves': 'ML1',    # Historical
        
        # Orioles
        'orioles': 'BAL',
        'baltimore orioles': 'BAL',
        'baltimore': 'BAL',
        'o\'s': 'BAL',
        'st. louis browns': 'SLA',    # Historical
        'st louis browns': 'SLA',
        'browns': 'SLA',
        
        # Red Sox
        'red sox': 'BOS',
        'boston red sox': 'BOS',
        'boston': 'BOS',
        'redsox': 'BOS',
        
        # Cubs
        'cubs': 'CHN',               # Use historical database code
        'chicago cubs': 'CHN',
        'cubbies': 'CHN',
        
        # White Sox
        'white sox': 'CHA',          # Use historical database code
        'chicago white sox': 'CHA',
        'whitesox': 'CHA',
        
        # Reds
        'reds': 'CIN',
        'cincinnati reds': 'CIN',
        'cincinnati': 'CIN',
        
        # Guardians/Indians
        'guardians': 'CLE',
        'cleveland guardians': 'CLE',
        'cleveland': 'CLE',
        'indians': 'CLE',
        'cleveland indians': 'CLE',
        
        # Rockies
        'rockies': 'COL',
        'colorado rockies': 'COL',
        'colorado': 'COL',
        
        # Tigers
        'tigers': 'DET',
        'detroit tigers': 'DET',
        'detroit': 'DET',
        
        # Astros
        'astros': 'HOU',
        'houston astros': 'HOU',
        'houston': 'HOU',
        
        # Royals
        'royals': 'KCR',
        'kansas city royals': 'KCR',
        'kansas city': 'KCR',
        
        # Dodgers
        'dodgers': 'LAN',
        'los angeles dodgers': 'LAN',
        'brooklyn dodgers': 'BR2',    # Use historical code for historical name
        
        # Marlins
        'marlins': 'MIA',
        'miami marlins': 'MIA',
        'florida marlins': 'FLA',     # Use historical code for historical name
        'miami': 'MIA',
        
        # Brewers
        'brewers': 'MIL',
        'milwaukee brewers': 'MIL',
        'milwaukee': 'MIL',
        
        # Twins
        'twins': 'MIN',
        'minnesota twins': 'MIN',
        'minnesota': 'MIN',
        
        # Mets
        'mets': 'NYM',
        'new york mets': 'NYM',
        'ny mets': 'NYM',
        
        # Yankees
        'yankees': 'NYY',
        'new york yankees': 'NYY',
        'ny yankees': 'NYY',
        'yanks': 'NYY',
        
        # Athletics
        'athletics': 'OAK',
        'oakland athletics': 'OAK',
        'oakland': 'OAK',
        'a\'s': 'OAK',
        'as': 'OAK',
        'philadelphia athletics': 'PHA',  # Historical
        
        # Phillies
        'phillies': 'PHI',
        'philadelphia phillies': 'PHI',
        'philadelphia': 'PHI',
        'phils': 'PHI',
        
        # Pirates
        'pirates': 'PIT',
        'pittsburgh pirates': 'PIT',
        'pittsburgh': 'PIT',
        'bucs': 'PIT',
        
        # Padres
        'padres': 'SDP',
        'san diego padres': 'SDP',
        'san diego': 'SDP',
        
        # Mariners
        'mariners': 'SEA',
        'seattle mariners': 'SEA',
        'seattle': 'SEA',
        'm\'s': 'SEA',
        
        # Giants
        'giants': 'SFG',
        'san francisco giants': 'SFG',
        'sf giants': 'SFG',
        'san francisco': 'SFG',
        
        # Cardinals
        'cardinals': 'STL',
        'st. louis cardinals': 'STL',
        'st louis cardinals': 'STL',
        'cards': 'STL',
        'st. louis': 'STL',
        'st louis': 'STL',
        
        # Rays
        'rays': 'TBR',
        'tampa bay rays': 'TBR',
        'tampa bay': 'TBR',
        'devil rays': 'TBD',         # Use historical code for historical name
        'tampa bay devil rays': 'TBD',
        
        # Rangers
        'rangers': 'TEX',
        'texas rangers': 'TEX',
        'texas': 'TEX',
        'washington senators': 'WAS', # Historical (became Rangers)
        'senators': 'WAS',
        
        # Blue Jays
        'blue jays': 'TOR',
        'toronto blue jays': 'TOR',
        'toronto': 'TOR',
        'jays': 'TOR',
        'bluejays': 'TOR',
        
        # Nationals
        'nationals': 'WSN',
        'washington nationals': 'WSN',
        'washington': 'WSN',
        'nats': 'WSN',
        'expos': 'MON',              # Historical Montreal Expos
        'montreal expos': 'MON'
    }
    
    # Check for exact match first
    if search_term in name_mappings:
        return name_mappings[search_term]
    
    # Check for partial matches (contains)
    for name, code in name_mappings.items():
        if search_term in name or name in search_term:
            return code
    
    # If no match found, return the original search term uppercased
    return search_term.upper()

def parse_team_input(team):
    """Parse team input like '2024 Dodgers', 'Dodgers 2024', 'Yankees', etc."""
    try:
        parts = team.strip().split()
        
        if len(parts) == 1:
            # Just team name/code - return None for year (will be handled by mode)
            team_code = get_team_code_from_search(parts[0])
            return team_code, None  # Changed from 2024 to None
            
        elif len(parts) == 2:
            # Year and team, or team with two words
            if parts[0].isdigit():
                # Format: "2024 Dodgers"
                team_code = get_team_code_from_search(parts[1])
                return team_code, int(parts[0])
            elif parts[1].isdigit():
                # Format: "Dodgers 2024"  
                team_code = get_team_code_from_search(parts[0])
                return team_code, int(parts[1])
            else:
                # Two word team name like "Los Angeles" or "New York"
                full_name = ' '.join(parts)
                team_code = get_team_code_from_search(full_name)
                return team_code, None  # Changed from 2024 to None
                
        else:
            # More than 2 parts - likely full team name with/without year
            # Check if last part is a year
            if parts[-1].isdigit() and len(parts[-1]) == 4:
                team_name = ' '.join(parts[:-1])
                team_code = get_team_code_from_search(team_name)
                return team_code, int(parts[-1])
            # Check if first part is a year
            elif parts[0].isdigit() and len(parts[0]) == 4:
                team_name = ' '.join(parts[1:])
                team_code = get_team_code_from_search(team_name)
                return team_code, int(parts[0])
            else:
                # Full team name without year
                full_name = ' '.join(parts)
                team_code = get_team_code_from_search(full_name)
                return team_code, None  # Changed from 2024 to None
        
    except Exception as e:
        print(f"Error parsing team input '{team}': {str(e)}")
        # Fallback - try to get team code from the whole input
        team_code = get_team_code_from_search(team)
        return team_code, None  # Changed from 2024 to None


def handle_team_batting_stats(team_id, year, mode):
    """Get team batting statistics - FIXED with correct column names and franchise mode"""
    try:
        conn = sqlite3.connect(DB_PATH)
        print(f"Connected to database: {DB_PATH}")
        print(f"handle_team_batting_stats called with: team_id='{team_id}', year={year}, mode='{mode}'")
        
        if mode == "season":
            # For season mode, use the provided year or default to 2024
            actual_year = year or 2024
            query = """
            SELECT yearid, teamid, g, ab, r, h, "2b", "3b", hr, bb, so, hbp, sf, sb, cs
            FROM lahman_teams 
            WHERE teamid = ? AND yearid = ?
            """
            print(f"Executing SEASON query with params: ({team_id}, {actual_year})")
            df = pd.read_sql_query(query, conn, params=(team_id, actual_year))
            
        elif mode in ["franchise", "career"]:
            # For franchise/career mode, ignore the year completely - aggregate all years
            query = """
            SELECT teamid, 
                   COUNT(*) as seasons,
                   SUM(g) as g, SUM(ab) as ab, SUM(r) as r, SUM(h) as h, 
                   SUM("2b") as "2b", SUM("3b") as "3b", SUM(hr) as hr,
                   SUM(sb) as sb, SUM(cs) as cs, SUM(bb) as bb, SUM(so) as so,
                   SUM(hbp) as hbp, SUM(sf) as sf
            FROM lahman_teams 
            WHERE teamid = ?
            GROUP BY teamid
            """
            print(f"Executing FRANCHISE/CAREER query with params: ({team_id},)")
            df = pd.read_sql_query(query, conn, params=(team_id,))
            print(f"Franchise/Career query returned {len(df)} rows")
            if not df.empty:
                print(f"Franchise data sample: seasons={df.iloc[0].get('seasons', 'N/A')}, games={df.iloc[0].get('g', 'N/A')}")
            
        elif mode == "history":
            # For history mode, get all seasons for the team
            query = """
            SELECT yearid, teamid, g, ab, r, h, "2b", "3b", hr, sb, cs, bb, so, hbp, sf,
                   w, l, rank, divwin, wcwin, lgwin, wswin, attendance
            FROM lahman_teams 
            WHERE teamid = ?
            ORDER BY yearid DESC
            """
            print(f"Executing HISTORY query with params: ({team_id},)")
            df = pd.read_sql_query(query, conn, params=(team_id,))
            
        else:
            # Default to season mode
            actual_year = year or 2024
            query = """
            SELECT yearid, teamid, g, ab, r, h, "2b", "3b", hr, sb, cs, bb, so, hbp, sf
            FROM lahman_teams 
            WHERE teamid = ? AND yearid = ?
            """
            print(f"Executing DEFAULT query with params: ({team_id}, {actual_year})")
            df = pd.read_sql_query(query, conn, params=(team_id, actual_year))
            
        conn.close()
        print(f"Query returned {len(df)} rows")
        
        if df.empty:
            if mode in ["franchise", "career"]:
                return jsonify({"error": f"Team '{team_id}' not found in database"}), 404
            else:
                actual_year = year or 2024
                return jsonify({"error": f"Team '{team_id}' not found for year {actual_year}"}), 404
        
        # Debug: Print raw data
        if not df.empty:
            print(f"Raw data sample: {df.iloc[0].to_dict()}")
        
        # Calculate derived stats
        df = calculate_team_batting_stats(df)
        
        return format_team_response(df, "batting", mode, team_id, year)
        
    except Exception as e:
        print(f"Error in handle_team_batting_stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    
def calculate_team_batting_stats(df):
    """Calculate batting averages, OBP, SLG, etc. - FIXED"""
    try:
        # Convert column names to lowercase to match database
        df.columns = df.columns.str.lower()
        
        # Handle missing columns with defaults - using lowercase names
        required_cols = ['ab', 'h', 'bb', 'hbp', 'sf', '2b', '3b', 'hr', 'r']
        for col in required_cols:
            if col not in df.columns:
                print(f"Missing column {col}, setting to 0")
                df[col] = 0
        
        # Fill NaN values with 0 and ensure numeric types
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        print(f"After conversion - AB: {df['ab'].iloc[0]}, H: {df['h'].iloc[0]}")
        
        # Calculate batting average
        df["ba"] = df.apply(lambda row: row["h"] / row["ab"] if row["ab"] > 0 else 0, axis=1)
        
        # Calculate on-base percentage
        df["obp"] = df.apply(lambda row: 
            (row["h"] + row["bb"] + row["hbp"]) / 
            (row["ab"] + row["bb"] + row["hbp"] + row["sf"]) 
            if (row["ab"] + row["bb"] + row["hbp"] + row["sf"]) > 0 else 0, axis=1)
        
        # Calculate singles and total bases
        df["singles"] = df["h"] - df["2b"] - df["3b"] - df["hr"]
        df["total_bases"] = df["singles"] + 2*df["2b"] + 3*df["3b"] + 4*df["hr"]
        
        # Calculate slugging percentage
        df["slg"] = df.apply(lambda row: row["total_bases"] / row["ab"] if row["ab"] > 0 else 0, axis=1)
        
        # Calculate OPS
        df["ops"] = df["obp"] + df["slg"]
        
        # Add RBI if available (not in your sample but might exist)
        if 'rbi' not in df.columns:
            df['rbi'] = 0  # Placeholder
        
        print(f"Calculated stats - BA: {df['ba'].iloc[0]:.3f}, OPS: {df['ops'].iloc[0]:.3f}")
        
        return df
        
    except Exception as e:
        print(f"Error calculating batting stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return df


def handle_team_pitching_stats(team_id, year, mode):
    """Get team pitching statistics - FIXED with correct column names and franchise mode"""
    try:
        conn = sqlite3.connect(DB_PATH)
        print(f"handle_team_pitching_stats called with: team_id='{team_id}', year={year}, mode='{mode}'")
        
        if mode == "season":
            # For season mode, use the provided year or default to 2024
            actual_year = year or 2024
            query = """
            SELECT yearid, teamid, w, l, cg, sho, sv, ipouts, ha, er, hra, bba, soa, era
            FROM lahman_teams 
            WHERE teamid = ? AND yearid = ?
            """
            print(f"Executing SEASON pitching query with params: ({team_id}, {actual_year})")
            df = pd.read_sql_query(query, conn, params=(team_id, actual_year))
            
        elif mode in ["franchise", "career"]:
            # For franchise/career mode, ignore the year completely
            query = """
            SELECT teamid, 
                   COUNT(*) as seasons,
                   SUM(w) as w, SUM(l) as l, SUM(cg) as cg, SUM(sho) as sho, SUM(sv) as sv,
                   SUM(ipouts) as ipouts, SUM(ha) as ha, SUM(er) as er, SUM(hra) as hra, 
                   SUM(bba) as bba, SUM(soa) as soa
            FROM lahman_teams 
            WHERE teamid = ?
            GROUP BY teamid
            """
            print(f"Executing FRANCHISE/CAREER pitching query with params: ({team_id},)")
            df = pd.read_sql_query(query, conn, params=(team_id,))
            print(f"Franchise/Career pitching query returned {len(df)} rows")
            if not df.empty:
                print(f"Pitching franchise data: seasons={df.iloc[0].get('seasons', 'N/A')}, wins={df.iloc[0].get('w', 'N/A')}")
            
        elif mode == "history":
            # For history mode, ignore the year filter
            query = """
            SELECT yearid, teamid, w, l, cg, sho, sv, ipouts, ha, er, hra, bba, soa, era,
                   rank, divwin, wcwin, lgwin, wswin, attendance
            FROM lahman_teams 
            WHERE teamid = ? 
            ORDER BY yearid DESC
            """
            print(f"Executing HISTORY pitching query with params: ({team_id},)")
            df = pd.read_sql_query(query, conn, params=(team_id,))
            
        else:
            # Default to season mode
            actual_year = year or 2024
            query = """
            SELECT yearid, teamid, w, l, cg, sho, sv, ipouts, ha, er, hra, bba, soa, era
            FROM lahman_teams 
            WHERE teamid = ? AND yearid = ?
            """
            print(f"Executing DEFAULT pitching query with params: ({team_id}, {actual_year})")
            df = pd.read_sql_query(query, conn, params=(team_id, actual_year))
        
        conn.close()
        print(f"Pitching query returned {len(df)} rows")
        
        if df.empty:
            if mode in ["franchise", "career"]:
                return jsonify({"error": f"Team '{team_id}' pitching stats not found in database"}), 404
            else:
                actual_year = year or 2024
                return jsonify({"error": f"Team '{team_id}' pitching stats not found for year {actual_year}"}), 404
        
        # Calculate derived pitching stats
        df = calculate_team_pitching_stats(df)
        
        return format_team_response(df, "pitching", mode, team_id, year)
        
    except Exception as e:
        print(f"Error in handle_team_pitching_stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Pitching stats error: {str(e)}"}), 500


def calculate_team_pitching_stats(df):
    """Calculate team pitching derived stats - FIXED"""
    try:
        # Convert column names to lowercase
        df.columns = df.columns.str.lower()
        
        # Handle missing columns - using correct lowercase names
        required_cols = ['ipouts', 'er', 'ha', 'bba', 'soa', 'w', 'l']
        for col in required_cols:
            if col not in df.columns:
                print(f"Missing pitching column {col}, setting to 0")
                df[col] = 0
                
        # Fill NaN values and ensure numeric types
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Calculate innings pitched
        df["ip"] = df["ipouts"] / 3.0
        
        # Calculate ERA (recalculate to be sure)
        df["era_calc"] = df.apply(lambda row: (row["er"] * 9) / (row["ipouts"] / 3.0) if row["ipouts"] > 0 else 0, axis=1)
        
        # Calculate WHIP (using ha and bba - hits allowed and walks allowed)
        df["whip"] = df.apply(lambda row: (row["ha"] + row["bba"]) / (row["ipouts"] / 3.0) if row["ipouts"] > 0 else 0, axis=1)
        
        # Calculate K/9 and BB/9
        df["k9"] = df.apply(lambda row: (row["soa"] * 9) / (row["ipouts"] / 3.0) if row["ipouts"] > 0 else 0, axis=1)
        df["bb9"] = df.apply(lambda row: (row["bba"] * 9) / (row["ipouts"] / 3.0) if row["ipouts"] > 0 else 0, axis=1)
        
        # Rename columns to match your frontend expectations
        df = df.rename(columns={
            'ha': 'h',      # hits allowed -> H
            'bba': 'bb',    # walks allowed -> BB  
            'soa': 'so',    # strikeouts -> SO
            'hra': 'hr'     # home runs allowed -> HR
        })
        
        return df
        
    except Exception as e:
        print(f"Error calculating pitching stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return df


def format_and_round_stats(stats_dict):
    """Format and round team stats with proper decimal places and leading zero removal"""
    
    # Define which stats need special formatting
    batting_averages = ['ba', 'obp', 'slg']  # 3 decimals, no leading zero (.258)
    ops_stats = ['ops']                      # 3 decimals, no leading zero (.847)
    era_stats = ['era', 'era_calc']         # 2 decimals, keep leading zero (4.32)
    whip_stats = ['whip']                   # 3 decimals, may or may not have leading zero
    rate_stats = ['k9', 'bb9']             # 1 decimal, keep leading zero (8.5)
    ip_stats = ['ip']                       # 1 decimal, keep leading zero (162.1)
    
    formatted_stats = {}
    
    for key, value in stats_dict.items():
        if value is None or pd.isna(value):
            formatted_stats[key] = None
            continue
            
        # Convert to float for processing
        try:
            num_value = float(value)
        except (ValueError, TypeError):
            formatted_stats[key] = value
            continue
        
        # Apply formatting based on stat type
        if key in batting_averages:
            # 3 decimals, remove leading zero for values < 1
            formatted = f"{num_value:.3f}"
            if num_value < 1.0 and formatted.startswith('0'):
                formatted = formatted[1:]  # Remove leading zero
            formatted_stats[key] = formatted
            
        elif key in ops_stats:
            # 3 decimals, remove leading zero for values < 1
            formatted = f"{num_value:.3f}"
            if num_value < 1.0 and formatted.startswith('0'):
                formatted = formatted[1:]
            formatted_stats[key] = formatted
            
        elif key in era_stats:
            # 2 decimals, keep all digits
            formatted_stats[key] = f"{num_value:.2f}"
            
        elif key in whip_stats:
            # 3 decimals, keep all digits (WHIP can be > 1)
            formatted_stats[key] = f"{num_value:.3f}"
            
        elif key in rate_stats:
            # 1 decimal, keep all digits
            formatted_stats[key] = f"{num_value:.1f}"
            
        elif key in ip_stats:
            # 1 decimal for innings pitched
            formatted_stats[key] = f"{num_value:.1f}"
            
        else:
            # Everything else - round to whole numbers
            if isinstance(num_value, float) and num_value.is_integer():
                formatted_stats[key] = int(num_value)
            elif isinstance(num_value, float):
                formatted_stats[key] = int(round(num_value))
            else:
                formatted_stats[key] = value
    
    return formatted_stats

def format_team_response(df, stat_type, mode, team_id, year):
    """Format team stats response - Updated to handle None year for franchise/career mode"""
    try:
        # For franchise/career mode, don't include year in team name
        if mode in ["franchise", "career"]:
            team_name = get_team_name(team_id, None)  # Pass None for year
        else:
            team_name = get_team_name(team_id, year)
        
        if mode in ["season", "franchise", "career"]:
            stats = df.to_dict(orient="records")[0] if not df.empty else {}
        elif mode == "history":
            stats = df.to_dict(orient="records")
        else:
            stats = df.to_dict(orient="records")[0] if not df.empty else {}
        
        # Convert numpy types to Python types for JSON serialization
        if isinstance(stats, dict):
            for key, value in stats.items():
                if hasattr(value, 'item'):  # numpy scalar
                    stats[key] = value.item()
                elif pd.isna(value):
                    stats[key] = None
            # Apply formatting to the stats dictionary
            stats = format_and_round_stats(stats)
            
        elif isinstance(stats, list):
            for i, record in enumerate(stats):
                for key, value in record.items():
                    if hasattr(value, 'item'):
                        record[key] = value.item()
                    elif pd.isna(value):
                        record[key] = None
                # Apply formatting to each record in the list
                stats[i] = format_and_round_stats(record)
        
        # Get team logo
        team_logo = get_team_logo_with_fallback(team_id, year)
        
        return jsonify({
            "mode": mode,
            "team_type": stat_type,
            "team_id": team_id,
            "team_name": team_name,
            "year": year,
            "team_logo": team_logo,
            "stats": stats
        })
        
    except Exception as e:
        print(f"Error formatting team response: {str(e)}")
        return jsonify({"error": f"Response formatting error: {str(e)}"}), 500

def get_team_name(team_id, year=None):
    """Get full team name for display purposes - Updated to handle franchise mode"""
    team_names = {
        # Angels - various eras
        'ALT': 'Los Angeles Angels',      # Early Angels
        'CAL': 'California Angels',       # California era
        'ANA': 'Anaheim Angels',         # Anaheim era  
        'LAA': 'Los Angeles Angels',      # Current era
        
        # Diamondbacks
        'ARI': 'Arizona Diamondbacks', 
        
        # Braves - moved cities
        'BSN': 'Boston Braves',          # Boston era
        'ML1': 'Milwaukee Braves',       # Milwaukee era
        'MLA': 'Milwaukee Braves',       # Alternative Milwaukee code
        'ATL': 'Atlanta Braves',         # Current Atlanta era
        
        # Orioles / St. Louis Browns
        'SLA': 'St. Louis Browns',       # Before moving to Baltimore
        'BAL': 'Baltimore Orioles',      # Current
        
        # Red Sox
        'BS1': 'Boston Red Sox',         # Historical code
        'BOS': 'Boston Red Sox',         # Current
        
        # Cubs
        'CHN': 'Chicago Cubs',           # Database code
        'CHC': 'Chicago Cubs',           # Alternative
        
        # White Sox
        'CHA': 'Chicago White Sox',      # Database code  
        'CHW': 'Chicago White Sox',      # Alternative
        'CWS': 'Chicago White Sox',      # Alternative
        
        # Reds
        'CN2': 'Cincinnati Reds',        # Historical code
        'CN3': 'Cincinnati Reds',        # Another historical code
        'CIN': 'Cincinnati Reds',        # Current
        
        # Indians/Guardians
        'CLE': 'Cleveland Guardians',    # Current (covers both Indians/Guardians)
        
        # Rockies
        'COL': 'Colorado Rockies',
        
        # Tigers
        'DET': 'Detroit Tigers',
        
        # Astros
        'HOU': 'Houston Astros',
        
        # Royals
        'KCA': 'Kansas City Royals',     # Historical code
        'KCR': 'Kansas City Royals',     # Current
        
        # Dodgers - Brooklyn to LA
        'BR1': 'Brooklyn Dodgers',       # Early Brooklyn era
        'BR2': 'Brooklyn Dodgers',       # Brooklyn era
        'BR4': 'Brooklyn Dodgers',       # Another Brooklyn code
        'BRO': 'Brooklyn Dodgers',       # If this code exists
        'LAD': 'Los Angeles Dodgers',    # Alternative current
        'LAN': 'Los Angeles Dodgers',    # Database code
        
        # Marlins
        'FLA': 'Florida Marlins',        # Florida era
        'MIA': 'Miami Marlins',          # Current Miami era
        
        # Brewers
        'MIL': 'Milwaukee Brewers',
        
        # Twins
        'MIN': 'Minnesota Twins',
        
        # Mets
        'NYM': 'New York Mets',
        
        # Yankees
        'NYY': 'New York Yankees',
        
        # Athletics - Philadelphia to Oakland
        'PHA': 'Philadelphia Athletics',  # Philadelphia era
        'OAK': 'Oakland Athletics',       # Current Oakland era
        
        # Phillies
        'PHN': 'Philadelphia Phillies',  # Historical code
        'PH3': 'Philadelphia Phillies',  # Another historical code
        'PHI': 'Philadelphia Phillies',  # Current
        
        # Pirates
        'PIT': 'Pittsburgh Pirates',
        
        # Padres
        'SDP': 'San Diego Padres',       # Database code
        'SD': 'San Diego Padres',        # Alternative
        
        # Mariners
        'SEA': 'Seattle Mariners',
        
        # Giants - New York to San Francisco
        'NY1': 'New York Giants',        # If this code exists
        'SFG': 'San Francisco Giants',   # Current
        'SF': 'San Francisco Giants',    # Alternative
        
        # Cardinals
        'STL': 'St. Louis Cardinals',
        
        # Rays
        'TBD': 'Tampa Bay Devil Rays',   # Devil Rays era
        'TBR': 'Tampa Bay Rays',         # Current Rays era
        'TB': 'Tampa Bay Rays',          # Alternative
        
        # Rangers / Washington Senators
        'WAS': 'Washington Senators',    # Before moving to Texas
        'TEX': 'Texas Rangers',          # Current
        
        # Blue Jays
        'TOR': 'Toronto Blue Jays',
        
        # Nationals / Montreal Expos
        'MON': 'Montreal Expos',         # Montreal era
        'WSN': 'Washington Nationals',   # Current
        'WAS': 'Washington Nationals'    # Alternative (though might conflict with Senators)
    }
    
    base_name = team_names.get(team_id.upper(), team_id)
    
    # For franchise mode or when year is None, don't prefix with year
    if year is None:
        return f"{base_name} (All-Time)"
    else:
        return f"{year} {base_name}"
    
def get_team_logo_url(team_id, year=None):
    """Get team logo URL using working MLB logo sources"""
    
    # Map your database team codes to MLB's team IDs and abbreviations
    mlb_team_mapping = {
        # Angels
        'ALT': {'abbrev': 'LAA', 'id': '108'},
        'CAL': {'abbrev': 'LAA', 'id': '108'}, 
        'ANA': {'abbrev': 'LAA', 'id': '108'},
        'LAA': {'abbrev': 'LAA', 'id': '108'},
        
        # Diamondbacks
        'ARI': {'abbrev': 'ARI', 'id': '109'},
        
        # Braves
        'BSN': {'abbrev': 'ATL', 'id': '144'},
        'ML1': {'abbrev': 'ATL', 'id': '144'},
        'MLA': {'abbrev': 'ATL', 'id': '144'},
        'ATL': {'abbrev': 'ATL', 'id': '144'},
        
        # Orioles
        'SLA': {'abbrev': 'BAL', 'id': '110'},
        'BAL': {'abbrev': 'BAL', 'id': '110'},
        
        # Red Sox
        'BS1': {'abbrev': 'BOS', 'id': '111'},
        'BOS': {'abbrev': 'BOS', 'id': '111'},
        
        # Cubs
        'CHN': {'abbrev': 'CHC', 'id': '112'},
        'CHC': {'abbrev': 'CHC', 'id': '112'},
        
        # White Sox
        'CHA': {'abbrev': 'CWS', 'id': '145'},
        'CHW': {'abbrev': 'CWS', 'id': '145'},
        'CWS': {'abbrev': 'CWS', 'id': '145'},
        
        # Reds
        'CN2': {'abbrev': 'CIN', 'id': '113'},
        'CN3': {'abbrev': 'CIN', 'id': '113'},
        'CIN': {'abbrev': 'CIN', 'id': '113'},
        
        # Indians/Guardians
        'CLE': {'abbrev': 'CLE', 'id': '114'},
        
        # Rockies
        'COL': {'abbrev': 'COL', 'id': '115'},
        
        # Tigers
        'DET': {'abbrev': 'DET', 'id': '116'},
        
        # Astros
        'HOU': {'abbrev': 'HOU', 'id': '117'},
        
        # Royals
        'KCA': {'abbrev': 'KC', 'id': '118'},
        'KCR': {'abbrev': 'KC', 'id': '118'},
        
        # Dodgers
        'BR1': {'abbrev': 'LAD', 'id': '119'},
        'BR2': {'abbrev': 'LAD', 'id': '119'},
        'BR4': {'abbrev': 'LAD', 'id': '119'},
        'BRO': {'abbrev': 'LAD', 'id': '119'},
        'LAD': {'abbrev': 'LAD', 'id': '119'},
        'LAN': {'abbrev': 'LAD', 'id': '119'},
        
        # Marlins
        'FLA': {'abbrev': 'MIA', 'id': '146'},
        'MIA': {'abbrev': 'MIA', 'id': '146'},
        
        # Brewers
        'MIL': {'abbrev': 'MIL', 'id': '158'},
        
        # Twins
        'MIN': {'abbrev': 'MIN', 'id': '142'},
        
        # Mets
        'NYM': {'abbrev': 'NYM', 'id': '121'},
        
        # Yankees
        'NYY': {'abbrev': 'NYY', 'id': '147'},
        
        # Athletics
        'PHA': {'abbrev': 'OAK', 'id': '133'},
        'OAK': {'abbrev': 'OAK', 'id': '133'},
        
        # Phillies
        'PHN': {'abbrev': 'PHI', 'id': '143'},
        'PH3': {'abbrev': 'PHI', 'id': '143'},
        'PHI': {'abbrev': 'PHI', 'id': '143'},
        
        # Pirates
        'PIT': {'abbrev': 'PIT', 'id': '134'},
        
        # Padres
        'SDP': {'abbrev': 'SD', 'id': '135'},
        'SD': {'abbrev': 'SD', 'id': '135'},
        
        # Mariners
        'SEA': {'abbrev': 'SEA', 'id': '136'},
        
        # Giants
        'NY1': {'abbrev': 'SF', 'id': '137'},
        'SFG': {'abbrev': 'SF', 'id': '137'},
        'SF': {'abbrev': 'SF', 'id': '137'},
        
        # Cardinals
        'STL': {'abbrev': 'STL', 'id': '138'},
        
        # Rays
        'TBD': {'abbrev': 'TB', 'id': '139'},
        'TBR': {'abbrev': 'TB', 'id': '139'},
        'TB': {'abbrev': 'TB', 'id': '139'},
        
        # Rangers
        'WAS': {'abbrev': 'TEX', 'id': '140'},
        'TEX': {'abbrev': 'TEX', 'id': '140'},
        
        # Blue Jays
        'TOR': {'abbrev': 'TOR', 'id': '141'},
        
        # Nationals
        'MON': {'abbrev': 'WSH', 'id': '120'},
        'WSN': {'abbrev': 'WSH', 'id': '120'},
        'WAS': {'abbrev': 'WSH', 'id': '120'}
    }
    
    # Get team info
    team_info = mlb_team_mapping.get(team_id.upper(), {'abbrev': team_id.upper(), 'id': '0'})
    abbrev = team_info['abbrev']
    team_number = team_info['id']
    
    # Try multiple URL patterns that are known to work
    logo_urls = [
        # MLB official team logos - using team ID
        f"https://www.mlbstatic.com/team-logos/url/{team_number}.svg",
        
        # Alternative MLB static URLs
        f"https://img.mlbstatic.com/mlb-photos/image/upload/v1/team/{abbrev.lower()}/logo/current",
        
        # ESPN logos (reliable fallback)
        f"https://a.espncdn.com/i/teamlogos/mlb/500/{abbrev.lower()}.png",
        
        # Sports logos database 
        f"https://content.sportslogos.net/logos/54/{team_number}/{abbrev}-logo-primary-dark.png",
        
        # Loodibee logos (free transparent PNGs)
        f"https://loodibee.com/wp-content/uploads/mlb-{abbrev.lower()}-logo-transparent.png",
        
        # TeamColorCodes fallback
        f"https://teamcolorcodes.com/wp-content/uploads/{abbrev.lower()}-logo.png"
    ]
    
    return logo_urls[0]  # Return primary URL


def get_team_logo_with_fallback(team_id, year=None):
    """Get team logo with multiple fallback options"""
    try:
        # Map team codes
        mlb_team_mapping = {
            'CHN': {'abbrev': 'CHC', 'id': '112'},
            'CHC': {'abbrev': 'CHC', 'id': '112'},
            'LAN': {'abbrev': 'LAD', 'id': '119'},
            'LAD': {'abbrev': 'LAD', 'id': '119'},
            'CHA': {'abbrev': 'CWS', 'id': '145'},
            'CWS': {'abbrev': 'CWS', 'id': '145'},
            'NYY': {'abbrev': 'NYY', 'id': '147'},
            'BOS': {'abbrev': 'BOS', 'id': '111'},
            'ATL': {'abbrev': 'ATL', 'id': '144'},
            'HOU': {'abbrev': 'HOU', 'id': '117'},
            'LAA': {'abbrev': 'LAA', 'id': '108'},
            'ARI': {'abbrev': 'ARI', 'id': '109'},
            'BAL': {'abbrev': 'BAL', 'id': '110'},
            'CIN': {'abbrev': 'CIN', 'id': '113'},
            'CLE': {'abbrev': 'CLE', 'id': '114'},
            'COL': {'abbrev': 'COL', 'id': '115'},
            'DET': {'abbrev': 'DET', 'id': '116'},
            'KCR': {'abbrev': 'KC', 'id': '118'},
            'MIA': {'abbrev': 'MIA', 'id': '146'},
            'MIL': {'abbrev': 'MIL', 'id': '158'},
            'MIN': {'abbrev': 'MIN', 'id': '142'},
            'NYM': {'abbrev': 'NYM', 'id': '121'},
            'OAK': {'abbrev': 'OAK', 'id': '133'},
            'PHI': {'abbrev': 'PHI', 'id': '143'},
            'PIT': {'abbrev': 'PIT', 'id': '134'},
            'SDP': {'abbrev': 'SD', 'id': '135'},
            'SEA': {'abbrev': 'SEA', 'id': '136'},
            'SFG': {'abbrev': 'SF', 'id': '137'},
            'STL': {'abbrev': 'STL', 'id': '138'},
            'TBR': {'abbrev': 'TB', 'id': '139'},
            'TEX': {'abbrev': 'TEX', 'id': '140'},
            'TOR': {'abbrev': 'TOR', 'id': '141'},
            'WSN': {'abbrev': 'WSH', 'id': '120'}
        }
        
        team_info = mlb_team_mapping.get(team_id.upper(), {'abbrev': team_id.upper(), 'id': '0'})
        abbrev = team_info['abbrev']
        team_number = team_info['id']
        
        # Primary URL (most reliable)
        primary_url = f"https://a.espncdn.com/i/teamlogos/mlb/500/{abbrev.lower()}.png"
        
        # Fallback URLs in order of reliability
        fallback_urls = [
            f"https://www.mlbstatic.com/team-logos/url/{team_number}.svg",
            f"https://loodibee.com/wp-content/uploads/mlb-{abbrev.lower()}-logo-transparent.png",
            f"https://content.sportslogos.net/logos/54/{team_number}/{abbrev}-logo-primary-dark.png",
            f"https://img.mlbstatic.com/mlb-photos/image/upload/v1/team/{abbrev.lower()}/logo/current"
        ]
        
        return {
            'primary': primary_url,
            'fallbacks': fallback_urls
        }
        
    except Exception as e:
        print(f"Error getting team logo: {e}")
        # Return a basic fallback
        return {
            'primary': f"https://a.espncdn.com/i/teamlogos/mlb/500/{team_id.lower()}.png",
            'fallbacks': []
        }



def get_modern_team_code(team_id):
    """Convert historical team codes to modern equivalents"""
    mapping = {
        'ALT': 'LAA', 'CAL': 'LAA', 'ANA': 'LAA', 'LAA': 'LAA',
        'BSN': 'ATL', 'ML1': 'ATL', 'MLA': 'ATL', 'ATL': 'ATL', 
        'SLA': 'BAL', 'BAL': 'BAL',
        'CHN': 'CHC', 'CHC': 'CHC',
        'CHA': 'CWS', 'CHW': 'CWS', 'CWS': 'CWS',
        'BR1': 'LAD', 'BR2': 'LAD', 'BR4': 'LAD', 'BRO': 'LAD', 'LAN': 'LAD', 'LAD': 'LAD',
        'FLA': 'MIA', 'MIA': 'MIA',
        'PHA': 'OAK', 'OAK': 'OAK',
        'SDP': 'SD', 'SD': 'SD',
        'TBD': 'TB', 'TBR': 'TB', 'TB': 'TB',
        'WAS': 'TEX', 'TEX': 'TEX',  # Senators -> Rangers
        'MON': 'WSH', 'WSN': 'WSH', 'WAS': 'WSH'  # Expos -> Nationals
    }
    return mapping.get(team_id.upper(), team_id.upper())


def get_historical_team_logo(team_id, year):
    """Get historically accurate team logos for specific years"""
    
    # Define logo changes by team and year
    historical_logos = {
        'LAA': {  # Angels logo changes
            'ranges': [
                (1961, 1970, 'california_angels_1961'),
                (1971, 1985, 'california_angels_1971'), 
                (1986, 1992, 'california_angels_1986'),
                (1993, 1996, 'california_angels_1993'),
                (1997, 2001, 'anaheim_angels_1997'),
                (2002, 2003, 'anaheim_angels_2002'),
                (2004, 2024, 'los_angeles_angels_2004')
            ]
        },
        'MIA': {  # Marlins logo changes
            'ranges': [
                (1993, 2011, 'florida_marlins_1993'),
                (2012, 2018, 'miami_marlins_2012'),
                (2019, 2024, 'miami_marlins_2019')
            ]
        },
        'TB': {  # Rays logo changes
            'ranges': [
                (1998, 2007, 'devil_rays_1998'),
                (2008, 2024, 'rays_2008')
            ]
        },
        'CLE': {  # Indians/Guardians
            'ranges': [
                (1901, 1914, 'cleveland_blues'),
                (1915, 2021, 'cleveland_indians'),
                (2022, 2024, 'cleveland_guardians')
            ]
        }
        # Add more teams with significant logo changes
    }
    
    modern_code = get_modern_team_code(team_id)
    
    if modern_code in historical_logos and year:
        for start_year, end_year, logo_key in historical_logos[modern_code]['ranges']:
            if start_year <= year <= end_year:
                return f"https://content.sportslogos.net/logos/53/historical/{logo_key}.png"
    
    # Fallback to current logo
    return get_team_logo_url(team_id, year)




if __name__ == "__main__":
    app.run(debug=True)