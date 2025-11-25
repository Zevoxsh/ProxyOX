#!/bin/bash
#
# ProxyOX Service Manager for Linux
# Manage ProxyOX service: start, stop, restart, status, validate
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.proxyox.pid"
LOG_FILE="$SCRIPT_DIR/proxyox.log"
MAIN_SCRIPT="$SCRIPT_DIR/src/main.py"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"

# Banner
show_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                     ${MAGENTA}ProxyOX Manager${CYAN}                       ║"
    echo "║                   Service Control v1.0                    ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Check if service is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Get service status
status() {
    show_banner
    echo -e "${BLUE}━━━ Service Status ━━━${NC}"
    echo ""
    
    if is_running; then
        PID=$(cat "$PID_FILE")
        UPTIME=$(ps -p "$PID" -o etime= 2>/dev/null | tr -d ' ' || echo "N/A")
        CPU=$(ps -p "$PID" -o %cpu= 2>/dev/null | tr -d ' ' || echo "N/A")
        MEM=$(ps -p "$PID" -o %mem= 2>/dev/null | tr -d ' ' || echo "N/A")
        
        echo -e "${GREEN}✓ ProxyOX is running${NC}"
        echo -e "  ${CYAN}PID:${NC}        ${BLUE}$PID${NC}"
        echo -e "  ${CYAN}Uptime:${NC}     ${BLUE}$UPTIME${NC}"
        echo -e "  ${CYAN}CPU Usage:${NC}  ${BLUE}$CPU%${NC}"
        echo -e "  ${CYAN}Memory:${NC}     ${BLUE}$MEM%${NC}"
        echo -e "  ${CYAN}Log File:${NC}   ${BLUE}$LOG_FILE${NC}"
        echo ""
        
        # Check dashboard port
        if [ -f "$SCRIPT_DIR/.env" ]; then
            DASHBOARD_PORT=$(grep "DASHBOARD_PORT" "$SCRIPT_DIR/.env" 2>/dev/null | cut -d'=' -f2 | tr -d ' "'"'"'' || echo "8080")
            DASHBOARD_PORT=${DASHBOARD_PORT:-8080}
            echo -e "${MAGENTA}🌐 Dashboard: ${CYAN}http://localhost:$DASHBOARD_PORT${NC}"
        else
            echo -e "${MAGENTA}🌐 Dashboard: ${CYAN}http://localhost:8080${NC} ${YELLOW}(default)${NC}"
        fi
        echo ""
        return 0
    else
        echo -e "${YELLOW}✗ ProxyOX is not running${NC}"
        
        if [ -f "$PID_FILE" ]; then
            echo -e "  ${RED}(Stale PID file found and removed)${NC}"
            rm -f "$PID_FILE"
        fi
        echo ""
        return 1
    fi
}

# Validate configuration
validate() {
    show_banner
    echo -e "${BLUE}━━━ Configuration Validation ━━━${NC}"
    echo ""
    
    if [ -f "$SCRIPT_DIR/check-config.sh" ]; then
        bash "$SCRIPT_DIR/check-config.sh" "$CONFIG_FILE"
    elif [ -f "$SCRIPT_DIR/check-config.py" ]; then
        python3 "$SCRIPT_DIR/check-config.py" "$CONFIG_FILE"
    else
        echo -e "${YELLOW}⚠ Validation script not found${NC}"
        echo -e "  Running basic check..."
        echo ""
        
        if [ ! -f "$CONFIG_FILE" ]; then
            echo -e "${RED}✗ Configuration file not found: $CONFIG_FILE${NC}"
            return 1
        fi
        
        if python3 -c "import yaml; yaml.safe_load(open('$CONFIG_FILE'))" 2>/dev/null; then
            echo -e "${GREEN}✓ YAML syntax is valid${NC}"
            return 0
        else
            echo -e "${RED}✗ Invalid YAML syntax${NC}"
            return 1
        fi
    fi
}

