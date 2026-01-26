# 📊 Track Record + Backtesting Module

## 🤖 INSTRUKCJA DLA COMET AI ASSISTANT

### Co to jest?
Ten moduł służy do **udowodnienia hedge fundom**, że sygnały ReviewSignal DZIAŁAJĄ.
Loguje każdy sygnał, oblicza performance, porównuje z benchmarkami.

### Jak uruchomić?
```bash
cd track_record
pip install -r requirements.txt
python -m pytest tests/ -v
```

### Struktura modułu:
```
track_record/
├── core/
│   ├── signal_logger.py      # Logowanie sygnałów BUY/SELL/HOLD
│   ├── performance_calc.py   # Obliczanie returns, P&L
│   ├── benchmark_compare.py  # Porównanie z S&P500, sektorami
│   ├── sharpe_ratio.py       # Risk-adjusted returns
│   └── drawdown_analyzer.py  # Max drawdown tracking
├── backtesting/
│   ├── historical_data.py    # Pobieranie historical prices
│   ├── signal_replayer.py    # Replay sygnałów na historii
│   ├── strategy_tester.py    # Test różnych strategii
│   ├── monte_carlo.py        # Symulacje Monte Carlo
│   └── walk_forward.py       # Walk-forward optimization
├── reports/
│   ├── report_generator.py   # PDF/HTML raporty
│   └── templates/            # Szablony raportów
├── models/
│   └── signal_models.py      # Pydantic models
├── database/
│   └── signal_repository.py  # Persystencja sygnałów
└── api/
    └── track_record_api.py   # REST endpoints
```

### Kluczowe metryki:
- **Signal Accuracy**: % trafień (target: 65%+)
- **Average Return**: średni return per sygnał
- **Sharpe Ratio**: risk-adjusted (target: 1.5+)
- **Max Drawdown**: maksymalny spadek (limit: -15%)
- **Win/Loss Ratio**: stosunek wygranych do przegranych

### Jak Comet powinien rozszerzać ten kod:
1. Dodaj więcej strategii w `strategy_tester.py`
2. Rozszerz `monte_carlo.py` o więcej symulacji
3. Dodaj nowe benchmarki w `benchmark_compare.py`
4. Stwórz więcej szablonów raportów

### API Endpoints:
- `POST /api/v1/signals` - Log new signal
- `GET /api/v1/signals/{id}` - Get signal details
- `GET /api/v1/performance` - Get performance metrics
- `GET /api/v1/backtest` - Run backtest
- `GET /api/v1/reports` - Generate report

---
**Autor:** Simon | **Wersja:** 1.0 | **Data:** 2026-01-26
