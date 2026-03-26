import re
import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import LabelEncoder
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest

def run_road_pipeline(filepath):
  #1. Extracting meta data (state, scheme) from first 10 rows.
  if filepath.endswith(".xlsx") or filepath.endswith(".xls"):
    meta_data = pd.read_excel(rf"{filepath}", nrows=10, header=None)
  else:
    meta_data = pd.read_csv(rf"{filepath}", nrows=10, header=None)

  meta_data = str(meta_data.iloc[6,1])
  state = re.search(r'State:\s*([A-Za-z\s]+?)(?:\s{2,}|District)', meta_data)
  scheme = re.search(r'Scheme\s*:\s*(.+?)\s*Sub Scheme', meta_data)

  scheme_name = scheme.group(1).strip() if scheme else 'Unknown'
  state_name = state.group(1).strip() if state else 'Unkown'

  #2. Load data with skiprows=10 ,firts 10 rows = meta data.
  if filepath.endswith(".xlsx") or filepath.endswith(".xls"):
    df = pd.read_excel(rf"{filepath}", skiprows=10)
  else:
    df = pd.read_csv(rf"{filepath}", skiprows=10)

  #3 drop unnamed & No value columns, Last two rows of to skip total.
  df = df.dropna(axis=1, how='all')
  df = df.iloc[:-2]

  #4 Drop unwanted / irrelevant fetaures.
  df = df.drop(columns = ["Sr.No.","Programme Implementation Unit","Road Name / Bridge Name","Core-Network Road name","Core-Network Habitation name","5 Years Maintenance Cost Due","Package No."], errors = 'ignore')
  required_cols = [
      "Road Length (Kms)",
      "Sanction Cost",
      "Expenditure Till Date"
  ]

  missing = [col for col in required_cols if col not in df.columns]

  if missing:
      raise ValueError(f"Missing columns: {missing}")

  #5 Split road/bridge
  bridge_df = df[df['Work Type'] == 'LSB'].copy()
  df = df[df['Work Type'] != 'LSB'].copy()
  # Keep Work Type column — useful for EDA dashboard
  df.drop(columns= ["Work Type","Bridge Length (Mtrs)","Block Name","Contractor Name"], inplace=True, errors="ignore")

  #6 Reset index
  df.reset_index(drop=True, inplace = True)

  #7 Extarct year via regex
  split = df["Completion Date"].fillna("").str.split("/", expand=True)
  fin_part = split[0]
  phy_part = split[1]
  df['Financial Completion Year'] = fin_part.str.extract(r"Financial.*?(\d{4})")
  df['Physical Completion Year'] = phy_part.str.extract(r"Physical.*?(\d{4})")
  df['Sanctioned Year'] = df['Sanctioned Year'].str.extract(r'(\d{4})')

  #8 Create Habitation Count
  df['Benefited Habitations'] = df["Name of Benefited Habitations"].str.count(',')+1
  df.drop(columns=["Completion Date","Name of Benefited Habitations"],inplace = True)

  #9 Fix Indian number format
  try:
    df["Sanction Cost"] = df["Sanction Cost"].str.replace(",","").pipe(pd.to_numeric, errors = "coerce")
    df["Expenditure Till Date"] = df["Expenditure Till Date"].str.replace(",","").pipe(pd.to_numeric, errors = 'coerce')
    df["State Cost"] = df["State Cost"].str.replace(",","").pipe(pd.to_numeric, errors = 'coerce')
  except:
    pass

  #10 Auto Type Converstion
  cols = [
    "Road Length (Kms)",
    "Road Length Completed Till Date",
    "Sanction Cost",
    "Expenditure Till Date",
    "Sanctioned Year",
    "State Cost"
  ]
  df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')

  #11 Handle Null Values.
  #Benefited Habitation -No data = 0 habitation
  df["Benefited Habitations"] = df["Benefited Habitations"].fillna(0)
  # Expenditure Till Date — no expenditure recorded = 0
  df['Expenditure Till Date'] = df['Expenditure Till Date'].fillna(0)
  # Road Length Completed Till Date — no completion recorded = 0
  df['Road Length Completed Till Date'] = df['Road Length Completed Till Date'].fillna(0)
  # State Cost — no state contribution recorded = 0
  df['State Cost'] = df['State Cost'].fillna(0)
  # Sanction Cost and Road Length — if null, drop the row
  # These are core columns — a project without cost or length is unusable
  df = df.dropna(subset=['Sanction Cost', 'Road Length (Kms)'])

  #12 Feature engineering
  df[['Sanctioned Year','Financial Completion Year','Physical Completion Year']]=df[['Sanctioned Year','Financial Completion Year','Physical Completion Year']].apply(pd.to_numeric).astype('Int64')
  df['Benefited Habitations'] = pd.to_numeric(df['Benefited Habitations'], errors="coerce")

  df['Is Completed'] = df['Financial Completion Year'].notnull().astype(int)
  #cost per km
  df['Cost Per Km'] = df["Sanction Cost"] / df["Road Length (Kms)"]
  df.loc[df["Road Length (Kms)"] == 0, "Cost Per Km"] = pd.NA
  #Completion year
  current_year = datetime.datetime.now().year
  df["Completion Ratio Raw"] = (df["Road Length Completed Till Date"] / df["Road Length (Kms)"]).clip(upper=1)
  #For Over completion ratio
  df["Completion Ratio"] = df["Completion Ratio Raw"].clip(upper=1)
  df["Over Completion Flag"] = (df["Completion Ratio Raw"] > 1).astype(float)

  df.loc[df["Road Length (Kms)"] == 0, "Completion Ratio"] = (df["Stage of Progress"].isin(["Completed","Maintenance"]).astype(float))
  # Financial Progress Completed till now
  df["Financial Progress"] = df["Expenditure Till Date"] / df["Sanction Cost"].replace(0, pd.NA)
  # Project by current year - sanction year
  df["Project Age"] = current_year - df["Sanctioned Year"]
  df.loc[df["Project Age"] < 0 , "Project Age"] = 0
  #13 State and scheme coulmns
  df["State"] = state_name
  df["Scheme"] = scheme_name

  #14 Drop negative expenditure rows
  df = df[df["Expenditure Till Date"] >= 0]
  df = df.dropna(subset=['District Name', 'Stage of Progress'])

  #15 Prepare ML Data
  ml_df = prepare_ml_data(df)

  #16 scale and train
  scaler = StandardScaler()
  X_scaled = scaler.fit_transform(ml_df)

  # Model used Isolation Forest
  model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
  model.fit(X_scaled)

  prediction = model.predict(X_scaled)
  scores = model.decision_function(X_scaled)

  #17 Assign back using index
  df["Anomaly"] = pd.NA
  df["Anomaly_Score"] =pd.NA
  df.loc[ml_df.index, "Anomaly"] = prediction
  df.loc[ml_df.index, "Anomaly_Score"] = scores

  print(f"Done. Rows {len(df)} | Anomalies : {(df['Anomaly'] == -1).sum()}")

  return df

def prepare_ml_data(df):
  ml_df = df.copy()

  le = LabelEncoder()

  #label encode categorical name
  cat_cols = ['District Name','Stage of Progress', "Collaboration", "Connectivity (New / Upgrade)"]

  for cols in cat_cols:
    ml_df[cols + "_encoded"] = le.fit_transform(ml_df[cols].astype(str))

  feature_cols = ['Cost Per Km', 'Completion Ratio', 'Financial Progress',
        'Project Age', 'Benefited Habitations', 'Road Length (Kms)',
        'Sanction Cost', 'Is Completed',
        'District Name_encoded', 'Stage of Progress_encoded',
        'Collaboration_encoded', 'Connectivity (New / Upgrade)_encoded']

  #Only Keeps Feature that exist
  feature_cols = [c for c in feature_cols if c in ml_df]

  ml_df = ml_df[feature_cols].dropna()

  #Drop Zero variance columns
  zero_var = [c for c in ml_df.columns if ml_df[c].nunique() <= 1]
  if zero_var:
    print(f"Dropping zero Variance: {zero_var}")
    ml_df = ml_df.drop(columns = zero_var)

  return ml_df