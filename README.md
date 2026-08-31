# Lever Trading Platform

Lever is a modern stock trading simulator built with a FastAPI backend and a Next.js (React) frontend. It mimics the mechanics of the Nigerian Exchange (NGX), allowing users to trade stocks, manage portfolios, and utilize margin with simulated leverage.

## Features
- **Real-Time Data Simulation:** Fetch and simulate stock prices.
- **Liquidity Tiers:** Stocks are categorized into Blue Chip, Established, Volatile, and Restricted tiers, which govern maximum leverage and margin requirements.
- **Margin Trading:** Open LONG and SHORT positions using leverage.
- **Dynamic Portfolio:** Real-time calculation of unrealized PnL, equity, and liquidation prices.

## Project Structure
- `/backend`: FastAPI application, SQLAlchemy models, and PostgreSQL database logic.
- `/frontend`: Next.js web application using Tailwind CSS and TanStack Query.

## Running Locally

### Backend
1. Navigate to the `backend` directory.
2. Activate the virtual environment: `source venv/bin/activate`
3. Start the server: `uvicorn main:app --reload --port 8000`

### Frontend
1. Navigate to the `frontend` directory.
2. Install dependencies: `npm install`
3. Start the development server: `npm run dev`
