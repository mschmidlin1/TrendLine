<div align="center">
  <img src="resources/logo_big.png" alt="TrendLine Logo" width="400"/>
</div>

# TrendLine

**TrendLine** is an intelligent stock trading bot that leverages news sentiment analysis and market trends to make automated trading decisions. By scraping and analyzing news articles from various financial websites, TrendLine identifies market sentiment patterns and executes trades based on real-time information and algorithmic strategies.

## Overview

TrendLine combines natural language processing with quantitative trading strategies to:
- **Monitor** financial news sources in real-time
- **Analyze** market sentiment from news articles and headlines
- **Execute** automated trades based on sentiment indicators and market trends
- **Adapt** to changing market conditions through continuous learning

This bot is designed for traders who want to capitalize on news-driven market movements and sentiment shifts before they're fully reflected in stock prices.

## Features

- 🔍 **News Scraping**: Automated collection of financial news from multiple sources
- 📊 **Sentiment Analysis**: Advanced NLP algorithms to gauge market sentiment
- 🤖 **Automated Trading**: Execute trades based on predefined strategies and sentiment signals
- 📈 **Trend Detection**: Identify emerging market trends from news patterns
- ⚡ **Real-time Processing**: React quickly to breaking news and market events

## Architecture

### Service-Based Class Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Frontend App                      │
│                    (User Interface Layer)                       │
│  - Dashboard visualization                                      │
│  - Trade monitoring                                             │
│  - Configuration management                                     │
│  - Performance metrics display                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Services Layer                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              TradingService                              │  │
│  │  - Execute buy/sell orders                               │  │
│  │  - Manage positions                                      │  │
│  │  - Calculate position sizing                             │  │
│  │  - Risk management                                       │  │
│  │  - Order validation                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              NewsScrapingService                         │  │
│  │  - Scrape financial news sources                         │  │
│  │  - Parse article content                                 │  │
│  │  - Extract headlines and metadata                        │  │
│  │  - Schedule periodic scraping                            │  │
│  │  - Handle rate limiting                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           SentimentAnalysisService                       │  │
│  │  - Analyze news sentiment                                │  │
│  │  - Generate sentiment scores                             │  │
│  │  - Identify sentiment trends                             │  │
│  │  - Aggregate multi-source sentiment                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              StrategyService                             │  │
│  │  - Implement trading strategies                          │  │
│  │  - Generate trading signals                              │  │
│  │  - Backtest strategies                                   │  │
│  │  - Strategy performance evaluation                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              MarketDataService                           │  │
│  │  - Fetch real-time stock prices                          │  │
│  │  - Retrieve historical data                              │  │
│  │  - Monitor market indicators                             │  │
│  │  - Handle API connections                                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              LoggingService                              │  │
│  │  - Centralized logging                                   │  │
│  │  - Log levels (DEBUG, INFO, WARNING, ERROR)              │  │
│  │  - Structured logging                                    │  │
│  │  - Log rotation and archival                             │  │
│  │  - Performance metrics logging                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Storage Layer                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              TradeRepository                             │  │
│  │  - Store executed trades                                 │  │
│  │  - Trade history queries                                 │  │
│  │  - Position tracking                                     │  │
│  │  - P&L calculations                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              NewsRepository                              │  │
│  │  - Store scraped news articles                           │  │
│  │  - Cache sentiment analysis results                      │  │
│  │  - Prevent duplicate scraping                            │  │
│  │  - Historical news queries                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              ConfigurationRepository                     │  │
│  │  - Store bot configuration                               │  │
│  │  - Strategy parameters                                   │  │
│  │  - API credentials (encrypted)                           │  │
│  │  - User preferences                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              PerformanceRepository                       │  │
│  │  - Store performance metrics                             │  │
│  │  - Portfolio snapshots                                   │  │
│  │  - Strategy performance data                             │  │
│  │  - Risk metrics history                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      Database Layer                             │
│  - SQLite / PostgreSQL for structured data                     │
│  - JSON files for configuration                                │
│  - CSV for data exports                                        │
└─────────────────────────────────────────────────────────────────┘
```

### Class Interaction Flow

```
1. News Collection Flow:
   NewsScrapingService → NewsRepository → LoggingService
                      ↓
              SentimentAnalysisService → NewsRepository
                      ↓
              StrategyService

2. Trading Decision Flow:
   MarketDataService → StrategyService → TradingService → TradeRepository
                                              ↓
                                        LoggingService

3. Frontend Display Flow:
   Streamlit App → All Services (read-only queries)
                → All Repositories (data retrieval)
                → LoggingService (audit trail)

4. Logging Flow:
   All Services → LoggingService → Log Files/Database
```

### Key Design Principles

- **Separation of Concerns**: Each service has a single, well-defined responsibility
- **Dependency Injection**: Services receive dependencies through constructors
- **Repository Pattern**: Data access is abstracted through repository classes
- **Centralized Logging**: All operations flow through the LoggingService
- **Stateless Services**: Services don't maintain state; state is persisted in repositories
- **Interface-Based Design**: Services implement interfaces for easy testing and mocking

---

*Disclaimer: This bot is for educational and research purposes. Always conduct thorough testing and risk assessment before using automated trading systems with real capital.*
