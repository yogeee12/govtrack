from flask import Flask, render_template
from config import Config
from models.db import mysql

app = Flask(__name__)
app.config.from_object(Config)

mysql.init_app(app)

@app.route("/")
def home():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT DATABASE();")
    data = cursor.fetchone()
    cursor.close()
    return f"Connected to database: {data}"

if __name__ == "__main__":
    app.run(debug=True)
