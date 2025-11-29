#!/bin/bash
# Management script for Boltz API

PORT=8000

# Check if we're in a virtual environment
check_env() {
    if ! python -c "import fastapi" 2>/dev/null; then
        echo "⚠️  FastAPI not found in current environment!"
        echo ""
        echo "Please activate your environment first:"
        echo "  conda activate boltz_api"
        echo "  # OR"
        echo "  source boltz_api_env/bin/activate"
        echo ""
        exit 1
    fi
}

case "$1" in
    start)
        check_env
        echo "🚀 Starting Boltz API on port $PORT..."
        python main.py
        ;;
    
    stop)
        echo "🛑 Stopping Boltz API..."
        PID=$(lsof -ti:$PORT)
        if [ -z "$PID" ]; then
            echo "No process found running on port $PORT"
        else
            kill $PID
            echo "Stopped process $PID"
        fi
        ;;
    
    restart)
        echo "🔄 Restarting Boltz API..."
        $0 stop
        sleep 2
        $0 start
        ;;
    
    status)
        echo "📊 Checking Boltz API status..."
        PID=$(lsof -ti:$PORT)
        if [ -z "$PID" ]; then
            echo "❌ API is not running"
            exit 1
        else
            echo "✅ API is running (PID: $PID)"
            ps -p $PID -o pid,comm,args
            echo ""
            echo "Health check:"
            curl -s http://localhost:$PORT/health | python -m json.tool || echo "API not responding"
        fi
        ;;
    
    logs)
        echo "📋 Showing API logs (if running with nohup)..."
        if [ -f "nohup.out" ]; then
            tail -f nohup.out
        else
            echo "No log file found. Run with: nohup ./manage_api.sh start &"
        fi
        ;;
    
    *)
        echo "Boltz API Management Script"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start    - Start the API server"
        echo "  stop     - Stop the API server"
        echo "  restart  - Restart the API server"
        echo "  status   - Check if API is running"
        echo "  logs     - View API logs (if running with nohup)"
        echo ""
        echo "Examples:"
        echo "  $0 start                  # Start in foreground"
        echo "  nohup $0 start &          # Start in background"
        echo "  $0 status                 # Check status"
        echo "  $0 stop                   # Stop the server"
        exit 1
        ;;
esac
