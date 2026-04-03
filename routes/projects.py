from flask import Blueprint, render_template, request
from sqlalchemy import text
from models.db import db
import pandas as pd

bp = Blueprint('projects', __name__)
TABLE = 'road_projects'

@bp.route('/projects')
def projects():
    district = request.args.get('district','')
    state = request.args.get('state','')
    scheme = request.args.get('scheme','')
    anomaly_only = request.args.get('anomaly','')

    # Build dynamic query
    where = [] 
    params = {}
    if district:
        where.append("`District Name` = :district")
        params['district'] = district
        
    if state:
        where.append("`State` = :state")
        params['state'] = state
        
    if scheme:
        where.append("`scheme` = :scheme")
        params['scheme'] = scheme
        
    if anomaly_only == '1':
        where.append("`Anomaly` = -1")

    where_sql = "WHERE "+" AND ".join(where) if where else ""
    query = f"SELECT * FROM {TABLE} {where_sql} LIMIT 500"

    with db.engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)
        districts = pd.read_sql(text(f"SELECT DISTINCT 'District Name' FROM {TABLE} ORDER BY `District Name`"), conn)['District Name'].tolist()
        states = pd.read_sql(text(f"SELECT DISTINCT State FROM {TABLE} ORDER BY State"), conn)["State"].tolist()
        schemes = pd.read_sql(text(f"SELECT DISTINCT Scheme FROM {TABLE} ORDER BY Scheme"), conn)["Scheme"].tolist()

        return render_template("projects.html",
                projects = df.to_dict('records'),
                districts = districts, states = states, scheme=schemes,
                selected_district = district, selected_state = state,
                selected_scheme=scheme, anomaly_only=anomaly_only
                )
    
@bp.route('/anomalies')
def anomalies():
    state = request.args.get('state','')
    where = "WHERE Anomaly = -1"
    params = {}
    if state:
        where += " AND State = :state" 
        params['state'] = state

    with db.engine.connect() as conn:
        df = pd.read_sql(
            text(f"SELECT * FROM {TABLE} {where} ORDER BY Anomaly_Score ASC LIMIT 500"),
            conn, params = params
        )
        states = pd.read_sql(text(f"SELECT DISTINCT State FROM {TABLE} ORDER BY State"),conn)["State"].tolist()

    return render_template('anomalies.html',
                           projects = df.to_dict('records'),
                           states= states, selected_state = state)

        