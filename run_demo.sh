#!/bin/bash
# Demo: backtest $10 scalper with synthetic data
set -e
cd python_bot
echo "=== Installing deps ==="
pip install --break-system-packages -q pandas numpy matplotlib python-dotenv 2>&1 | tail -5
echo
echo "=== EURUSD M5 synthetic 3000 bars ==="
python backtest.py --balance 10 --preset EURUSD_M5 --bars 3000 --plot
echo
echo "=== XAUUSD M5 ==="
python backtest.py --balance 10 --preset XAUUSD_M5 --bars 3000
echo
echo "Done. Check backtest_trades.csv and equity.png (ignored in git, generated locally)"
