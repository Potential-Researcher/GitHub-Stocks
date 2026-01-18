#!/usr/bin/env python3
"""
Stock Data Fetcher for GitHub Actions
Fetches stock data from Alpha Vantage API and saves to JSON
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

# Configuration
API_BASE = "https://www.alphavantage.co/query"
DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "stocks.json"


def get_api_key():
    """Get API key from environment variable."""
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        print("⚠️  Warning: ALPHA_VANTAGE_API_KEY not set. Using demo mode.")
        return "demo"
    return api_key


def get_symbols():
    """Get stock symbols from environment variable."""
    symbols_str = os.environ.get("SYMBOLS", "AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA")
    return [s.strip().upper() for s in symbols_str.split(",")]


def fetch_quote(symbol: str, api_key: str) -> dict:
    """Fetch current quote for a symbol."""
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": api_key,
    }
    
    try:
        response = requests.get(API_BASE, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "Error Message" in data:
            print(f"  ❌ Error for {symbol}: {data['Error Message']}")
            return None
        
        if "Note" in data:
            print(f"  ⚠️  API rate limit reached")
            return None
        
        quote = data.get("Global Quote", {})
        if not quote:
            print(f"  ❌ No data found for {symbol}")
            return None
        
        return {
            "symbol": quote.get("01. symbol", symbol),
            "price": float(quote.get("05. price", 0)),
            "change": float(quote.get("09. change", 0)),
            "changePercent": float(quote.get("10. change percent", "0%").replace("%", "")),
            "open": float(quote.get("02. open", 0)),
            "high": float(quote.get("03. high", 0)),
            "low": float(quote.get("04. low", 0)),
            "volume": int(quote.get("06. volume", 0)),
            "prevClose": float(quote.get("08. previous close", 0)),
            "latestTradingDay": quote.get("07. latest trading day", ""),
        }
        
    except requests.RequestException as e:
        print(f"  ❌ Request failed for {symbol}: {e}")
        return None
    except (ValueError, KeyError) as e:
        print(f"  ❌ Parse error for {symbol}: {e}")
        return None


def fetch_daily_history(symbol: str, api_key: str, output_size: str = "compact") -> list:
    """Fetch daily historical data for a symbol."""
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": output_size,  # "compact" = 100 days, "full" = 20+ years
        "apikey": api_key,
    }
    
    try:
        response = requests.get(API_BASE, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "Error Message" in data or "Note" in data:
            return []
        
        time_series = data.get("Time Series (Daily)", {})
        
        history = []
        for date_str, values in sorted(time_series.items()):
            history.append({
                "date": date_str,
                "open": float(values.get("1. open", 0)),
                "high": float(values.get("2. high", 0)),
                "low": float(values.get("3. low", 0)),
                "close": float(values.get("4. close", 0)),
                "volume": int(values.get("5. volume", 0)),
            })
        
        return history
        
    except (requests.RequestException, ValueError, KeyError):
        return []


def generate_demo_data(symbols: list) -> dict:
    """Generate demo data when API is not available."""
    import random
    
    print("📊 Generating demo data...")
    
    stocks = {}
    base_prices = {
        "AAPL": 185.0,
        "MSFT": 420.0,
        "GOOGL": 175.0,
        "AMZN": 220.0,
        "TSLA": 175.0,
        "NVDA": 140.0,
    }
    
    for symbol in symbols:
        base_price = base_prices.get(symbol, 100.0)
        price = base_price + random.uniform(-5, 5)
        change = random.uniform(-3, 3)
        
        stocks[symbol] = {
            "quote": {
                "symbol": symbol,
                "price": round(price, 2),
                "change": round(change, 2),
                "changePercent": round((change / price) * 100, 2),
                "open": round(price - random.uniform(0, 2), 2),
                "high": round(price + random.uniform(0, 3), 2),
                "low": round(price - random.uniform(0, 3), 2),
                "volume": random.randint(20000000, 80000000),
                "prevClose": round(price - change, 2),
                "latestTradingDay": datetime.now().strftime("%Y-%m-%d"),
            },
            "history": generate_demo_history(price),
        }
    
    return stocks


def generate_demo_history(current_price: float, days: int = 100) -> list:
    """Generate demo historical data."""
    import random
    
    history = []
    price = current_price * 0.9  # Start 10% lower
    
    for i in range(days):
        date = datetime.now()
        date = date.replace(day=1)  # Start from beginning of current month
        
        # Calculate the date for this entry
        from datetime import timedelta
        entry_date = datetime.now() - timedelta(days=days - i)
        
        # Skip weekends
        if entry_date.weekday() >= 5:
            continue
        
        # Random walk
        change = random.uniform(-0.03, 0.035) * price
        price = max(price * 0.5, min(price * 1.5, price + change))
        
        volatility = random.uniform(1, 4)
        
        history.append({
            "date": entry_date.strftime("%Y-%m-%d"),
            "open": round(price - volatility, 2),
            "high": round(price + volatility + random.uniform(0, 2), 2),
            "low": round(price - volatility - random.uniform(0, 2), 2),
            "close": round(price, 2),
            "volume": random.randint(20000000, 80000000),
        })
    
    return history


def main():
    """Main function to fetch and save stock data."""
    print("=" * 50)
    print("📈 Stock Data Fetcher")
    print("=" * 50)
    print()
    
    api_key = get_api_key()
    symbols = get_symbols()
    
    print(f"🎯 Symbols: {', '.join(symbols)}")
    print(f"🔑 API Key: {'Set' if api_key != 'demo' else 'Demo mode'}")
    print()
    
    # Create data directory if it doesn't exist
    DATA_DIR.mkdir(exist_ok=True)
    
    # Check if we should use demo mode
    if api_key == "demo":
        stocks = generate_demo_data(symbols)
    else:
        stocks = {}
        
        for symbol in symbols:
            print(f"📥 Fetching {symbol}...")
            
            quote = fetch_quote(symbol, api_key)
            if quote:
                history = fetch_daily_history(symbol, api_key, "compact")
                stocks[symbol] = {
                    "quote": quote,
                    "history": history,
                }
                print(f"  ✅ {symbol}: ${quote['price']:.2f} ({quote['change']:+.2f})")
            else:
                print(f"  ⏭️  Skipping {symbol}")
    
    if not stocks:
        print("\n❌ No data fetched. Exiting.")
        sys.exit(1)
    
    # Add metadata
    output = {
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
        "symbols": list(stocks.keys()),
        "stocks": stocks,
    }
    
    # Save to JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print()
    print(f"✅ Data saved to {OUTPUT_FILE}")
    print(f"📊 Updated {len(stocks)} stocks")
    print(f"🕐 Timestamp: {output['lastUpdated']}")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
