import pandas as pd
import sqlite3

# Path to your database and the CSV file
DB_PATH = r"C:\Users\noahs\OneDrive\Documents\Baseball Stats\lahman2024.db"
CSV_PATH = r"C:\Users\noahs\OneDrive\Documents\Baseball Stats\jeffbagwell_war_historical_2025.csv"  # Update this path

def load_war_data():
    # Read the CSV file
    print("Reading JEFFBAGWELL WAR CSV file...")
    df = pd.read_csv(CSV_PATH)
    
    print(f"Loaded {len(df)} rows of WAR data")
    print("Columns:", list(df.columns))
    
    # Connect to your database
    conn = sqlite3.connect(DB_PATH)
    
    # Create the table and load the data
    print("Loading data into SQLite database...")
    df.to_sql('jeffbagwell_war', conn, if_exists='replace', index=False)
    
    # Create an index for faster queries
    print("Creating indexes...")
    conn.execute('CREATE INDEX IF NOT EXISTS idx_war_bbref ON jeffbagwell_war(key_bbref)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_war_year ON jeffbagwell_war(year_ID)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_war_bbref_year ON jeffbagwell_war(key_bbref, year_ID)')
    
    conn.commit()
    
    # Test the data
    print("\nTesting the data...")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jeffbagwell_war")
    count = cursor.fetchone()[0]
    print(f"Total records in database: {count}")
    
    # Sample some data
    cursor.execute("SELECT player_name, year_ID, WAR162 FROM jeffbagwell_war WHERE player_name LIKE '%Mike Trout%' ORDER BY year_ID DESC LIMIT 5")
    sample = cursor.fetchall()
    print("\nSample Mike Trout data:")
    for row in sample:
        print(f"  {row[0]} - {row[1]}: {row[2]} WAR")
    
    conn.close()
    print("WAR data loaded successfully!")

if __name__ == "__main__":
    load_war_data()