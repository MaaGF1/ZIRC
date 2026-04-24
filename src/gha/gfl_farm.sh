#!/bin/bash
# gfl_farm.sh - Local Controller for GFL Auto Farm

PIDS_DIR="./run"
LOGS_DIR="./logs"
ENV_FILE="./.env"

# Ensure directories exist
mkdir -p "$PIDS_DIR"
mkdir -p "$LOGS_DIR"

# Print Help
show_help() {
    echo "Usage: ./gfl_farm.sh [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start -<mission>   Start farming (e.g., ./gfl_farm.sh start -f2p)"
    echo "                     Valid missions: f2p, f2p_pr, pick_coin, epa_fifo, epa_rr"
    echo "  stop               Stop all running agents safely"
    echo "  status             Check if agents are running"
    echo "  log [account_idx]  Tail the log of a specific account (default: 0)"
    echo ""
}

# Source secrets safely
load_env() {
    if [ ! -f "$ENV_FILE" ]; then
        echo "[-] FATAL: $ENV_FILE not found."
        exit 1
    fi
    source "$ENV_FILE"
}

# Command: start
start_agents() {
    local mission=$1
    mission=${mission#-} # Remove leading dash if provided
    
    if [ -z "$mission" ]; then
        echo "[-] Mission type not specified. Defaulting to 'f2p'."
        mission="f2p"
    fi

    load_env

    # Determine number of accounts from GFL_CONFIG JSON array length
    local acc_count=$(python3 -c "
import os, json
try:
    c = json.loads(os.environ.get('GFL_CONFIG', '[]'))
    print(len(c) if isinstance(c, list) else 1)
except:
    print(1)
")

    echo "[*] Starting $acc_count account(s) for mission: $mission"

    for (( i=0; i<$acc_count; i++ )); do
        local pid_file="$PIDS_DIR/agent_${i}.pid"
        local log_file="$LOGS_DIR/agent_${i}.log"

        if [ -f "$pid_file" ] && kill -0 $(cat "$pid_file" 2>/dev/null) 2>/dev/null; then
            echo "[!] Account [$i] is already running (PID: $(cat $pid_file)). Skipping."
            continue
        fi

        # The Daemon Loop (runs in background subshell)
        (
            echo "=== Farm Session Started: $(date -u) ===" >> "$log_file"
            while true; do
                rm -f "respawn.flag"
                
                # Execute Python Agent
                GFL_MISSION_TYPE="$mission" \
                GFL_ACCOUNT_INDEX="$i" \
                PYTHONUNBUFFERED="1" \
                python3 src/gha/agent.py >> "$log_file" 2>&1
                
                local exit_code=$?
                
                if [ -f "respawn.flag" ]; then
                    echo "[System] Respawn flag triggered. Restarting loop in 5s..." >> "$log_file"
                    sleep 5
                elif [ $exit_code -ne 0 ]; then
                    echo "[System] Agent crashed with exit code $exit_code. Restarting in 60s..." >> "$log_file"
                    sleep 60
                else
                    echo "[System] Agent finished gracefully. Exiting daemon." >> "$log_file"
                    break
                fi
            done
            # Cleanup PID file when done
            rm -f "$pid_file"
        ) & 
        
        # Save background subshell PID
        echo $! > "$pid_file"
        echo "[+] Account [$i] Daemon spawned successfully. (PID: $!)"
    done
    
    echo "[+] All agents started in background. Use './gfl_farm.sh status' to check."
}

# Command: stop
stop_agents() {
    echo "[*] Stopping all agents..."
    for pid_file in $PIDS_DIR/*.pid; do
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file")
            # Kill the subshell and its child python processes
            pkill -P "$pid" 2>/dev/null
            kill "$pid" 2>/dev/null
            rm -f "$pid_file"
            echo "  [-] Stopped Daemon PID $pid"
        fi
    done
    # Failsafe kill
    pkill -f "python3 src/gha/agent.py" 2>/dev/null
    echo "[+] All agents stopped."
}

# Command: status
check_status() {
    echo "=== Agent Status ==="
    local running=0
    for pid_file in $PIDS_DIR/*.pid; do
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file")
            local acc_idx=$(basename "$pid_file" | tr -dc '0-9')
            if kill -0 "$pid" 2>/dev/null; then
                echo "[+] Account [$acc_idx]: RUNNING (PID: $pid)"
                running=$((running + 1))
            else
                echo "[-] Account [$acc_idx]: STALE PID DETECTED"
                rm -f "$pid_file"
            fi
        fi
    done
    
    if [ "$running" -eq 0 ]; then
        echo "No agents are currently running."
    fi
    echo "===================="
}

# Command: log
tail_logs() {
    local acc_idx=${1:-0}
    local log_file="$LOGS_DIR/agent_${acc_idx}.log"
    if [ -f "$log_file" ]; then
        echo "[*] Tailing log for Account [$acc_idx]. Press Ctrl+C to exit."
        tail -n 50 -f "$log_file"
    else
        echo "[-] Log file $log_file not found."
    fi
}

# Main Router
case "$1" in
    start)
        start_agents "$2"
        ;;
    stop)
        stop_agents
        ;;
    status)
        check_status
        ;;
    log)
        tail_logs "$2"
        ;;
    *)
        show_help
        ;;
esac