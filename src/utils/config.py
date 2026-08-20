import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class TradingConfig:
    """Configuration for trading parameters."""
    default_symbol: str = "AAPL"
    default_interval: str = "1m"
    default_period: str = "1d"
    default_initial_cash: float = 50000.0
    default_short_window: int = 5
    default_long_window: int = 20
    default_profit_threshold: float = 0.015
    default_stop_loss: float = 0.01
    default_rsi_window: int = 14
    max_retries: int = 5
    retry_delay: int = 10
    risk_per_trade: float = 0.02
    max_portfolio_values: int = 100
    simulation_sleep_time: int = 10
    historical_sleep_time: float = 0.5

@dataclass
class FlaskConfig:
    """Configuration for Flask application."""
    debug: bool = True
    secret_key: str = "dev-secret-key-change-in-production"
    host: str = "0.0.0.0"
    port: int = 5000
    max_content_length: int = 16 * 1024 * 1024  # 16MB

@dataclass
class LoggingConfig:
    """Configuration for logging."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None

class Config:
    """Main configuration class that manages all application settings."""
    
    def __init__(self):
        self.trading = TradingConfig()
        self.flask = FlaskConfig()
        self.logging = LoggingConfig()
        self._load_from_environment()
        self._setup_logging()
    
    def _load_from_environment(self):
        """Load configuration from environment variables."""
        # Flask Configuration — production defaults to debug off; local keeps debug on.
        env_name = (
            os.environ.get("ENV")
            or os.environ.get("FLASK_ENV")
            or os.environ.get("RAILWAY_ENVIRONMENT")
            or "development"
        ).lower()
        self.environment = env_name
        default_debug = "false" if env_name in ("production", "prod") else "true"
        self.flask.debug = os.environ.get("FLASK_DEBUG", default_debug).lower() == "true"
        self.flask.secret_key = os.environ.get('SECRET_KEY', self.flask.secret_key)
        self.flask.host = os.environ.get('HOST', self.flask.host)
        self.flask.port = int(os.environ.get('PORT', self.flask.port))
        
        # Trading Configuration
        self.trading.default_symbol = os.environ.get('DEFAULT_SYMBOL', self.trading.default_symbol)
        self.trading.default_interval = os.environ.get('DEFAULT_INTERVAL', self.trading.default_interval)
        self.trading.default_period = os.environ.get('DEFAULT_PERIOD', self.trading.default_period)
        self.trading.default_initial_cash = float(os.environ.get('DEFAULT_INITIAL_CASH', self.trading.default_initial_cash))
        self.trading.default_short_window = int(os.environ.get('DEFAULT_SHORT_WINDOW', self.trading.default_short_window))
        self.trading.default_long_window = int(os.environ.get('DEFAULT_LONG_WINDOW', self.trading.default_long_window))
        self.trading.default_profit_threshold = float(os.environ.get('DEFAULT_PROFIT_THRESHOLD', self.trading.default_profit_threshold))
        self.trading.default_stop_loss = float(os.environ.get('DEFAULT_STOP_LOSS', self.trading.default_stop_loss))
        self.trading.max_retries = int(os.environ.get('MAX_RETRIES', self.trading.max_retries))
        self.trading.retry_delay = int(os.environ.get('RETRY_DELAY', self.trading.retry_delay))
        
        # Logging Configuration
        self.logging.level = os.environ.get('LOG_LEVEL', self.logging.level)
        self.logging.file = os.environ.get('LOG_FILE', self.logging.file)
    
    def _setup_logging(self):
        """Setup logging configuration."""
        handlers = [logging.StreamHandler()]
        
        if self.logging.file:
            try:
                handlers.append(logging.FileHandler(self.logging.file))
            except Exception as e:
                logging.warning(f"Could not setup file logging: {e}")
        
        logging.basicConfig(
            level=getattr(logging, self.logging.level.upper()),
            format=self.logging.format,
            handlers=handlers
        )
    
    def validate(self) -> bool:
        """Validate configuration values."""
        errors = []
        
        # Validate trading parameters
        if self.trading.default_initial_cash <= 0:
            errors.append("DEFAULT_INITIAL_CASH must be positive")
        
        if self.trading.default_short_window >= self.trading.default_long_window:
            errors.append("DEFAULT_SHORT_WINDOW must be less than DEFAULT_LONG_WINDOW")
        
        if not (0 < self.trading.default_profit_threshold < 1):
            errors.append("DEFAULT_PROFIT_THRESHOLD must be between 0 and 1")
        
        if not (0 < self.trading.default_stop_loss < 1):
            errors.append("DEFAULT_STOP_LOSS must be between 0 and 1")
        
        if self.trading.max_retries <= 0:
            errors.append("MAX_RETRIES must be positive")
        
        # Validate Flask parameters
        if self.flask.port < 1 or self.flask.port > 65535:
            errors.append("PORT must be between 1 and 65535")
        
        if errors:
            for error in errors:
                logging.error(f"Configuration error: {error}")
            return False
        
        return True
    
    def get_trading_config(self) -> Dict[str, Any]:
        """Get trading configuration as dictionary."""
        return {
            'symbol': self.trading.default_symbol,
            'interval': self.trading.default_interval,
            'period': self.trading.default_period,
            'initial_cash': self.trading.default_initial_cash,
            'short_window': self.trading.default_short_window,
            'long_window': self.trading.default_long_window,
            'profit_threshold': self.trading.default_profit_threshold,
            'stop_loss': self.trading.default_stop_loss,
            'rsi_window': self.trading.default_rsi_window,
            'max_retries': self.trading.max_retries,
            'retry_delay': self.trading.retry_delay,
            'risk_per_trade': self.trading.risk_per_trade,
            'max_portfolio_values': self.trading.max_portfolio_values,
            'simulation_sleep_time': self.trading.simulation_sleep_time,
            'historical_sleep_time': self.trading.historical_sleep_time
        }
    
    def get_flask_config(self) -> Dict[str, Any]:
        """Get Flask configuration as dictionary."""
        return {
            'DEBUG': self.flask.debug,
            'SECRET_KEY': self.flask.secret_key,
            'MAX_CONTENT_LENGTH': self.flask.max_content_length
        }

# Global configuration instance
config = Config()

def get_config() -> Config:
    """Get the global configuration instance."""
    return config 