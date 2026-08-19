from flask import Flask, render_template, request
from src.api.routes import api_bp
from src.api.ai_routes import ai_bp
from src.api.simulation_routes import simulation_bp
from src.api.strategy_lab_routes import strategy_lab_bp
from src.api.mentor_routes import mentor_bp
from src.api.terminal_routes import terminal_bp
from src.api.chart_routes import chart_bp
from src.api.execution_routes import execution_bp
from src.api.trade_plan_routes import trade_plan_bp
from src.api.instrument_routes import instrument_bp
from src.api.replay_routes import replay_bp
from src.config.product import get_product, get_product_context
from src.utils.config import get_config
import logging

def create_app():
    """Application factory pattern for creating Flask app."""
    try:
        config = get_config()

        if not config.validate():
            raise ValueError("Invalid configuration. Check logs for details.")

        app = Flask(__name__,
                    template_folder='static/templates',
                    static_folder='static')

        flask_config = config.get_flask_config()
        app.config.update(flask_config)
        app.config["PRODUCT"] = get_product()

        @app.context_processor
        def inject_product():
            return get_product_context()

        app.register_blueprint(api_bp)
        app.register_blueprint(ai_bp)
        app.register_blueprint(simulation_bp)
        app.register_blueprint(strategy_lab_bp)
        app.register_blueprint(mentor_bp)
        app.register_blueprint(terminal_bp)
        app.register_blueprint(execution_bp)
        app.register_blueprint(chart_bp)
        app.register_blueprint(trade_plan_bp)
        app.register_blueprint(instrument_bp)
        app.register_blueprint(replay_bp)
    except Exception as e:
        logging.error(f"Failed to create Flask app: {e}")
        raise

    @app.route('/')
    def home():
        """OctoMarket landing dashboard."""
        try:
            return render_template('home.html')
        except Exception as e:
            logging.error(f"Error rendering home: {e}")
            return render_template('500.html'), 500

    @app.route('/replay')
    def replay():
        """Market replay simulator."""
        try:
            return render_template('index.html', active_nav='replay')
        except Exception as e:
            logging.error(f"Error rendering replay: {e}")
            return render_template('500.html'), 500

    @app.route('/strategy-lab')
    def strategy_lab():
        """Strategy Lab page."""
        try:
            return render_template('strategy_lab.html', active_nav='lab')
        except Exception as e:
            logging.error(f"Error rendering strategy lab: {e}")
            return render_template('500.html'), 500

    @app.route('/mentor')
    def mentor_dashboard():
        """AI Trading Mentor dashboard."""
        try:
            return render_template('mentor.html', active_nav='mentor')
        except Exception as e:
            logging.error(f"Error rendering mentor dashboard: {e}")
            return render_template('500.html'), 500

    @app.route('/terminal')
    def trading_terminal():
        """Live market practice terminal."""
        try:
            return render_template('terminal.html', active_nav='terminal')
        except Exception as e:
            logging.error(f"Error rendering trading terminal: {e}")
            return render_template('500.html'), 500

    @app.route('/academy')
    def academy():
        """Lessons and challenges."""
        try:
            return render_template('academy.html', active_nav='academy')
        except Exception as e:
            logging.error(f"Error rendering academy: {e}")
            return render_template('500.html'), 500

    @app.route('/journal')
    def journal():
        """Trade journal."""
        try:
            return render_template('journal.html', active_nav='journal')
        except Exception as e:
            logging.error(f"Error rendering journal: {e}")
            return render_template('500.html'), 500

    @app.errorhandler(404)
    def not_found(error):
        logging.warning(f"404 error: {request.url}")
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logging.error(f"500 error: {error}")
        return render_template('500.html'), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        logging.error(f"Unhandled exception: {e}")
        return render_template('500.html'), 500

    return app

if __name__ == '__main__':
    try:
        config = get_config()
        app = create_app()
        product = get_product()

        host = config.flask.host
        port = config.flask.port
        debug = config.flask.debug

        print(f"🚀 Starting {product['name']} v{product['version']}...")
        print(f"📊 {product['tagline']}")
        print(f"🌐 Dashboard: http://{host}:{port}")
        print(f"🔧 Debug mode: {debug}")
        print(f"📈 Default symbol: {config.trading.default_symbol}")
        print(f"💰 Initial cash: ${config.trading.default_initial_cash:,.2f}")

        app.run(host=host, port=port, debug=debug)

    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        print(f"❌ Failed to start application: {e}")
        exit(1)
