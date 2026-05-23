# 📈 CAN SLIM Stock Scanner

A Python-based stock screener implementing William O'Neil's **CAN SLIM** methodology from *How to Make Money in Stocks*. Designed for Google Colab or Jupyter Notebook. Built on `yfinance`, `pandas`, and `numpy`.

---

## CAN SLIM Criteria

| Letter | Full Name | Criteria | Default Threshold |
|--------|-----------|----------|--------------------|
| **C** | Current Earnings | Quarterly EPS growth YoY | ≥ 25% |
| **A** | Annual Earnings | 3-year average annual EPS growth | ≥ 25% |
| **N** | New Highs | Price within N% of 52-week high | ≤ 10% below |
| **S** | Supply & Demand | Up/Down volume ratio | ≥ 1.0 |
| **L** | Leader or Laggard | Relative Strength vs S&P 500 | RS ≥ 70/99 |
| **I** | Institutional Sponsorship | Sector, industry, inst. ownership | Informational |
| **M** | Market Direction | SPY above 50-day MA + FTD detection | Must pass |

---

## Project Structure

```
canslim_scanner/
├── canslim_scanner.py       # Core scanner module (importable)
├── canslim_scanner.ipynb    # Jupyter / Google Colab notebook
├── requirements.txt
└── README.md
```

---

## Quickstart

### Option A — Google Colab (recommended)

1. Upload `canslim_scanner.py` via the Colab Files panel
2. Open `canslim_scanner.ipynb` in Colab
3. Run cells top to bottom

Or pull directly from GitHub in a Colab cell:
```python
!wget -q https://raw.githubusercontent.com/YOUR_USERNAME/canslim_scanner/main/canslim_scanner.py
```

### Option B — Local Jupyter

```bash
pip install -r requirements.txt
jupyter notebook canslim_scanner.ipynb
```

---

## Usage

```python
from canslim_scanner import CANSLIMScanner, WATCHLISTS

scanner = CANSLIMScanner()

# Scan a custom list
results = scanner.scan(["NVDA", "AAPL", "GOOGL", "JPM"], min_passes=4)
scanner.print_results(results)

# Export to CSV
scanner.export_csv(results, "my_scan.csv")

# Get as DataFrame
df = scanner.to_dataframe(results)

# Use a preset watchlist
results = scanner.scan(WATCHLISTS["mega_cap_tech"])
```

### Override thresholds

```python
scanner = CANSLIMScanner(config={
    "C_min_eps_growth":    20.0,   # lower EPS bar
    "L_min_rs_rating":     60.0,   # accept weaker RS
    "N_near_high_pct":     15.0,   # further from 52-wk high OK
})
```

---

## Outputs

- **Console report** — pass/fail per criterion with values
- **Heatmap** — color-coded grid of all symbols × criteria
- **RS bar chart** — relative strength ratings ranked
- **Price chart** — close + 50/200-day MA + volume bars
- **CSV export** — full results with all values and details

---

## Built-in Watchlists

```python
WATCHLISTS = {
    "mega_cap_tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
    "financials":    ["JPM", "BAC", "GS", "MS", "V", "MA", "XLF", "KRE"],
    "healthcare":    ["UNH", "LLY", "ABBV", "JNJ", "MRK", "PFE", "AMGN"],
    "industrials":   ["CAT", "DE", "HON", "GE", "BA", "RTX", "LMT"],
    "sample_mixed":  ["NVDA", "AAPL", "GOOGL", "META", "JPM", "UNH", "CAT"],
}
```

---

## Roadmap

- [ ] IBD-style Composite Rating (weighted C + A + L)
- [ ] Industry group rank via sector ETFs
- [ ] Integration with `options_scanner.py` signals
- [ ] Streamlit web UI for mobile access
- [ ] GitHub Actions daily scheduled scan
- [ ] Email/SMS alert when stock hits 6/7 or 7/7

---

## Limitations

- EPS data depends on yfinance (coverage varies)
- RS Rating is a proxy, not IBD's proprietary formula
- Industry ranking uses sectors, not IBD's 197 industry groups
- **Not financial advice.** Do your own due diligence.

---

## Dependencies

- `yfinance >= 0.2.40`
- `pandas >= 2.0`
- `numpy >= 1.24`
- `matplotlib >= 3.7`

---

## License

MIT
