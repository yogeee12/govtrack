import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
import joblib
from sqlalchemy import create_engine
import pymysql

engine = create_engine("mysql+pymysql://root:E=mc*2@localhost/govtrack")
df = pd.read_sql("SELECT * FROM road_projects", con=engine)
df = df.dropna(subset=["Cost Per Km","District Name","State","Scheme","Connectivity (New / Upgrade)", "Road Length (Kms)"])

le_state    = LabelEncoder()
le_district = LabelEncoder()
le_scheme   = LabelEncoder()
le_conn     = LabelEncoder()

df['State_enc']    = le_state.fit_transform(df['State'])
df['District_enc'] = le_district.fit_transform(df['District Name'])
df['Scheme_enc']   = le_scheme.fit_transform(df['Scheme'])
df['Conn_enc']     = le_conn.fit_transform(df['Connectivity (New / Upgrade)'])

feature_cols = ['State_enc', 'District_enc', 'Road Length (Kms)', 'Conn_enc', 'Scheme_enc']
X = df[feature_cols]
y = df['Cost Per Km']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

score = model.score(X_test, y_test)
print(f"R² Score: {score:.3f}")

importances = model.feature_importances_
for name, imp in zip(feature_cols, importances):
    print(f"{name}: {imp:.3f}")

joblib.dump({
    'model': model,
    'le_state': le_state,
    'le_district': le_district,
    'le_scheme': le_scheme,
    'le_conn': le_conn
}, 'cost_estimater.pkl')
