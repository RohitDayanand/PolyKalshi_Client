
# 📊 Multi-Platform Prediction Market Analytics

A production-ready trading analytics platform that aggregates real-time data from Kalshi and Polymarket, providing unified dashboards, advanced market analytics, and automated arbitrage detection with PostgreSQL persistence and Next.js visualization interface.

## 🎯 Project Overview

This platform serves traders and analysts who want comprehensive market insights across multiple prediction market platforms. By connecting to both Kalshi and Polymarket through their WebSocket APIs, we provide:

- **Real-time data ingestion** from both platforms via WebSocket connections
- **Unified market analytics** with Next.js dashboard and React components
- **Advanced metrics** including rolling volatility, orderbook analysis, and cross-platform price comparisons
- **Professional dashboards** with real-time visualizations and market monitoring
- **Automated arbitrage detection** with PostgreSQL persistence and tracking
- **Statistical analysis** with comprehensive data processing and alerts

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

### 🎛️ Production Dashboard (Next.js)
- **Real-time market monitoring** with React components
- **Interactive charts** using Lightweight Charts and Recharts
- **Market search and filtering** with real-time updates
- **Orderbook visualization** and depth analysis
- **Arbitrage opportunity display** with profit calculations
- **Responsive design** with Tailwind CSS and Radix UI

### 🔧 Arbitrage Detection Engine
- **Automated opportunity scanning** across platforms
- **PostgreSQL persistence** for historical tracking
- **Real-time profit calculations** with fee considerations
- **Alert system** for profitable opportunities
- **Performance analytics** and success rate tracking

## 🏗️ Production Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   Kalshi API    │    │ Polymarket API  │
│   WebSocket     │    │   WebSocket     │
└─────────┬───────┘    └─────────┬───────┘
          │                      │
          └──────┬─────────┬─────┘
                 │         │
         ┌───────▼─────────▼───────┐
         │  Python Backend         │
         │  WebSocket Clients      │
         │  (master_manager)       │
         └───────┬─────────────────┘
                 │
         ┌───────▼─────────────────┐
         │   PostgreSQL Database   │
         │   Arbitrage Tracking    │
         │   (JSONB + Relations)   │
         └───────┬─────────────────┘
                 │
         ┌───────▼─────────────────┐
         │  Arbitrage Service      │
         │  Analytics Engine       │
         │  Detection Algorithms   │
         └───────┬─────────────────┘
                 │
         ┌───────▼─────────────────┐
         │   Next.js Frontend      │
         │   React Dashboard       │
         │   Real-time Charts      │
         └─────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+ and pnpm
- PostgreSQL 12+
- Kalshi API credentials
- Polymarket WebSocket access

### Installation

