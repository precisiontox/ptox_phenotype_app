from flask import Flask
from .routes.main import main_bp
from .routes.experiments import experiments_bp
from .routes.compare import compare_bp
from .routes.explore import explore_bp
from .routes.api import api_bp
from .db import close_db
from config import Config
import atexit
from werkzeug.middleware.proxy_fix import ProxyFix


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    # app.config["APPLICATION_ROOT"] = "/phenotype"
    Config.validate()
    
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    app.register_blueprint(main_bp)
    app.register_blueprint(experiments_bp, url_prefix="/experiments")
    app.register_blueprint(compare_bp, url_prefix="/compare")
    app.register_blueprint(explore_bp, url_prefix="/explore")
    app.register_blueprint(api_bp, url_prefix="/api")

    atexit.register(close_db)

    return app