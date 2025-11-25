#!/bin/bash

# mini-lumina startup script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if .env file exists
if [ ! -f .env ]; then
    print_error ".env file not found!"
    print_info "Creating .env from .env.example..."
    cp .env.example .env
    print_warning "Please edit .env file with your credentials before continuing."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
print_info "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check what mode to run
MODE=${1:-"all"}

case $MODE in
    "backend")
        print_info "Starting FastAPI backend on port 8000..."
        uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
        ;;
    "frontend")
        print_info "Starting Streamlit frontend on port 8501..."
        streamlit run streamlit_app/app.py
        ;;
    "test")
        print_info "Running tests..."
        pytest app/tests/ -v --cov=app
        ;;
    "ingest")
        if [ -z "$2" ]; then
            print_error "Please provide a file or directory path to ingest"
            echo "Usage: ./run.sh ingest <path>"
            exit 1
        fi
        print_info "Ingesting documents from: $2"
        python -m app.ingestion "$2"
        ;;
    "eval")
        print_info "Running evaluation..."
        python -m app.eval --dataset eval_dataset.csv --output eval_report.json
        ;;
    "docker")
        print_info "Starting services with Docker Compose..."
        docker-compose up --build
        ;;
    "all")
        print_info "Starting both backend and frontend..."
        print_info "Backend will run on: http://localhost:8000"
        print_info "Frontend will run on: http://localhost:8501"
        print_info "Press Ctrl+C to stop both services"

        # Start backend in background
        uvicorn app.main:app --host 0.0.0.0 --port 8000 &
        BACKEND_PID=$!

        # Give backend time to start
        sleep 3

        # Start frontend
        streamlit run streamlit_app/app.py &
        FRONTEND_PID=$!

        # Trap Ctrl+C and kill both processes
        trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT

        # Wait for both processes
        wait
        ;;
    *)
        print_error "Unknown mode: $MODE"
        echo ""
        echo "Usage: ./run.sh [mode]"
        echo ""
        echo "Modes:"
        echo "  backend   - Run FastAPI backend only"
        echo "  frontend  - Run Streamlit frontend only"
        echo "  all       - Run both backend and frontend (default)"
        echo "  test      - Run pytest tests"
        echo "  ingest    - Ingest documents (requires path argument)"
        echo "  eval      - Run evaluation"
        echo "  docker    - Run with Docker Compose"
        echo ""
        echo "Examples:"
        echo "  ./run.sh                          # Run both services"
        echo "  ./run.sh backend                  # Run only backend"
        echo "  ./run.sh ingest sample_data/      # Ingest sample data"
        echo "  ./run.sh docker                   # Run with Docker"
        exit 1
        ;;
esac