# Start service
start() {
    show_banner
    echo -e "${BLUE}━━━ Starting ProxyOX ━━━${NC}"
    echo ""
    
    if is_running; then
        echo -e "${YELLOW}⚠ ProxyOX is already running (PID: $(cat $PID_FILE))${NC}"
        echo ""
        return 1
    fi
    
    # Validate config before starting
    echo -e "${CYAN}→ Validating configuration...${NC}"
    if ! validate > /dev/null 2>&1; then
        echo -e "${RED}✗ Configuration validation failed${NC}"
        echo -e "  Run: ${BLUE}$0 validate${NC} for details"
        echo ""
        return 1
    fi
    echo -e "${GREEN}✓ Configuration is valid${NC}"
    echo ""
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}✗ Python 3 is not installed${NC}"
        echo ""
        return 1
    fi
    
    # Check if main script exists
    if [ ! -f "$MAIN_SCRIPT" ]; then
        echo -e "${RED}✗ Main script not found: $MAIN_SCRIPT${NC}"
        echo ""
        return 1
    fi
    
    # Start the service
    echo -e "${CYAN}→ Starting ProxyOX service...${NC}"
    nohup python3 "$MAIN_SCRIPT" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    # Wait a moment and check if it started successfully
    sleep 2
    
    if is_running; then
        echo -e "${GREEN}✓ ProxyOX started successfully${NC}"
        echo -e "  ${CYAN}PID:${NC} ${BLUE}$(cat $PID_FILE)${NC}"
        echo -e "  ${CYAN}Log:${NC} ${BLUE}$LOG_FILE${NC}"
        echo ""
        
        # Show dashboard info
        if [ -f "$SCRIPT_DIR/.env" ]; then
            DASHBOARD_PORT=$(grep "DASHBOARD_PORT" "$SCRIPT_DIR/.env" 2>/dev/null | cut -d'=' -f2 | tr -d ' "'"'"'' || echo "8080")
            DASHBOARD_PORT=${DASHBOARD_PORT:-8080}
            echo -e "${MAGENTA}🌐 Dashboard: ${CYAN}http://localhost:$DASHBOARD_PORT${NC}"
        else
            echo -e "${MAGENTA}🌐 Dashboard: ${CYAN}http://localhost:8080${NC}"
        fi
        echo ""
        return 0
    else
        echo -e "${RED}✗ Failed to start ProxyOX${NC}"
        echo -e "  Check log file for details: ${BLUE}$LOG_FILE${NC}"
        echo ""
        rm -f "$PID_FILE"
        return 1
    fi
}

# Stop service
stop() {
    show_banner
    echo -e "${BLUE}━━━ Stopping ProxyOX ━━━${NC}"
    echo ""
    
    if ! is_running; then
        echo -e "${YELLOW}⚠ ProxyOX is not running${NC}"
        rm -f "$PID_FILE"
        echo ""
        return 0
    fi
    
    PID=$(cat "$PID_FILE")
    echo -e "${CYAN}→ Stopping ProxyOX (PID: $PID)...${NC}"
    
    # Try graceful shutdown first
    kill -TERM "$PID" 2>/dev/null || true
    
    # Wait for graceful shutdown
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ ProxyOX stopped gracefully${NC}"
            rm -f "$PID_FILE"
            echo ""
            return 0
        fi
        sleep 1
    done
    
    # Force kill if still running
    echo -e "${YELLOW}⚠ Forcing shutdown...${NC}"
    kill -KILL "$PID" 2>/dev/null || true
    rm -f "$PID_FILE"
    
    echo -e "${GREEN}✓ ProxyOX stopped${NC}"
    echo ""
    return 0
}

# Restart service
restart() {
    show_banner
    echo -e "${BLUE}━━━ Restarting ProxyOX ━━━${NC}"
    echo ""
    
    if is_running; then
        stop
        sleep 2
    fi
    
    start
}

# Show logs
logs() {
    show_banner
    echo -e "${BLUE}━━━ ProxyOX Logs ━━━${NC}"
    echo ""
    
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}⚠ Log file not found: $LOG_FILE${NC}"
        echo ""
        return 1
    fi
    
    # Check if tail is available
    if command -v tail &> /dev/null; then
        echo -e "${CYAN}→ Showing last 50 lines (Press Ctrl+C to exit)${NC}"
        echo ""
        tail -n 50 -f "$LOG_FILE"
    else
        cat "$LOG_FILE"
    fi
}

# Show help
help() {
    show_banner
    echo -e "${BLUE}━━━ Usage ━━━${NC}"
    echo ""
    echo "  $0 {start|stop|restart|status|validate|logs|help}"
    echo ""
    echo -e "${CYAN}Commands:${NC}"
    echo -e "  ${GREEN}start${NC}      Start ProxyOX service"
    echo -e "  ${GREEN}stop${NC}       Stop ProxyOX service"
    echo -e "  ${GREEN}restart${NC}    Restart ProxyOX service"
    echo -e "  ${GREEN}status${NC}     Show service status"
    echo -e "  ${GREEN}validate${NC}   Validate configuration file"
    echo -e "  ${GREEN}logs${NC}       Show service logs (real-time)"
    echo -e "  ${GREEN}help${NC}       Show this help message"
    echo ""
    echo -e "${CYAN}Examples:${NC}"
    echo "  $0 start"
    echo "  $0 status"
    echo "  $0 logs"
    echo ""
}

# Main
case "${1:-}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    validate|check)
        validate
        ;;
    logs|log)
        logs
        ;;
    help|--help|-h)
        help
        ;;
    *)
        help
        exit 1
        ;;
esac

exit $?
