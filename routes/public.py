from flask import Blueprint, render_template, request
from sqlalchemy import text
from models.db import db
import pandas as pd
import json
import joblib

bp = Blueprint("public", __name__)

TABLE = "road_projects"

@bp.route('/')
def home():
    with db.engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar()
        total_km = conn.execute(text(f"SELECT ROUND(SUM('Road Length (kms)'),1) FROM {TABLE}")).scalar()
        anomalies = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE} WHERE Anomaly = -1")).scalar()
        state = conn.execute(text(f"SELECT COUNT(DISTINCT State) FROM {TABLE}")).scalar()
        scheme = conn.execute(text(f"SELECT COUNT(DISTINCT Scheme) FROM {TABLE}")).scalar()

    return render_template('index.html', total=total, total_km=total_km, anomalies=anomalies, state=state, scheme=scheme)

@bp.route('/dashboard')
def dashboard():
    with db.engine.connect() as conn:
        # Stage of progress distribution
        stage = pd.read_sql(text(f"SELECT 'Stage of Progress', count(*) as cnt FROM {TABLE} GROUP BY 'Stage of Progress' ORDER BY cnt DESC"),conn)
        # Road length by district (top 10)
        district = pd.read_sql(text(f"SELECT 'District Name', ROUND(SUM('Road Length (Kms)'),1) as km FROM {TABLE} GROUP BY 'District Name' ORDER BY km DESC LIMIT 10"),conn)
        # Anomalies by district (top 10)
        anom_dist = pd.read_sql(text(f"SELECT 'District Name', COUNT(*) as cnt FROM {TABLE} WHERE Anomaly = -1 GROUP BY 'District Name' ORDER BY cnt DESC LIMIT 10"), conn)
        # Projects by state
        by_state = pd.read_sql(text(f"SELECT State, COUNT(*) as cnt FROM {TABLE} GROUP BY State ORDER BY cnt DESC"), conn)

        return render_template('dashboard.html',
                               stage_data = json.dumps({'labels': stage['Stage of Progress'].tolist(), 'values': stage['cnt'].tolist()}),
                               district_data = json.dumps({'labels': district['District Name'].tolist(), 'values': district['km'].tolist()}),
                               anomaly_data = json.dumps({'labels': anom_dist['District Name'].tolist(), 'values': anom_dist['cnt'].tolist()}),
                               state_data = json.dumps({'labels': by_state['State'].tolist(), 'values': by_state['cnt'].tolist()}),
                               )

@bp.route('/estimator', methods=['GET','POST'])
def estimator():
    result = None
    #get filter option for dropdowns
    with db.engine.connect() as conn:
        district = pd.read_sql(text(f"SELECT DISTINCT 'District Name' FROM {TABLE} ORDER BY 'District Name'"), conn)['District Name'].tolist()
        state = pd.read_sql(text(f"SELECT DISTINCT State FROM {TABLE} ORDER BY state"), conn)

        if request == "POST":
            district = request.form['district']
            road_length = float(request.form['road_length'])
            connectivity = request.form['connectivity']

            bundle = joblib.load('models/cost_estimater.pkl')
            model = bundle['model']
            le_d = bundle['le_district']
            le_c = bundle['le_conn']

            try:
                d_enc = le_d.transform([district])[0]
                c_enc = le_c.transform([connectivity])[0]
                cost_per_km = model.predict([[d_enc, road_length, c_enc]])[0]
                total = round(cost_per_km * road_length, 2)
                result = {"cost_per_km" : round(cost_per_km, 2), "total" : total, "district": district, "km":road_length}
            except Exception as e:
                result = {"error" : str(e)}

        return render_template('estimator.html', result=result, district=district, state=state)
    