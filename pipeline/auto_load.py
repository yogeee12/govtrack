import os
import glob
import pandas as pd
from sqlalchemy import create_engine
from pipeline.govtrack_pipeline import run_road_pipeline

DB_URL = "mysql+pymysql://root:E=mc*2@localhost/govtrack"
Data_DIR = r"C:\Users\yoges\OneDrive\Desktop\Final_year_project\govtrack\data"
TABLE_NAME = "road_projects"

engine = create_engine(DB_URL)

# -- Find all XLSX and CSV files recursivly 
xlsx_files = glob.glob(os.path.join(Data_DIR, "**/*.xlsx"), recursive=True)
csv_files = glob.glob(os.path.join(Data_DIR, "**/*.csv"), recursive=True)
all_files = xlsx_files + csv_files

# Process for each file
first = True
for filepath in all_files:
    print(f"\nProcessing : {filepath}")
    source_file = os.path.basename(filepath)

    # Check if source_file already exists in database
    try:
        query = f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE source_file = '{source_file}'"
        result = pd.read_sql(query, con=engine)
        if result.iloc[0, 0] > 0:
            print(f" Skipped - {source_file} already exists in database")
            continue
    except:
        pass

    try:
        df = run_road_pipeline(filepath)
        if df is None or len(df) == 0:
            print(" Skipped - empty output")
            continue

        # First file replaces tables, rest append
        mode = 'replace' if first else 'append'
        df['source_file'] = source_file
        df.to_sql(TABLE_NAME, con=engine, if_exists=mode, index=False)
        print(f' Loaded {len(df)} rows ({mode} | Anomalies : {(df["Anomaly"] == -1).sum()})')
        first = False

    except Exception as e:
        print(f"ERROR : {e}")
        continue

    print(f"\nDone. Run: SELECT COUNT(*) FROM {TABLE_NAME};")
