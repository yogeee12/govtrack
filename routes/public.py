from flask import Blueprint, render_template, request
from sqlalchemy import text
from models.db import db
import pandas as pd
import json
import joblib

bp = Blueprint("public", __name__)

TABLE = "road_projects"


def _normalize_connectivity_for_encoder(raw, le):
    """Align form values with labels the fitted le_conn was trained on."""
    v = (raw or "").strip()
    classes = [str(c) for c in getattr(le, "classes_", [])]
    if not classes:
        return v
    if v in classes:
        return v
    by_lower = {c.lower(): c for c in classes}
    if v.lower() in by_lower:
        return by_lower[v.lower()]
    # PMGSY source files often spell upgrade as "Upgarde"; model was fit on that text.
    if v == "Upgrade" and "Upgarde" in classes:
        return "Upgarde"
    if v.lower() in ("upgrade existing", "upgrade_existing") and "Upgarde" in classes:
        return "Upgarde"
    return v


@bp.route('/')
def home():
    with db.engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar()
        total_km = conn.execute(text(f"SELECT ROUND(SUM(`Road Length (Kms)`),1) FROM {TABLE}")).scalar()
        anomalies = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE} WHERE Anomaly = -1")).scalar()
        state = conn.execute(text(f"SELECT COUNT(DISTINCT State) FROM {TABLE}")).scalar()
        scheme = conn.execute(text(f"SELECT COUNT(DISTINCT Scheme) FROM {TABLE}")).scalar()

    return render_template('index.html', total=total, total_km=total_km, anomalies=anomalies, state=state, scheme=scheme)

