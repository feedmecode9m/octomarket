import yfinance as yf
import pandas as pd
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from functools import lru_cache
import threading
import numpy as np

logger = logging.getLogger(__name__)

class DataFetcher:
    """Enhanced stock data fetcher with improved caching and real-time data handling."""
    
    def __init__(self, symbol="AAPL", interval="1m", period="1d", max_retries=5, retry_delay=10, start_date=None):
        self.symbol = symbol.upper()
        self.interval = interval
        self.period = period
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.start_date = start_date
        self.last_data = pd.DataFrame()
        self.last_fetch_time = None
        self._cache = {}
        self._cache_lock = threading.Lock()
        self._last_error = None
        self._consecutive_failures = 0
        self._max_cache_age = 30  # Reduced cache time for more frequent updates
        self._data_buffer = []  # Buffer for storing recent data points
        self._max_buffer_size = 100  # Keep last 100 data points
        
        # Validate inputs
        self._validate_parameters()
    
    def _validate_parameters(self):
        """Validate initialization parameters."""
        if not self.symbol or len(self.symbol) > 10:
            raise ValueError("Invalid symbol")
        
        valid_intervals = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo']
        if self.interval not in valid_intervals:
            raise ValueError(f"Invalid interval. Must be one of: {valid_intervals}")
        
        if self.max_retries < 1:
            raise ValueError("max_retries must be at least 1")
        
        if self.retry_delay < 1:
            raise ValueError("retry_delay must be at least 1")
    
    def _get_cache_key(self) -> str:
        """Generate cache key for current request."""
        return f"{self.symbol}_{self.interval}_{self.period}_{self.start_date}"
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cached data is still valid."""
        if not cache_entry:
            return False
        
        cache_time = cache_entry.get('timestamp')
        if not cache_time:
            return False
        
        age = time.time() - cache_time
        return age < self._max_cache_age
    
    def _get_cached_data(self) -> Optional[pd.DataFrame]:
        """Get data from cache if valid."""
        with self._cache_lock:
            cache_key = self._get_cache_key()
            cache_entry = self._cache.get(cache_key)
            
            if self._is_cache_valid(cache_entry):
                logger.debug(f"Using cached data for {self.symbol}")
                return cache_entry['data'].copy()
        
        return None
    
    def _cache_data(self, data: pd.DataFrame):
        """Cache the fetched data."""
        with self._cache_lock:
            cache_key = self._get_cache_key()
            self._cache[cache_key] = {
                'data': data.copy(),
                'timestamp': time.time()
            }
            
            # Clean old cache entries
            self._clean_cache()
    
    def _clean_cache(self):
        """Remove old cache entries to prevent memory leaks."""
        current_time = time.time()
        keys_to_remove = []
        
        for key, entry in self._cache.items():
            if current_time - entry['timestamp'] > self._max_cache_age * 2:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._cache[key]
    
    def _handle_api_error(self, error: Exception, attempt: int) -> bool:
        """Handle API errors with exponential backoff."""
        self._last_error = str(error)
        self._consecutive_failures += 1
        
        logger.warning(f"API error for {self.symbol} (attempt {attempt}/{self.max_retries}): {error}")
        
        # Exponential backoff
        backoff_delay = min(self.retry_delay * (2 ** (attempt - 1)), 60)
        
        if attempt < self.max_retries:
            logger.info(f"Retrying in {backoff_delay} seconds...")
            time.sleep(backoff_delay)
            return True
        
        return False
    
    def _validate_data(self, data: pd.DataFrame) -> bool:
        """Validate fetched data."""
        if data.empty:
            return False
        
        required_columns = ["Open", "High", "Low", "Close", "Volume"]
        if not all(col in data.columns for col in required_columns):
            logger.error(f"Data missing required columns. Available: {data.columns.tolist()}")
            return False
        
        # Check for reasonable price values
        if data["Close"].min() <= 0 or data["Close"].max() > 10000:
            logger.warning(f"Suspicious price values in data: {data['Close'].describe()}")
        
        # Check for reasonable volume values
        if data["Volume"].min() < 0:
            logger.warning("Negative volume values found")
            return False
        
        return True
    
    def _add_synthetic_data_points(self, data: pd.DataFrame) -> pd.DataFrame:
        """Add synthetic data points for smoother charts when data is sparse."""
        if len(data) < 10:  # Only add synthetic points if we have very few data points
            # Create more data points by interpolating between existing ones
            extended_data = []
            
            for i in range(len(data) - 1):
                current_row = data.iloc[i]
                next_row = data.iloc[i + 1]
                
                # Add current row
                extended_data.append(current_row)
                
                # Add interpolated points between current and next
                for j in range(1, 4):  # Add 3 interpolated points
                    factor = j / 4
                    interpolated_row = current_row.copy()
                    
                    # Interpolate price data
                    interpolated_row['Open'] = current_row['Open'] + (next_row['Open'] - current_row['Open']) * factor
                    interpolated_row['High'] = current_row['High'] + (next_row['High'] - current_row['High']) * factor
                    interpolated_row['Low'] = current_row['Low'] + (next_row['Low'] - current_row['Low']) * factor
                    interpolated_row['Close'] = current_row['Close'] + (next_row['Close'] - current_row['Close']) * factor
                    interpolated_row['Volume'] = current_row['Volume'] + (next_row['Volume'] - current_row['Volume']) * factor
                    
                    # Create interpolated timestamp
                    current_time = current_row.name
                    next_time = next_row.name
                    time_diff = next_time - current_time
                    interpolated_time = current_time + time_diff * factor
                    interpolated_row.name = interpolated_time
                    
                    extended_data.append(interpolated_row)
            
            # Add the last row
            if len(data) > 0:
                extended_data.append(data.iloc[-1])
            
            return pd.DataFrame(extended_data)
        
        return data
    
    def get_real_time_data(self) -> pd.DataFrame:
        """Fetch real-time stock data with enhanced error handling and data smoothing."""
        # Check cache first
        cached_data = self._get_cached_data()
        if cached_data is not None:
            return cached_data
        
        # Fetch fresh data
        for attempt in range(1, self.max_retries + 1):
            try:
                stock = yf.Ticker(self.symbol)
                
                if self.start_date:
                    data = self._fetch_historical_data(stock, attempt)
                else:
                    data = self._fetch_current_data(stock, attempt)
                
                if not data.empty and self._validate_data(data):
                    # Add synthetic data points for smoother charts
                    data = self._add_synthetic_data_points(data)
                    
                    # Update data buffer
                    self._update_data_buffer(data)
                    
                    # Reset error counters on success
                    self._consecutive_failures = 0
                    self._last_error = None
                    
                    # Cache the data
                    self._cache_data(data)
                    
                    # Update last data
                    self.last_data = data.copy()
                    self.last_fetch_time = datetime.now()
                    
                    logger.info(f"Successfully fetched {len(data)} rows for {self.symbol}")
                    return data
                
                else:
                    logger.warning(f"Empty or invalid data received for {self.symbol}")
                    if not self._handle_api_error(Exception("Empty data"), attempt):
                        break
            
            except Exception as e:
                if not self._handle_api_error(e, attempt):
                    break
        
        # Return last valid data if available
        if not self.last_data.empty:
            logger.warning(f"Using last valid data for {self.symbol} ({len(self.last_data)} rows)")
            return self.last_data
        
        logger.error(f"Failed to fetch data for {self.symbol} after {self.max_retries} attempts")
        return pd.DataFrame()
    
    def _update_data_buffer(self, data: pd.DataFrame):
        """Update the data buffer with new data points."""
        if not data.empty:
            # Add new data points to buffer
            for _, row in data.iterrows():
                self._data_buffer.append({
                    'timestamp': row.name,
                    'open': row['Open'],
                    'high': row['High'],
                    'low': row['Low'],
                    'close': row['Close'],
                    'volume': row['Volume']
                })
            
            # Keep only the last max_buffer_size points
            if len(self._data_buffer) > self._max_buffer_size:
                self._data_buffer = self._data_buffer[-self._max_buffer_size:]
    
    def _fetch_historical_data(self, stock: yf.Ticker, attempt: int) -> pd.DataFrame:
        """Fetch historical data for a specific date with enhanced period handling."""
        try:
            start_dt = pd.to_datetime(self.start_date)
            end_dt = start_dt + timedelta(days=1)
            
            # Check if date is in the future
            if start_dt > datetime.now():
                logger.error(f"Cannot fetch data for future date {self.start_date}")
                return pd.DataFrame()
            
            # Check if date is too old for 1m data
            days_diff = (datetime.now() - start_dt).days
            if days_diff > 30 and self.interval == "1m":
                logger.warning(f"1m data only available for last 30 days. Using 1d data for {self.start_date}")
                data = stock.history(start=start_dt, end=end_dt, interval="1d")
            else:
                # Try to get more data points by extending the period slightly
                extended_start = start_dt - timedelta(hours=2)
                data = stock.history(start=extended_start, end=end_dt, interval=self.interval)
                
                # Filter to the requested date range - fix timezone comparison
                if not data.empty:
                    # Convert timezone-aware timestamps to timezone-naive for comparison
                    if data.index.tz is not None:
                        data.index = data.index.tz_localize(None)
                    if start_dt.tz is not None:
                        start_dt_naive = start_dt.tz_localize(None)
                    else:
                        start_dt_naive = start_dt
                    data = data[data.index >= start_dt_naive]
            
            logger.info(f"Fetched {len(data)} historical rows for {self.symbol} on {self.start_date}")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return pd.DataFrame()
    
    def _fetch_current_data(self, stock: yf.Ticker, attempt: int) -> pd.DataFrame:
        """Fetch current real-time data with enhanced period handling."""
        try:
            # Use a longer period to get more data points for smoother charts
            extended_period = self._get_extended_period()
            data = stock.history(period=extended_period, interval=self.interval)
            
            current_time = datetime.now()
            logger.info(f"Fetched {len(data)} current rows for {self.symbol} at {current_time}")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching current data: {e}")
            return pd.DataFrame()
    
    def _get_extended_period(self) -> str:
        """Get an extended period to ensure we have enough data points."""
        period_mapping = {
            '1d': '5d',
            '5d': '1mo',
            '1mo': '3mo',
            '3mo': '6mo',
            '6mo': '1y',
            '1y': '2y'
        }
        
        return period_mapping.get(self.period, self.period)
    
    def get_latest_price(self) -> Optional[float]:
        """Get the most recent closing price with error handling."""
        try:
            if not self.last_data.empty and len(self.last_data) > 0:
                if "Close" in self.last_data.columns:
                    latest_price = self.last_data["Close"].iloc[-1]
                    if pd.isna(latest_price):
                        logger.warning(f"Latest price is NaN for {self.symbol}")
                        return None
                    return float(latest_price)

            data = self.get_real_time_data()
            if not data.empty and len(data) > 0:
                if "Close" in data.columns:
                    latest_price = data["Close"].iloc[-1]
                    if pd.isna(latest_price):
                        logger.warning(f"Latest price is NaN for {self.symbol}")
                        return None
                    return float(latest_price)
                else:
                    logger.warning(f"No 'Close' column found in data for {self.symbol}")
                    return None
        except Exception as e:
            logger.error(f"Error getting latest price for {self.symbol}: {e}")
        
        return None
    
    def get_data_summary(self) -> Dict[str, Any]:
        """Get a summary of the current data state."""
        return {
            'symbol': self.symbol,
            'interval': self.interval,
            'period': self.period,
            'start_date': self.start_date,
            'last_fetch_time': self.last_fetch_time.isoformat() if self.last_fetch_time else None,
            'data_points': len(self.last_data),
            'buffer_size': len(self._data_buffer),
            'consecutive_failures': self._consecutive_failures,
            'last_error': self._last_error,
            'cache_size': len(self._cache)
        }
    
    def get_buffer_data(self) -> List[Dict[str, Any]]:
        """Get the buffered data for real-time updates."""
        return self._data_buffer.copy()
    
    def clear_cache(self):
        """Clear the data cache."""
        with self._cache_lock:
            self._cache.clear()
            logger.info("Data cache cleared")
    
    def reset_error_counters(self):
        """Reset error counters."""
        self._consecutive_failures = 0
        self._last_error = None
        logger.info("Error counters reset")
    
    def get_moving_averages(self, data: pd.DataFrame, short_window: int = 5, long_window: int = 20) -> pd.DataFrame:
        """Calculate moving averages for the given data."""
        if data.empty:
            return data
        
        result = data.copy()
        
        # Calculate short-term moving average
        if len(data) >= short_window:
            result['short_ma'] = data['Close'].rolling(window=short_window).mean()
        else:
            result['short_ma'] = np.nan
        
        # Calculate long-term moving average
        if len(data) >= long_window:
            result['long_ma'] = data['Close'].rolling(window=long_window).mean()
        else:
            result['long_ma'] = np.nan
        
        return result