(below is for actual editing, if you want to run it's setup env files, docker compose build, then docker compose up)
1. **Clone the repository**
```bash
git clone https://github.com/your-username/multi-platform-trading-analytics
cd multi-platform-trading-analytics
```

2. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

3. **Install frontend dependencies**
```bash
cd frontend
pnpm install
cd ..
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your PostgreSQL and API credentials
```

5. **Initialize PostgreSQL database**
```bash
# Set up database schema
psql -U your_username -d your_database -f backend/postgresql_schema.sql
```

6. **Start the application**
```bash
# Start backend services
python backend/start_server.py

# Start frontend dashboard (in another terminal)
cd frontend && pnpm run dev
```

## 📁 Project Structure

```
├── backend/                       # Python backend services
│   ├── master_manager/           # Core application logic
│   │   ├── clients/              # API clients (Kalshi, Polymarket)
│   │   ├── services/             # Business logic services
│   │   │   ├── arbitrage_service/ # Arbitrage detection engine
│   │   │   ├── events/           # Event handling
│   │   │   └── messaging/        # Inter-service communication
│   │   └── tests/                # Backend tests
│   ├── postgresql_schema.sql     # Database schema
│   └── start_server.py          # Main server entry point
├── frontend/                     # Next.js dashboard
│   ├── app/                     # Next.js app router
│   ├── components/              # React components
│   │   ├── charts/              # Chart visualizations
│   │   ├── containers/          # Page containers
│   │   └── ui/                  # UI component library
│   ├── lib/                     # Utilities and helpers
│   │   ├── RxJSChannel/         # WebSocket management
│   │   └── store/               # Redux state management
│   └── package.json             # Frontend dependencies
├── config/                      # Configuration files
├── docs/                        # Documentation
└── README.md                    # This file
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

## 💻 Tech Stack

### Backend
- **Python 3.9+** with asyncio for concurrent processing
- **PostgreSQL** with JSONB support for flexible data storage
- **WebSocket clients** for real-time Kalshi and Polymarket data
- **Service-oriented architecture** with modular components
- **Async processing** for high-throughput arbitrage detection

### Frontend  
- **Next.js 15** with App Router for modern React development
- **TypeScript** for type-safe development
- **Tailwind CSS** + **Radix UI** for responsive design
- **Lightweight Charts** for financial data visualization
- **Redux Toolkit** + **RxJS** for state and WebSocket management
- **Recharts** for additional chart components

### Database Schema
- **PostgreSQL** with optimized arbitrage tracking tables
- **JSONB storage** for flexible orderbook data
- **Indexed queries** for fast opportunity detection
- **Async batch operations** for performance optimization

## 🔍 Usage Examples

### Market Discovery
```python
from backend.master_manager.clients.kalshi_client import KalshiClient

# Find active markets
kalshi = KalshiClient()
markets = kalshi.get_markets(event_ticker="PRESIDENT-2024")
print(f"Found {len(markets.get('markets', []))} active markets")
```

### Real-time Monitoring
```python
# Start the backend services
from backend.master_manager.services.service_coordinator import ServiceCoordinator

# Initialize and start all services
coordinator = ServiceCoordinator()
coordinator.start_all_services()

# Access dashboard at http://localhost:3000
# View arbitrage opportunities and market data in real-time
```

## 🎯 Roadmap

### Phase 1: Core Infrastructure ✅ **COMPLETE**
- [x] WebSocket data ingestion from Kalshi and Polymarket
- [x] PostgreSQL database schema with JSONB support
- [x] Market discovery and real-time data collection
- [x] Error handling, logging, and reconnection logic
- [x] Master manager orchestration system

### Phase 2: Analytics Engine ✅ **COMPLETE**
- [x] Rolling average calculations and volatility metrics
- [x] Cross-platform price comparison algorithms
- [x] Statistical arbitrage detection with profit calculations
- [x] PostgreSQL arbitrage tracking and persistence
- [x] Fee calculation and opportunity scoring
- [x] Async processing for high-throughput operations

### Phase 3: Dashboard & UI ✅ **COMPLETE**
- [x] Next.js real-time dashboard with React components
- [x] Interactive market visualization with Lightweight Charts
- [x] Orderbook depth charts and volume analysis
- [x] Market search and filtering capabilities
- [x] Arbitrage opportunity display with profit metrics
- [x] Responsive design with Tailwind CSS and Radix UI
- [x] Redux state management and RxJS WebSocket handling

### Phase 4: Advanced Features 🚧 **IN PROGRESS**
- [x] Performance analytics and throughput testing
- [ ] Machine learning prediction models
- [ ] Advanced risk management tools
- [ ] Portfolio optimization algorithms
- [ ] Mobile application interface

## 🤝 Contributing

We welcome contributions from the open-source community! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📋 API Documentation

### Key Components
- **Backend Services**: Python services in `backend/master_manager/services/`
- **Arbitrage Engine**: Real-time detection in `backend/master_manager/services/arbitrage_service/`
- **Frontend API**: Next.js API routes in `frontend/app/api/`
- **WebSocket Management**: RxJS channels in `frontend/lib/RxJSChannel/`

### Performance
- **High-throughput processing** with async PostgreSQL operations
- **Real-time WebSocket** connections with automatic reconnection
- **Optimized database queries** with proper indexing
- **Responsive frontend** with efficient state management

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

- **Project Maintainer**: Rohit Dayanand
- **Email**: rohitdayanand8@gmail.com
- **LinkedIn**: https://www.linkedin.com/in/rohit-dayanand-44122b1a6/

---

⭐ **Star this repo** if you find it useful for your trading and analytics needs!

[![GitHub stars](https://img.shields.io/github/stars/your-username/multi-platform-trading-analytics.svg?style=social&label=Star)](https://github.com/your-username/multi-platform-trading-analytics)
[![GitHub forks](https://img.shields.io/github/forks/your-username/multi-platform-trading-analytics.svg?style=social&label=Fork)](https://github.com/your-username/multi-platform-trading-analytics/fork)

