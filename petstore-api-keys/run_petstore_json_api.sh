#!/bin/bash

# Enhanced API Traffic Simulator Runner
# Production-ready script with error handling and colored output

set -e  # Exit on error

# ============================================================================
# COLOR DEFINITIONS
# ============================================================================
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m' # No Color

# ============================================================================
# CONFIGURATION
# ============================================================================
readonly REPO_DIR="${HOME}/Documents/GitHub/petstore-api-workers"
readonly VENV_DIR="PETSTORE_API"
readonly LOG_DIR="logs"
readonly TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Simulation parameters (can be overridden via environment variables)
readonly DURATION=${SIM_DURATION:-30}
readonly RATE=${SIM_RATE:-60}
readonly PARALLEL=${SIM_PARALLEL:-3}
readonly MIN_PETS=${SIM_MIN_PETS:-10}
readonly MIN_USERS=${SIM_MIN_USERS:-10}

# API endpoints
readonly PETSTORE_URL="https://petstore.automatic-demo.com/api/v3/"
readonly JSON_API_URL="https://json.dlsdemo.com"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

print_banner() {
    echo -e "${MAGENTA}${BOLD}"
    echo "================================================================================"
    echo "   API TRAFFIC SIMULATOR ORCHESTRATOR"
    echo "================================================================================"
    echo -e "${NC}"
}

print_section() {
    echo -e "\n${CYAN}${BOLD}▶ $1${NC}"
    echo -e "${CYAN}$(printf '─%.0s' {1..80})${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "Required command '$1' not found"
        return 1
    fi
    return 0
}

cleanup() {
    local exit_code=$?
    print_section "Cleanup"
    
    # Kill background processes
    if [ -n "${PETSTORE_PID}" ]; then
        if kill -0 "${PETSTORE_PID}" 2>/dev/null; then
            print_info "Stopping Petstore simulator (PID: ${PETSTORE_PID})"
            kill "${PETSTORE_PID}" 2>/dev/null || true
        fi
    fi
    
    if [ -n "${JSON_API_PID}" ]; then
        if kill -0 "${JSON_API_PID}" 2>/dev/null; then
            print_info "Stopping JSON API simulator (PID: ${JSON_API_PID})"
            kill "${JSON_API_PID}" 2>/dev/null || true
        fi
    fi
    
    # Deactivate virtual environment
    if [ -n "${VIRTUAL_ENV}" ]; then
        deactivate 2>/dev/null || true
    fi
    
    if [ $exit_code -eq 0 ]; then
        print_success "Cleanup completed"
    else
        print_warning "Cleanup completed with errors (exit code: $exit_code)"
    fi
}

trap cleanup EXIT INT TERM

# ============================================================================
# MAIN SCRIPT
# ============================================================================

