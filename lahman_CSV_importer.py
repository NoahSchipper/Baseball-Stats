import os
import sqlite3
import pandas as pd
import zipfile

# Paths
ZIP_PATH = r"C:\Users\noahs\OneDrive\Documents\Baseball Stats\lahman_1871-2024_csv.zip"
CSV_FOLDER = r"C:\Users\noahs\OneDrive\Documents\Baseball Stats\lahman_csv"
DB_PATH = r"C:\Users\noahs\OneDrive\Documents\Baseball Stats\lahman2024.db"

# 1. Unzip Lahman if not already extracted
if not os.path.exists(CSV_FOLDER):
    os.makedirs(CSV_FOLDER)
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(CSV_FOLDER)
    print(f"Extracted Lahman CSVs to: {CSV_FOLDER}")

# 2. Connect to SQLite
conn = sqlite3.connect(DB_PATH)

# 3. Loop through every CSV in the folder
for csv_file in os.listdir(CSV_FOLDER):
    if not csv_file.endswith(".csv"):
        continue  # skip non-CSV files

    # Normalize table name: lahman_<filename_lowercase>
    table_name = "lahman_" + os.path.splitext(csv_file)[0].lower()
    file_path = os.path.join(CSV_FOLDER, csv_file)

    print(f"Loading {csv_file} into table '{table_name}'...")

    # Read CSV
    df = pd.read_csv(file_path)
    df.columns = [c.lower().strip() for c in df.columns]  # normalize columns

    # Write to SQLite
    df.to_sql(table_name, conn, if_exists="replace", index=False)

# 4. Close connection
conn.close()
print(f"✅ All Lahman CSVs imported into {DB_PATH}")
