#!/bin/bash
# ============================================================
#  deploy.sh — Run this on your OLD MacBook after git pull
#  Usage: bash deploy.sh
# ============================================================

set -e
cd "$(dirname "$0")"

echo ""
echo "🚀 Price Agent — Deploy Script"
echo "================================"

# 1. Check Python
echo "→ Checking Python 3..."
python3 --version || { echo "❌ Python 3 not found. Install via: brew install python3"; exit 1; }

# 2. Install dependencies
echo "→ Installing Python dependencies..."
pip3 install -r requirements.txt --quiet

# 3. Create runtime dirs
echo "→ Creating logs/ and data/ directories..."
mkdir -p logs data

# 4. Check .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  No .env file found!"
    echo "   Copy the example and fill in your keys:"
    echo "   cp .env.example .env && nano .env"
    echo ""
    exit 1
fi
echo "→ .env file found ✅"

# 5. Test run (dry run)
echo "→ Running a quick test..."
python3 agent.py --flights 2>&1 | tail -5 || true

# 6. Install cron job (every 30 min — scheduler.py decides the actual run time)
echo ""
echo "→ Setting up cron job (scheduler runs every 30 min, picks random safe times)..."
SCRIPT_DIR="$(pwd)"
CRON_LINE="*/30 * * * * cd $SCRIPT_DIR && python3 scheduler.py >> logs/agent.log 2>&1"

# Add only if not already there
( crontab -l 2>/dev/null | grep -v "price-agent\|scheduler.py\|agent.py"; echo "$CRON_LINE" ) | crontab -
echo "→ Cron job installed ✅"

# 7. Prevent sleep
echo ""
echo "→ Disabling Mac sleep (requires sudo)..."
sudo pmset -a sleep 0 disksleep 0 && echo "→ Sleep disabled ✅" || echo "⚠️  Could not set pmset — do it manually in Energy Saver."

echo ""
echo "✅ Deploy complete!"
echo ""
echo "Useful commands:"
echo "  Check logs:          tail -f $SCRIPT_DIR/logs/agent.log"
echo "  Run manually:        python3 $SCRIPT_DIR/agent.py"
echo "  Check next run time: cat $SCRIPT_DIR/data/next_run.json"
echo "  Edit routes:         nano $SCRIPT_DIR/config.py"
echo "  View cron jobs:      crontab -l"
echo ""
