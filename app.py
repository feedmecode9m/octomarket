from flask import Flask, render_template, request
from src.api.routes import api_bp
from src.api.ai_routes import ai_bp
from src.api.simulation_routes import simulation_bp
from src.api.strategy_lab_routes import strategy_lab_bp
from src.api.mentor_routes import mentor_bp
from src.utils.config import get_config
import logging

def create_app():
    """Application factory pattern for creating Flask app."""
    try:
        # Get configuration
        config = get_config()
        
        # Validate configuration
        if not config.validate():
            raise ValueError("Invalid configuration. Check logs for details.")
        
        app = Flask(__name__, 
                    template_folder='static/templates',
                    static_folder='static')
        
        # Configure app with validated settings
        flask_config = config.get_flask_config()
        app.config.update(flask_config)
        
        # Register blueprints
        app.register_blueprint(api_bp)
        app.register_blueprint(ai_bp)
        app.register_blueprint(simulation_bp)
        app.register_blueprint(strategy_lab_bp)
        app.register_blueprint(mentor_bp)
    except Exception as e:
        logging.error(f"Failed to create Flask app: {e}")
        raise
    
    @app.route('/')
    def index():
        """Main dashboard route."""
        try:
            return render_template('index.html')
        except Exception as e:
            logging.error(f"Error rendering index template: {e}")
            return render_template('500.html'), 500

    @app.route('/strategy-lab')
    def strategy_lab():
        """Strategy Lab page."""
        try:
            return render_template('strategy_lab.html')
        except Exception as e:
            logging.error(f"Error rendering strategy lab: {e}")
            return render_template('500.html'), 500

    @app.route('/mentor')
    def mentor_dashboard():
        """AI Trading Mentor dashboard."""
        try:
            return render_template('mentor.html')
        except Exception as e:
            logging.error(f"Error rendering mentor dashboard: {e}")
            return render_template('500.html'), 500
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        logging.warning(f"404 error: {request.url}")
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        logging.error(f"500 error: {error}")
        return render_template('500.html'), 500
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Handle unhandled exceptions."""
        logging.error(f"Unhandled exception: {e}")
        return render_template('500.html'), 500
    
    return app

if __name__ == '__main__':
    try:
        # Get configuration
        config = get_config()
        
        # Create app
        app = create_app()
        
        # Get server settings
        host = config.flask.host
        port = config.flask.port
        debug = config.flask.debug
        
        print("🚀 Starting Real-Time Stock Trading Simulator...")
        print(f"📊 Dashboard available at: http://{host}:{port}")
        print(f"🔧 Debug mode: {debug}")
        print(f"📈 Trading symbol: {config.trading.default_symbol}")
        print(f"💰 Initial cash: ${config.trading.default_initial_cash:,.2f}")
        
        # Start the application
        app.run(host=host, port=port, debug=debug)
        
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        print(f"❌ Failed to start application: {e}")
        exit(1) 