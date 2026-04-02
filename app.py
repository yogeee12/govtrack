from flask import Flask, render_template
from config import Config
from models.db import db

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

from routes.public import bp as public_bp
from routes.projects import bp as projects_bp
app.register_blueprint(public_bp)
app.register_blueprint(projects_bp)

if __name__ == "__main__":
    app.run(debug=True)
