# 📈 StockPulse - Stock Market Dashboard

A modern, real-time stock market dashboard built to demonstrate **GitHub features, automation, and API integrations** for educational purposes.

![Dashboard Preview](https://img.shields.io/badge/status-live-brightgreen) ![GitHub Actions](https://img.shields.io/badge/automation-GitHub%20Actions-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## 🎯 Learning Objectives

This project demonstrates:

| GitHub Feature | What You'll Learn |
|----------------|-------------------|
| **GitHub Pages** | Free static site hosting directly from a repository |
| **GitHub Actions** | Automated workflows, scheduled tasks (cron jobs), CI/CD pipelines |
| **Secrets Management** | Securely storing API keys and sensitive data |
| **Automated Commits** | Having Actions commit data back to the repository |
| **Branch Protection** | Setting up code review and governance workflows |
| **Issues & Projects** | Using GitHub for project management |
| **Dependabot** | Automated dependency security updates |

---

## 🚀 Quick Start

### Step 1: Fork or Clone This Repository

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/stock-dashboard.git
cd stock-dashboard
```

Or click the **"Use this template"** button on GitHub.

### Step 2: Get a Free Alpha Vantage API Key

1. Visit [Alpha Vantage](https://www.alphavantage.co/support/#api-key)
2. Enter your email and get a free API key
3. Save this key - you'll need it for the next step

> 💡 **Free tier**: 25 requests/day - perfect for learning!

### Step 3: Add Your API Key to GitHub Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `ALPHA_VANTAGE_API_KEY`
5. Value: *Your API key from Step 2*
6. Click **Add secret**

### Step 4: Enable GitHub Pages

1. Go to **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` (or `master`)
4. Folder: `/ (root)`
5. Click **Save**

Your site will be live at: `https://YOUR_USERNAME.github.io/stock-dashboard/`

### Step 5: Enable GitHub Actions

1. Go to the **Actions** tab
2. Click **"I understand my workflows, go ahead and enable them"**
3. The workflow will now run on schedule (hourly during market hours)

---

## 📁 Project Structure

```
stock-dashboard/
├── .github/
│   └── workflows/
│       └── update-stocks.yml    # 🤖 GitHub Actions automation
├── data/
│   ├── stocks.json              # 📊 Auto-updated stock data
│   └── shows.json               # 📺 The shared TV watchlist
├── scripts/
│   ├── fetch_stocks.py          # 🐍 Python script for fetching data
│   └── watchlist.py             # 📺 Watchlist CLI (add / rate / stats)
├── index.html                   # 🌐 Main dashboard page
├── watchlist.html               # 📺 Watchlist page
├── style.css                    # 🎨 Dark theme styling
├── watchlist.css                # 📺 Watchlist styling
├── script.js                    # ⚡ Interactive functionality
├── watchlist.js                 # 📺 Watchlist rendering
├── our_shows.example.txt        # 📝 Bulk-import template
└── README.md                    # 📚 This file!
```

---

## 🔧 How It Works

### The Automation Pipeline

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  GitHub Action  │────▶│  Alpha Vantage  │────▶│  stocks.json    │
│  (Scheduled)    │     │  API            │     │  (Updated)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                                               │
         │                                               ▼
         │                                      ┌─────────────────┐
         │                                      │  GitHub Pages   │
         └─────────────────────────────────────▶│  (Auto Deploy)  │
                                                └─────────────────┘
```

1. **GitHub Action** runs on a schedule (every hour during market hours)
2. **Python script** fetches data from Alpha Vantage API
3. Data is saved to `stocks.json` and **committed to the repo**
4. **GitHub Pages** automatically rebuilds with the new data
5. Users see updated stock prices!

### The Schedule (Cron Syntax)

```yaml
schedule:
  - cron: '0 14-21 * * 1-5'  # Every hour, 9am-4pm ET, Mon-Fri
```

Breaking it down:
- `0` - At minute 0
- `14-21` - Hours 14-21 UTC (9am-4pm Eastern)
- `* *` - Every day of the month, every month
- `1-5` - Monday through Friday

---

## 🧪 Testing Locally

### Option 1: Use Demo Mode
Simply open `index.html` in your browser and click "Use Demo Data" when prompted.

### Option 2: Use Your API Key Locally
1. Open `index.html` in your browser
2. Enter your Alpha Vantage API key when prompted
3. Search for any stock symbol!

### Option 3: Run the Python Script

```bash
# Set your API key
export ALPHA_VANTAGE_API_KEY="your-api-key"
export SYMBOLS="AAPL,MSFT,GOOGL"

# Run the script
python scripts/fetch_stocks.py
```

---

## 📚 Learning Exercises

### Exercise 1: Understand GitHub Actions
1. Go to the **Actions** tab
2. Click on a workflow run
3. Explore the logs for each step
4. Try triggering a manual run with the **"Run workflow"** button

### Exercise 2: Modify the Workflow
1. Edit `.github/workflows/update-stocks.yml`
2. Change the stock symbols in the default list
3. Commit and push - watch the Action run!

### Exercise 3: Add a New Feature
Ideas to try:
- Add more statistics (P/E ratio, market cap)
- Create a watchlist feature
- Add price alerts
- Implement a comparison view

### Exercise 4: Set Up Branch Protection
1. Go to **Settings** → **Branches**
2. Add a rule for `main`
3. Enable "Require pull request reviews"
4. Try making a change via a pull request

### Exercise 5: Use GitHub Issues
1. Go to the **Issues** tab
2. Create an issue for a new feature
3. Reference it in a commit message: `Fixes #1`
4. Watch it auto-close when merged!

---

## 🔐 Security Best Practices

This project demonstrates secure API key handling:

✅ **DO:**
- Store API keys in GitHub Secrets
- Use environment variables in Actions
- Keep secrets out of your code

❌ **DON'T:**
- Commit API keys to the repository
- Share your API key publicly
- Hardcode secrets in your code

---

## 🛠️ Customization

### Change Stock Symbols
Edit the workflow to track different stocks:

```yaml
env:
  SYMBOLS: 'AAPL,NVDA,AMD,INTC,TSM'  # Tech stocks
```

### Change Update Frequency
Modify the cron schedule:

```yaml
schedule:
  - cron: '*/30 9-16 * * 1-5'  # Every 30 minutes during market hours
```

### Add More Data Sources
The architecture supports multiple APIs. Consider adding:
- [Finnhub](https://finnhub.io/) - Real-time data
- [Polygon.io](https://polygon.io/) - Historical data
- [Yahoo Finance](https://www.yahoofinanceapi.com/) - Free tier available

---

## 📖 Additional Resources

### GitHub Documentation
- [GitHub Pages](https://docs.github.com/pages)
- [GitHub Actions](https://docs.github.com/actions)
- [Encrypted Secrets](https://docs.github.com/actions/security-guides/encrypted-secrets)

### API Documentation
- [Alpha Vantage API](https://www.alphavantage.co/documentation/)

### Learning Paths
- [GitHub Skills](https://skills.github.com/) - Interactive courses
- [GitHub Learning Lab](https://lab.github.com/) - Hands-on tutorials

---

## 📺 The Shared Watchlist

A second, unrelated thing living in this repo: a record of every TV show two
people have watched **together**, what each of them thought of it, and what
that says about what to watch next. It's at `watchlist.html`.

The list lives in `data/shows.json`. Nothing edits it by hand — everything
goes through the CLI.

### First run

```bash
# Use your actual names (a and b are the two slots)
python scripts/watchlist.py viewers a=Sam b=Riley

# Add shows one at a time...
python scripts/watchlist.py add "Severance" --ratings a=10 b=9 \
    --note "the one we both couldn't shut up about"

# ...or dump the whole backlog in at once
cp our_shows.example.txt our_shows.txt   # then edit it
python scripts/watchlist.py import our_shows.txt
```

The import format is one show per line, and only the title is required:

```
Title | your score | her score | status | note
```

### Filling in the details

Set a [free TMDB key](https://www.themoviedb.org/settings/api) and the tool
fetches year, genres, network, episode counts and poster art:

```bash
export TMDB_API_KEY=your_key
python scripts/watchlist.py enrich
```

### Getting something out of it

```bash
python scripts/watchlist.py stats        # taste profile, genre ranking, biggest splits
python scripts/watchlist.py recommend    # what to watch next, from TMDB
python scripts/watchlist.py list --sort spread   # where you two disagree most
python scripts/watchlist.py export -o watchlist.csv
```

`stats` is the point of the whole thing. It reports how each of you rates on
average, which genres actually earn their runtime, which shows you both loved,
and which ones split you — then `recommend` builds suggestions from the shows
you *both* rated highly, so it isn't just chasing one person's taste.

### Commands

| Command | What it does |
|---------|--------------|
| `add` | Add one show, with ratings, status, tags and a note |
| `import` | Bulk add from a text file (or stdin) |
| `rate` | Score a show already on the list |
| `set` | Change status, note, tags or dates |
| `rm` | Remove a show |
| `list` | Print the list, sorted by title, rating, spread or year |
| `enrich` | Fill in metadata from TMDB |
| `stats` | Taste profile and genre ranking |
| `recommend` | Suggestions built from what you both liked |
| `export` | Write CSV |
| `viewers` | Set your display names |

> The watchlist page reads `data/shows.json` over `fetch`, so open it through a
> local server (`python -m http.server`) rather than as a `file://` path.

---

## 🤝 Contributing

This is an educational project! Feel free to:
1. Fork it
2. Experiment with changes
3. Submit pull requests with improvements
4. Open issues with questions

---

## 📄 License

MIT License - feel free to use this for your own learning!

---

## 🙋 FAQ

**Q: Why am I getting "API rate limit reached"?**
A: Alpha Vantage's free tier allows 25 requests/day. Wait until tomorrow or use demo mode.

**Q: The Action isn't running on schedule?**
A: GitHub may delay scheduled actions by a few minutes. Also, Actions are disabled on forked repos by default - enable them in the Actions tab.

**Q: How do I add more stocks?**
A: Edit the `SYMBOLS` environment variable in the workflow file or trigger a manual run with custom symbols.

**Q: Can I use a different stock API?**
A: Yes! Modify `scripts/fetch_stocks.py` to use any API. The data format in `stocks.json` should remain consistent.

---

Built with ❤️ for learning GitHub and APIs
