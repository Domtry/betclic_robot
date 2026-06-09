#!/bin/bash
# start_bot.sh - Start the Betclic bot if not already running
# Place this script in the project root and make it executable.

PROJECT_DIR="/tmp/betclic_robot"
PIDFILE="$PROJECT_DIR/bot.pid"
LOGFILE="$PROJECT_DIR/bot.log"

cd "$PROJECT_DIR" || exit 1

# Clean up stale Chromium lock files from crashed sessions
rm -f "$PROJECT_DIR/user_data/SingletonCookie"
rm -f "$PROJECT_DIR/user_data/SingletonLock"
rm -f "$PROJECT_DIR/user_data/SingletonSocket"
rm -rf /tmp/org.chromium.Chromium.*

if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
    echo "Bot is already running (PID=$(cat $PIDFILE))"
    exit 0
fi

# Remove stale PID file from crashed session
rm -f "$PIDFILE"

# Start the bot in background
uv run python main.py > "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
echo "Bot started with PID $(cat $PIDFILE)"