from flask import Flask, request, jsonify, send_from_directory
from pybaseball import playerid_lookup, batting_stats, cache
import sqlite3
import pandas as pd
import os
import datetime

app = Flask(__name__, static_folder="static")

cache.enable()

DB_PATH = r"C:\Users\noahs\OneDrive\Documents\Baseball Stats\lahman2024.db"

def get_career_war(playerid):
    """Get career WAR from JEFFBAGWELL database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Query career WAR total
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

    # MLBAM ID for photo
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

    # Lahman batting stats - INCLUDE sh (sacrifice hits) for plate appearances calculation
    stats_query = """
    SELECT yearid, teamid, g, ab, h, hr, rbi, sb, bb, hbp, sf, sh, `2b`, `3b`
    FROM lahman_batting WHERE playerid = ?
    """
    df_lahman = pd.read_sql_query(stats_query, conn, params=(playerid,))
    conn.close()

    # Current year live pybaseball stats
    current_year = datetime.date.today().year
    df_live = batting_stats(current_year)
    df_live['Name'] = df_live['Name'].str.lower()
    live_row = df_live[df_live['Name'] == f"{first.lower()} {last.lower()}"]

    if mode == "career":
        if df_lahman.empty:
            return jsonify({"error": "No stats found"}), 404

        totals = df_lahman.agg({
            "g": "sum", "ab": "sum", "h": "sum", "hr": "sum", "rbi": "sum",
            "sb": "sum", "bb": "sum", "hbp": "sum", "sf": "sum", "sh": "sum", "2b": "sum", "3b": "sum"
        }).to_dict()

        # Calculate derived stats
        singles = totals["h"] - totals["2b"] - totals["3b"] - totals["hr"]
        total_bases = singles + 2*totals["2b"] + 3*totals["3b"] + 4*totals["hr"]
        ba = totals["h"] / totals["ab"] if totals["ab"] > 0 else 0
        obp_denominator = totals["ab"] + totals["bb"] + totals["hbp"] + totals["sf"]
        obp = (totals["h"] + totals["bb"] + totals["hbp"]) / obp_denominator if obp_denominator > 0 else 0
        slg = total_bases / totals["ab"] if totals["ab"] > 0 else 0
        ops = obp + slg

        # Calculate plate appearances: AB + BB + HBP + SF + SH
        plate_appearances = totals["ab"] + totals["bb"] + totals["hbp"] + totals["sf"] + totals["sh"]

        # Get career WAR from JEFFBAGWELL database
        career_war = get_career_war(playerid)

        # OPS+ from current season (proxy for career)
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
            "totals": result,
            "photo_url": photo_url
        })

    elif mode == "season":
        if df_lahman.empty:
            return jsonify({"error": "No stats found"}), 404

        # Get season WAR history
        df_war_history = get_season_war_history(playerid)

        # Calculate derived stats per season
        df = df_lahman.copy()
        df["singles"] = df["h"] - df["2b"] - df["3b"] - df["hr"]
        df["total_bases"] = df["singles"] + 2*df["2b"] + 3*df["3b"] + 4*df["hr"]
        df["ba"] = df.apply(lambda row: row["h"] / row["ab"] if row["ab"] > 0 else 0, axis=1)
        df["obp"] = df.apply(lambda row: (row["h"] + row["bb"] + row["hbp"]) / (row["ab"] + row["bb"] + row["hbp"] + row["sf"]) if (row["ab"] + row["bb"] + row["hbp"] + row["sf"]) > 0 else 0, axis=1)
        df["slg"] = df.apply(lambda row: row["total_bases"] / row["ab"] if row["ab"] > 0 else 0, axis=1)
        df["ops"] = df["obp"] + df["slg"]
        df["pa"] = df["ab"] + df["bb"] + df["hbp"] + df["sf"] + df["sh"]

        # Merge with WAR data
        if not df_war_history.empty:
            df = df.merge(df_war_history, left_on='yearid', right_on='year_ID', how='left')
            df['war'] = df['war'].fillna(0)
        else:
            df['war'] = 0

        # Select columns to return
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
            "stats": df_result.to_dict(orient="records"),
            "photo_url": photo_url
        })

    elif mode == "live":
        if live_row.empty:
            return jsonify({"error": "No live stats found"}), 404

        live_stats = live_row.to_dict(orient="records")[0]

        # Get current season stats including WAR
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
            "stats": result,
            "photo_url": photo_url
        })

    elif mode == "combined":
        if df_lahman.empty:
            return jsonify({"error": "No career stats found"}), 404

        # Lahman career totals - INCLUDE sh for plate appearances calculation
        totals = df_lahman.agg({
            "g": "sum", "ab": "sum", "h": "sum", "hr": "sum", "rbi": "sum",
            "sb": "sum", "bb": "sum", "hbp": "sum", "sf": "sum", "sh": "sum", "2b": "sum", "3b": "sum"
        }).to_dict()

        # Get career WAR from JEFFBAGWELL database
        career_war = get_career_war(playerid)

        # Add current season stats if available
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
            totals["sh"] += int(live_stats.get("SH", 0))  # Add sacrifice hits from live stats
            totals["2b"] += int(live_stats.get("2B", 0))
            totals["3b"] += int(live_stats.get("3B", 0))

            # Get current season WAR
            for war_col in ['WAR', 'war', 'War', 'fWAR', 'bWAR', 'rWAR']:
                if war_col in live_stats and not pd.isna(live_stats[war_col]):
                    current_season_war = float(live_stats[war_col])
                    break

        # Calculate combined stats
        singles = totals["h"] - totals["2b"] - totals["3b"] - totals["hr"]
        total_bases = singles + 2*totals["2b"] + 3*totals["3b"] + 4*totals["hr"]
        ba = totals["h"] / totals["ab"] if totals["ab"] > 0 else 0
        obp_denominator = totals["ab"] + totals["bb"] + totals["hbp"] + totals["sf"]
        obp = (totals["h"] + totals["bb"] + totals["hbp"]) / obp_denominator if obp_denominator > 0 else 0
        slg = total_bases / totals["ab"] if totals["ab"] > 0 else 0
        ops = obp + slg

        # Calculate combined plate appearances: AB + BB + HBP + SF + SH
        plate_appearances = totals["ab"] + totals["bb"] + totals["hbp"] + totals["sf"] + totals["sh"]

        # Combined WAR (career + current season)
        combined_war = career_war + current_season_war

        # OPS+ (current season proxy)
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
            "totals": result,
            "photo_url": photo_url
        })

    else:
        return jsonify({"error": "Invalid mode"}), 400

if __name__ == "__main__":
    app.run(debug=True)