def _dashboard_num(value, cast, default):
    """Coerce DB/pandas aggregates for dashboard summary (NULL / NaN safe)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    return cast(value)


def _dashboard_where(state_arg, district_arg):
    """Build WHERE clauses and bound params for dashboard filters (never interpolate user strings into SQL)."""
    state = (state_arg or "") or None
    district = (district_arg or "") or None
    if district and not state:
        district = None
    geo_parts = []
    params = {}
    if state:
        geo_parts.append("TRIM(State) = TRIM(:st)")
        params["st"] = state
    if district:
        geo_parts.append("TRIM(`District Name`) = TRIM(:dist)")
        params["dist"] = district
    where_geo = (" WHERE " + " AND ".join(geo_parts)) if geo_parts else ""
    anom_parts = list(geo_parts) + ["Anomaly = -1"]
    where_anom = " WHERE " + " AND ".join(anom_parts)
    # Strip for display only
    display_state = state.strip() if state else state
    display_district = district.strip() if district else district
    return where_geo, where_anom, params, display_state, display_district


@bp.route('/dashboard')
def dashboard():
    where_geo, where_anom, filt_params, selected_state, selected_district = _dashboard_where(
        request.args.get("state"), request.args.get("district")
    )

    with db.engine.connect() as conn:
        state_list = pd.read_sql(
            text(f"SELECT DISTINCT State FROM {TABLE} ORDER BY State"), conn
        )["State"].tolist()

        all_pairs = pd.read_sql(
            text(f"SELECT DISTINCT State, `District Name` FROM {TABLE} ORDER BY State, `District Name`"),
            conn,
        )
        district_by_state = {}
        for _, row in all_pairs.iterrows():
            sk = row["State"]
            district_by_state.setdefault(sk, []).append(row["District Name"])
        district_by_state_json = json.dumps(district_by_state)

        stage = pd.read_sql(
            text(
                f"SELECT `Stage of Progress`, COUNT(*) as cnt FROM {TABLE}{where_geo} "
                f"GROUP BY `Stage of Progress` ORDER BY cnt DESC"
            ),
            conn,
            params=filt_params,
        )
        if stage.empty:
            stage_labels, stage_vals = ["No records in filter"], [0]
        else:
            stage_labels = stage["Stage of Progress"].tolist()
            stage_vals = stage["cnt"].tolist()

        if selected_state and not selected_district:
            dist_sql = (
                f"SELECT `District Name`, ROUND(SUM(`Road Length (Kms)`),1) as km FROM {TABLE}{where_geo} "
                f"GROUP BY `District Name` ORDER BY km DESC LIMIT 10"
            )
            anom_sql = (
                f"SELECT `District Name`, COUNT(*) as cnt FROM {TABLE}{where_anom} "
                f"GROUP BY `District Name` ORDER BY cnt DESC LIMIT 10"
            )
        elif selected_state and selected_district:
            dist_sql = (
                f"SELECT `District Name`, ROUND(SUM(`Road Length (Kms)`),1) as km FROM {TABLE}{where_geo} "
                f"GROUP BY `District Name`"
            )
            anom_sql = (
                f"SELECT `District Name`, COUNT(*) as cnt FROM {TABLE}{where_anom} "
                f"GROUP BY `District Name`"
            )
        else:
            dist_sql = (
                f"SELECT `District Name`, ROUND(SUM(`Road Length (Kms)`),1) as km FROM {TABLE} "
                f"GROUP BY `District Name` ORDER BY km DESC LIMIT 10"
            )
            anom_sql = (
                f"SELECT `District Name`, COUNT(*) as cnt FROM {TABLE}{where_anom} "
                f"GROUP BY `District Name` ORDER BY cnt DESC LIMIT 10"
            )

        district_df = pd.read_sql(text(dist_sql), conn, params=filt_params)
        anom_dist = pd.read_sql(text(anom_sql), conn, params=filt_params)

        if not selected_state:
            breakdown = pd.read_sql(
                text(f"SELECT State, COUNT(*) as cnt FROM {TABLE} GROUP BY State ORDER BY cnt DESC"),
                conn,
            )
            breakdown_title = "Projects by State"
            if breakdown.empty:
                breakdown_labels, breakdown_vals = ["No data"], [0]
            else:
                breakdown_labels = breakdown["State"].tolist()
                breakdown_vals = breakdown["cnt"].tolist()
        else:
            breakdown = pd.read_sql(
                text(
                    f"SELECT Scheme, COUNT(*) as cnt FROM {TABLE}{where_geo} "
                    f"GROUP BY Scheme ORDER BY cnt DESC"
                ),
                conn,
                params=filt_params,
            )
            breakdown_title = (
                "Projects by Scheme (selected district)"
                if selected_district
                else "Projects by Scheme (within selected state)"
            )
            if breakdown.empty:
                breakdown_labels, breakdown_vals = ["No data"], [0]
            else:
                breakdown_labels = breakdown["Scheme"].tolist()
                breakdown_vals = breakdown["cnt"].tolist()

        summary = pd.read_sql(
            text(
                f"SELECT COUNT(*) as n_proj, "
                f"COALESCE(ROUND(SUM(`Road Length (Kms)`), 1), 0) as km_sum, "
                f"COALESCE(SUM(CASE WHEN Anomaly = -1 THEN 1 ELSE 0 END), 0) as n_anom "
                f"FROM {TABLE}{where_geo}"
            ),
            conn,
            params=filt_params,
        ).iloc[0]

        n_proj = _dashboard_num(summary["n_proj"], int, 0)
        km_sum = _dashboard_num(summary["km_sum"], float, 0.0)
        n_anom = _dashboard_num(summary["n_anom"], int, 0)

        if selected_state and selected_district:
            filter_label = f"{selected_district}, {selected_state}"
        elif selected_state:
            filter_label = selected_state
        else:
            filter_label = "All states (national view)"

        # ── Analysis text for each chart ──────────────────────────
        # 1. Stage of Progress analysis
        if not stage.empty:
            total_stage = int(stage["cnt"].sum())
            top_stage = stage.iloc[0]["Stage of Progress"]
            top_pct = round(stage.iloc[0]["cnt"] / total_stage * 100, 1) if total_stage else 0
            completed_row = stage[stage["Stage of Progress"].str.contains("Completed", case=False, na=False)]
            completed_pct = round(completed_row["cnt"].sum() / total_stage * 100, 1) if total_stage else 0
            stage_analysis = (
                f"Out of {total_stage:,} projects, the dominant stage is \"{top_stage}\" ({top_pct}%). "
                f"Overall completion rate is {completed_pct}% of all projects in this selection."
            )
        else:
            stage_analysis = "No project data found for the selected filter."

        # 2. Road length by district analysis
        if not district_df.empty:
            top_dist = district_df.iloc[0]["District Name"].strip()
            top_km = district_df.iloc[0]["km"]
            total_km_chart = district_df["km"].sum()
            top3_km = district_df.head(3)["km"].sum()
            top3_pct = round(top3_km / total_km_chart * 100, 1) if total_km_chart else 0
            district_analysis = (
                f"Leading district: {top_dist} with {top_km} km of sanctioned road. "
                f"The top 3 districts account for {top3_pct}% of the displayed road length ({top3_km} km out of {total_km_chart} km)."
            )
        else:
            district_analysis = "No road length data available for the selected filter."

        # 3. Anomaly by district analysis
        if not anom_dist.empty:
            top_anom_dist = anom_dist.iloc[0]["District Name"].strip()
            top_anom_cnt = int(anom_dist.iloc[0]["cnt"])
            total_anom_chart = int(anom_dist["cnt"].sum())
            anom_pct_of_all = round(n_anom / n_proj * 100, 1) if n_proj else 0
            anomaly_analysis = (
                f"{top_anom_dist} has the most flagged projects ({top_anom_cnt}). "
                f"In total, {n_anom:,} out of {n_proj:,} projects ({anom_pct_of_all}%) are flagged as anomalous across this selection."
            )
        else:
            anomaly_analysis = "No anomalies were detected in the selected filter."

        # 4. Breakdown analysis
        if breakdown_labels[0] not in ("No data",):
            top_brk = breakdown_labels[0].strip() if isinstance(breakdown_labels[0], str) else str(breakdown_labels[0])
            top_brk_cnt = breakdown_vals[0]
            total_brk = sum(breakdown_vals)
            top_brk_pct = round(top_brk_cnt / total_brk * 100, 1) if total_brk else 0
            if not selected_state:
                breakdown_analysis = (
                    f"\"{top_brk}\" leads with {top_brk_cnt:,} projects ({top_brk_pct}% of all). "
                    f"There are {len(breakdown_labels)} states represented in the data."
                )
            else:
                breakdown_analysis = (
                    f"The most active scheme is \"{top_brk}\" with {top_brk_cnt:,} projects ({top_brk_pct}%). "
                    f"{len(breakdown_labels)} scheme(s) operate within the selection."
                )
        else:
            breakdown_analysis = "No breakdown data available for the selected filter."

        return render_template(
            "dashboard.html",
            state_list=state_list,
            selected_state=selected_state or "",
            selected_district=selected_district or "",
            district_by_state=district_by_state_json,
            filter_label=filter_label,
            summary_projects=n_proj,
            summary_km=km_sum,
            summary_anomalies=n_anom,
            stage_data=json.dumps({"labels": stage_labels, "values": stage_vals}),
            district_data=json.dumps(
                {
                    "labels": district_df["District Name"].tolist(),
                    "values": district_df["km"].tolist(),
                }
            ),
            anomaly_data=json.dumps(
                {
                    "labels": anom_dist["District Name"].tolist(),
                    "values": anom_dist["cnt"].tolist(),
                }
            ),
            breakdown_data=json.dumps(
                {"labels": breakdown_labels, "values": breakdown_vals}
            ),
            breakdown_title=breakdown_title,
            district_chart_title=(
                "Road length — selected district"
                if selected_district
                else (
                    "Road length by district (Top 10 in state)"
                    if selected_state
                    else "Road Length by District (Top 10)"
                )
            ),
            anomaly_chart_title=(
                "Anomalies — selected district"
                if selected_district
                else (
                    "Anomaly count by district (Top 10 in state)"
                    if selected_state
                    else "Anomalies by District (Top 10)"
                )
            ),
            stage_analysis=stage_analysis,
            district_analysis=district_analysis,
            anomaly_analysis=anomaly_analysis,
            breakdown_analysis=breakdown_analysis,
        )

@bp.route('/estimator', methods=['GET','POST'])
def estimator():
    result = None
    real_projects = []
    #get filter option for dropdowns
    with db.engine.connect() as conn:
        district = pd.read_sql(text(f"SELECT DISTINCT `District Name` FROM {TABLE} ORDER BY 'District Name'"), conn)['District Name'].tolist()
        state = pd.read_sql(text(f"SELECT DISTINCT State FROM {TABLE} ORDER BY state"), conn)['State'].tolist()
        schemes   = pd.read_sql(text(f"SELECT DISTINCT Scheme FROM {TABLE} ORDER BY Scheme"), conn)['Scheme'].tolist()

        # Build state → district mapping for JS filter
        all_pairs = pd.read_sql(
            text(f"SELECT DISTINCT State, `District Name` FROM {TABLE} ORDER BY State, `District Name`"),
            conn
        )
        district_by_state = {}
        for _, row in all_pairs.iterrows():
            state_key = row['State']
            if state_key not in district_by_state:
                district_by_state[state_key] = []
            district_by_state[state_key].append(row['District Name'])

        district_by_state_json = json.dumps(district_by_state)

        if request.method == "POST":
            selected_state = request.form['state']
            selected_scheme = request.form['scheme']
            selected_district = request.form['district']
            road_length = float(request.form['road_length'])
            connectivity = request.form['connectivity']

            bundle = joblib.load('models/cost_estimater.pkl')
            model = bundle['model']
            le_s = bundle['le_state']
            le_sc = bundle['le_scheme']
            le_d = bundle['le_district']
            le_c = bundle['le_conn']

            try:
                s_enc = le_s.transform([selected_state])[0]
                sc_enc = le_sc.transform([selected_scheme])[0]
                d_enc = le_d.transform([selected_district])[0]
                conn_label = _normalize_connectivity_for_encoder(connectivity, le_c)
                c_enc = le_c.transform([conn_label])[0]

                cost_per_km = model.predict([[s_enc ,d_enc, road_length, c_enc ,sc_enc]])[0]
                total = round(cost_per_km * road_length, 2)

                district_avg = conn.execute(
                    text(f"SELECT AVG(`Cost Per Km`) FROM {TABLE} WHERE `District Name` = :d"),
                    {'d': selected_district}
                ).scalar() or 0
                district_avg = round(district_avg, 2)

                # Step 6 — reason string
                diff = ((cost_per_km - district_avg) / district_avg * 100) if district_avg else 0
                if diff > 20:
                    reason = f"Predicted cost is {diff:.0f}% above district average — likely due to terrain or road type."
                elif diff < -20:
                    reason = f"Predicted cost is {abs(diff):.0f}% below district average — possibly a simpler or shorter road."
                else:
                    reason = f"Predicted cost is within normal range for {selected_district.strip()} (±{abs(diff):.0f}% of average)."

                # Step 7 — 10 real similar projects
                real_projects = pd.read_sql(
                    text(f"SELECT `District Name`, State, Scheme, `Road Length (Kms)`, `Sanction Cost`, `Cost Per Km`, `Stage of Progress`, Anomaly FROM {TABLE} WHERE `District Name` = :d ORDER BY ABS(`Cost Per Km` - :pred) ASC LIMIT 10"),
                    conn,
                    params={'d': selected_district, 'pred': round(cost_per_km, 2)}
                ).to_dict('records')

                result = {
                    'cost_per_km':   round(cost_per_km, 2),
                    'total':         total,
                    'district':      selected_district,
                    'state':         selected_state,
                    'scheme':        selected_scheme,
                    'connectivity':  connectivity,
                    'km':            road_length,
                    'district_avg':  district_avg,
                    'reason':        reason
                }
            except Exception as e:
                result = {"error" : str(e)}

    return render_template('estimator.html',
        result=result,
        real_projects=real_projects,
        districts=district,
        states=state,
        schemes=schemes,
        district_by_state=district_by_state_json
    )
    