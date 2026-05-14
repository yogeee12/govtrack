# 🗺️ GovTrack — Government Road Project Transparency Portal

> **ML-Powered Analysis of PMGSY Rural Road Construction Projects Across India**

GovTrack is a Flask-based web application that ingests raw government road construction data, detects anomalous projects using **Isolation Forest**, and provides a **Random Forest-based cost estimator** — all through an interactive dashboard.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📊 **Interactive Dashboard** | Filter by State & District with live Chart.js visualisations (stage progress, road length, anomalies, scheme breakdown) — each chart has an auto-generated analysis summary |
| ⚠️ **Anomaly Detection** | IsolationForest (scikit-learn) flags ~5% of projects as statistically unusual based on cost, progress, and age |
| 💰 **Cost Estimator** | Enter road specs → RandomForestRegressor predicts Cost/Km, compares with district average, and shows 10 similar real projects |
| 🔍 **Project Explorer** | Searchable, filterable data grid of all projects with dynamic State→District filtering |
| 🔄 **Automated ETL Pipeline** | Cleans messy PMGSY spreadsheets (regex metadata extraction, Indian number format, missing values, feature engineering) and loads into MySQL |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3, Flask, Jinja2, SQLAlchemy |
| **Database** | MySQL (via PyMySQL) |
| **ML Models** | scikit-learn — `IsolationForest`, `RandomForestRegressor` |
| **Data Processing** | Pandas, NumPy, Joblib |
| **Frontend** | HTML, CSS, JavaScript, Chart.js |
| **Deployment** | Gunicorn-ready |

---

## 📁 Project Structure

```
govtrack/
├── app.py                          # Flask entry point
├── config.py                       # DB credentials & app config
├── requirements.txt                # Python dependencies
│
├── pipeline/
│   ├── govtrack_pipeline.py        # ETL + IsolationForest anomaly detection
│   ├── cost_estimator_pipeline.py  # Train & save RandomForest cost model
│   └── auto_load.py                # Batch-load all CSV/XLSX into MySQL
│
├── models/
│   ├── db.py                       # SQLAlchemy init
│   └── cost_estimater.pkl          # Serialised cost model + encoders
│
├── routes/
│   ├── public.py                   # /, /dashboard, /estimator
│   └── projects.py                 # /projects, /anomalies
│
├── templates/                      # Jinja2 HTML templates
├── static/css/style.css            # All styling
└── data/                           # Raw PMGSY CSV files (12 files, 3 states)
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- MySQL server running with a database called `govtrack`

### Setup

```bash
# Clone
git clone https://github.com/yogeee12/govtrack.git
cd govtrack

# Virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Load data into MySQL
python -m pipeline.auto_load

# Train cost estimation model
python pipeline/cost_estimator_pipeline.py

# Run the app
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

---

## 🤖 ML Models

### 1. Isolation Forest — Anomaly Detection
- **Type**: Unsupervised
- **Purpose**: Flags projects with unusual cost patterns, completion ratios, or financial progress
- **Config**: 100 trees, 5% contamination rate
- **Features**: Cost/Km, Completion Ratio, Financial Progress, Project Age, Road Length, and more
- **Output**: `Anomaly` (-1 = suspicious, 1 = normal) + continuous `Anomaly_Score`

### 2. Random Forest Regressor — Cost Estimation
- **Type**: Supervised (trained on historical data)
- **Purpose**: Predicts expected Cost Per Km for a proposed road
- **Config**: 100 trees, 80/20 train-test split
- **Features**: State, District, Road Length, Connectivity Type, Scheme
- **Output**: Predicted Cost Per Km (₹ Lakhs)

---

## 📊 Data Source

Raw data sourced from the **PMGSY OMMS Portal** ([omms.nic.in](https://omms.nic.in)):
- Himachal Pradesh (PMGSY I, II, III, IV)
- Madhya Pradesh (PMGSY II, III, PM-JANMAN, RCPLWEA)
- Manipur (PMGSY I, II, III, PM-JANMAN)

---

## 📸 Pages

| Page | URL | Description |
|---|---|---|
| Home | `/` | Summary cards + quick navigation |
| Dashboard | `/dashboard` | 4 charts with filters + analysis boxes |
| Projects | `/projects` | Filterable data grid (500 rows) |
| Anomalies | `/anomalies` | ML-flagged suspicious projects |
| Estimator | `/estimator` | Cost prediction form + comparison |

---

## 📄 License

This project is part of a Final Year academic project.

---

*Built with ❤️ using Flask, scikit-learn & Chart.js*