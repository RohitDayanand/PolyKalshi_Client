# 📊 Multi-Platform Prediction Market Analytics

A professional-grade trading analytics platform that aggregates real-time data from Kalshi and Polymarket, providing unified dashboards and advanced market analytics that neither platform offers individually.

## 🎯 Project Overview

This platform serves traders and analysts who want comprehensive market insights across multiple prediction market platforms. By connecting to both Kalshi and Polymarket through their WebSocket APIs, we provide:

- **Real-time data ingestion** from both platforms
- **Unified market analytics** and visualizations
- **Advanced metrics** like rolling volatility, trade place data, and cross-platform price comparisons
- **Professional dashboards** for market monitoring and analysis
- **Statistical arbitrage** opportunity identification

## ⭐ Key Features

### 📡 Real-Time Data Pipeline
- **WebSocket connections** to Kalshi and Polymarket
- **High-performance data ingestion** with PostgreSQL storage
- **JSONB storage** for flexible orderbook data
- **Automated reconnection** and error handling

### 📈 Advanced Analytics
- **Rolling averages** (short-term and long-term)
- **Volatility filters** and metrics
- **Cross-platform price comparison**
- **Order book depth analysis**
- **Trade volume analytics**

### 🎛️ Professional Dashboards
- **Real-time market monitoring**
- **Customizable alerts** and notifications
- **Historical data visualization**
- **Portfolio tracking** across platforms
- **Risk management tools**

### 🔧 Platform Integration
- **Unified login** for both Kalshi and Polymarket accounts
- **Secure API key management**
- **Cross-platform position tracking**
- **Automated market discovery**

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   Kalshi API    │    │ Polymarket API  │
│   WebSocket     │    │   WebSocket     │
└─────────┬───────┘    └─────────┬───────┘
          │                      │
          └──────┬─────────┬─────┘
                 │         │
         ┌───────▼─────────▼───────┐
         │   Data Ingestion        │
         │   Pipeline              │
         └───────┬─────────────────┘
                 │
         ┌───────▼─────────────────┐
         │   PostgreSQL Database   │
         │   (JSONB + Schema)      │
         └───────┬─────────────────┘
                 │
         ┌───────▼─────────────────┐
         │   Analytics Engine      │
         │   & API Backend         │
         └───────┬─────────────────┘
                 │
         ┌───────▼─────────────────┐
         │   Real-time Dashboard   │
         │   & Visualization       │
         └─────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- PostgreSQL 12+
- Kalshi API credentials
- Polymarket API access

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/your-username/multi-platform-trading-analytics
cd multi-platform-trading-analytics
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your credentials
```

4. **Initialize the database**
```bash
python -c "from kalshi-starter-code-python.models import init_db; init_db()"
```

5. **Start the data collection**
```bash
# Start Kalshi data collection
python kalshi-starter-code-python/main.py

# Start Polymarket data collection (in another terminal)
python poly-starter-code/Connection.py
```

## 📁 Project Structure

```
├── kalshi-starter-code-python/     # Kalshi integration
│   ├── models.py                   # Database models
│   ├── kalshi_client.py           # Kalshi API client
│   ├── orderbook_processor.py     # Real-time data processing
│   ├── find_kalshi_markets.py     # Market discovery
│   └── main.py                    # Main orchestration
├── poly-starter-code/             # Polymarket integration
│   ├── Connection.py              # WebSocket client
│   ├── Market_Finder.py           # Market discovery
│   └── models.py                  # Database models
├── docs/                          # Documentation
├── tests/                         # Test suite
└── dashboard/                     # Frontend dashboard (coming soon)
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file with:

```env
# Database Configuration
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
POSTGRES_DB=trading_analytics
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Kalshi API
KALSHI_API_KEY=your_kalshi_api_key
PROD_KEYID=your_production_key_id
PROD_KEYFILE=kalshi_key_file.txt

# Polymarket (add when available)
POLYMARKET_API_KEY=your_polymarket_key
```

## 📊 Data Models

### Kalshi Data Structure
- **Orderbook Snapshots**: Full market depth with JSONB orders
- **Deltas**: Real-time order changes
- **Trades**: Executed transaction data
- **Fills**: Order fill notifications
- **Ticker V2**: Market statistics and metrics

### Polymarket Data Structure
- **Order Books**: Bid/ask spreads and market depth
- **Price Changes**: Real-time price movements
- **Tick Size Changes**: Market parameter updates

## 🔍 Usage Examples

### Market Discovery
```python
from kalshi_starter_code_python.find_kalshi_markets import get_markets

# Find active markets
markets = get_markets("PRESIDENT-2024")
print(f"Found {len(markets.get('markets', []))} active markets")
```

### Real-time Monitoring
```python
from kalshi_starter_code_python.main import main as start_kalshi
from poly_starter_code.Connection import PolymarketWebSocket

# Start real-time data collection
start_kalshi()  # Kalshi data
ws = PolymarketWebSocket("your-market-slug")  # Polymarket data
```

## 🎯 Roadmap

### Phase 1: Core Infrastructure ✅
- [x] WebSocket data ingestion
- [x] Database schema design
- [x] Basic market discovery
- [x] Error handling and logging

### Phase 2: Analytics Engine 🚧
- [ ] Rolling average calculations
- [ ] Volatility metrics
- [ ] Cross-platform price comparison
- [ ] Statistical arbitrage detection

### Phase 3: Dashboard & UI 📋
- [ ] Real-time dashboard
- [ ] Market visualization
- [ ] Alert system
- [ ] User authentication

### Phase 4: Advanced Features 🎯
- [ ] Machine learning predictions
- [ ] Risk management tools
- [ ] Portfolio optimization
- [ ] Mobile application

## 🤝 Contributing

We welcome contributions from the open-source community! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📋 API Documentation

Detailed API documentation is available in the [docs/](docs/) directory:
- [Kalshi Integration](docs/kalshi-api.md)
- [Polymarket Integration](docs/polymarket-api.md)
- [Database Schema](docs/database-schema.md)
- [Analytics API](docs/analytics-api.md)

## 🛡️ Security

- **API keys** are stored securely in environment variables
- **Database credentials** are encrypted
- **WebSocket connections** use secure protocols
- **Rate limiting** prevents API abuse

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Kalshi for their comprehensive trading API
- Polymarket for real-time market data
- The open-source community for inspiration and support

## 📞 Contact

- **Project Maintainer**: [Your Name]
- **Email**: your.email@example.com
- **LinkedIn**: [Your LinkedIn Profile]
- **Twitter**: [@YourHandle]

---

⭐ **Star this repo** if you find it useful for your trading and analytics needs!

[![GitHub stars](https://img.shields.io/github/stars/your-username/multi-platform-trading-analytics.svg?style=social&label=Star)](https://github.com/your-username/multi-platform-trading-analytics)
[![GitHub forks](https://img.shields.io/github/forks/your-username/multi-platform-trading-analytics.svg?style=social&label=Fork)](https://github.com/your-username/multi-platform-trading-analytics/fork)