main() {
    print_banner
    
    # Display configuration
    print_section "Configuration"
    print_info "Repository:        ${BOLD}${REPO_DIR}${NC}"
    print_info "Virtual Env:       ${BOLD}${VENV_DIR}${NC}"
    print_info "Duration:          ${BOLD}${DURATION} minutes${NC}"
    print_info "Rate:              ${BOLD}${RATE} ops/minute${NC}"
    print_info "Parallel Threads:  ${BOLD}${PARALLEL}${NC}"
    print_info "Petstore URL:      ${BOLD}${PETSTORE_URL}${NC}"
    print_info "JSON API URL:      ${BOLD}${JSON_API_URL}${NC}"
    
    # Check prerequisites
    print_section "Prerequisites Check"
    
    local prereqs_ok=true
    for cmd in python3 pip; do
        if check_command "$cmd"; then
            print_success "$cmd found"
        else
            prereqs_ok=false
        fi
    done
    
    if [ "$prereqs_ok" = false ]; then
        print_error "Missing required commands. Please install them first."
        exit 1
    fi
    
    # Change to repository directory
    print_section "Directory Setup"
    if [ ! -d "$REPO_DIR" ]; then
        print_error "Repository directory not found: ${REPO_DIR}"
        print_info "Please update REPO_DIR in the script"
        exit 1
    fi
    
    cd "$REPO_DIR" || exit 1
    print_success "Changed to: $(pwd)"
    
    # Create logs directory
    mkdir -p "$LOG_DIR"
    print_success "Logs directory: ${LOG_DIR}/"
    
    # Setup virtual environment
    print_section "Virtual Environment Setup"
    
    if [ ! -d "$VENV_DIR" ]; then
        print_info "Creating virtual environment..."
        python3 -m venv "$VENV_DIR" || {
            print_error "Failed to create virtual environment"
            exit 1
        }
        print_success "Virtual environment created"
    else
        print_success "Virtual environment exists"
    fi
    
    # Activate virtual environment
    print_info "Activating virtual environment..."
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate" || {
        print_error "Failed to activate virtual environment"
        exit 1
    }
    print_success "Virtual environment activated"
    
    # Install/upgrade dependencies
    print_section "Dependencies Installation"
    print_info "Upgrading pip..."
    pip install --upgrade pip --quiet
    print_success "pip upgraded"
    
    print_info "Installing required packages..."
    pip install --quiet \
        "httpx[http2]" \
        authlib \
        cryptography \
        fake_useragent || {
        print_error "Failed to install required packages"
        exit 1
    }
    print_success "All packages installed"
    
    # Verify scripts exist
    print_section "Script Verification"
    
    local scripts_ok=true
    for script in "traffic-simulator.py" "traffic-simulator-json-api.py"; do
        if [ -f "$script" ]; then
            print_success "$script found"
        else
            print_error "$script not found"
            scripts_ok=false
        fi
    done
    
    if [ "$scripts_ok" = false ]; then
        print_error "Required scripts missing"
        exit 1
    fi
    
    # Start simulators
    print_section "Starting Traffic Simulators"
    
    # Start Petstore API simulator
    print_info "Starting Petstore API simulator..."
    python traffic-simulator.py \
        --url "$PETSTORE_URL" \
        --duration "$DURATION" \
        --rate "$RATE" \
        --min-pets "$MIN_PETS" \
        --min-users "$MIN_USERS" \
        --parallel "$PARALLEL" \
        --use-jwt \
        > "${LOG_DIR}/petstore_${TIMESTAMP}.log" 2>&1 &
    
    PETSTORE_PID=$!
    print_success "Petstore simulator started (PID: ${PETSTORE_PID})"
    print_info "Log file: ${LOG_DIR}/petstore_${TIMESTAMP}.log"
    
    # Small delay to stagger starts
    sleep 2
    
    # Start JSON API simulator
    print_info "Starting JSON API simulator..."
    python traffic-simulator-json-api.py \
        > "${LOG_DIR}/json_api_${TIMESTAMP}.log" 2>&1 &
    
    JSON_API_PID=$!
    print_success "JSON API simulator started (PID: ${JSON_API_PID})"
    print_info "Log file: ${LOG_DIR}/json_api_${TIMESTAMP}.log"
    
    # Monitor simulators
    print_section "Monitoring Simulators"
    print_info "Both simulators are running. Press Ctrl+C to stop."
    echo ""
    
    # Wait for both processes with progress updates
    local wait_time=0
    local max_wait=$((DURATION * 60))
    local update_interval=30  # Update every 30 seconds
    
    while kill -0 "$PETSTORE_PID" 2>/dev/null || kill -0 "$JSON_API_PID" 2>/dev/null; do
        sleep "$update_interval"
        wait_time=$((wait_time + update_interval))
        
        local elapsed_min=$((wait_time / 60))
        local remaining_min=$(((max_wait - wait_time) / 60))
        
        if [ $wait_time -le $max_wait ]; then
            print_info "Progress: ${elapsed_min}/${DURATION} minutes elapsed, ${remaining_min} minutes remaining"
            
            # Check if processes are still running
            if ! kill -0 "$PETSTORE_PID" 2>/dev/null; then
                print_warning "Petstore simulator has stopped"
            fi
            if ! kill -0 "$JSON_API_PID" 2>/dev/null; then
                print_warning "JSON API simulator has stopped"
            fi
        fi
    done
    
    # Generate completion summary
    print_section "Simulation Complete"
    
    echo ""
    echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}${BOLD}║                   ALL SIMULATIONS COMPLETED SUCCESSFULLY                   ║${NC}"
    echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    print_info "Duration: ${DURATION} minutes"
    print_info "Simulators: 2 (Petstore API + JSON API)"
    print_info "Logs saved to: ${LOG_DIR}/"
    
    # Show log files
    echo ""
    print_section "Output Files"
    for log_file in "${LOG_DIR}"/*"${TIMESTAMP}"*; do
        if [ -f "$log_file" ]; then
            local size=$(du -h "$log_file" | cut -f1)
            print_success "$(basename "$log_file") (${size})"
        fi
    done
    
    # Show summary of simulation reports
    echo ""
    print_section "Generated Reports"
    for report in traffic_simulation_report*.txt petstore_simulator.log; do
        if [ -f "$report" ]; then
            print_success "$report"
        fi
    done
    
    echo ""
    print_info "To view detailed results:"
    echo -e "  ${CYAN}tail -f ${LOG_DIR}/petstore_${TIMESTAMP}.log${NC}"
    echo -e "  ${CYAN}tail -f ${LOG_DIR}/json_api_${TIMESTAMP}.log${NC}"
    echo ""
}

# Run main function
main "$@"