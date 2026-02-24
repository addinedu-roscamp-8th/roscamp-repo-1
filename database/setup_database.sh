#!/bin/bash

# ========================================
# Kitchmatic Database Setup Script
# Automated PostgreSQL initialization
# ========================================
#
# Usage:
#   ./setup_database.sh
#   ./setup_database.sh --password "my_secure_password"
#   ./setup_database.sh --host 192.168.1.3 --password "secure_pass"
#
# Requirements:
#   - PostgreSQL must be installed and running
#   - Current user must have sudo access
#   - psql command available in PATH
#

set -e

# ========================================
# Configuration
# ========================================

DB_USER="kitchmatic_user"
DB_NAME="kitchmatic"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_PASSWORD="${DB_PASSWORD:-kitchmatic_secure_password_2025}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ========================================
# Functions
# ========================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_banner() {
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo "║   Kitchmatic Database Setup                ║"
    echo "║   PostgreSQL Initialization Script         ║"
    echo "╚════════════════════════════════════════════╝"
    echo ""
}

check_postgresql() {
    log_info "Checking PostgreSQL installation..."

    if ! command -v psql &> /dev/null; then
        log_error "psql not found. Please install PostgreSQL first."
        echo "  $ sudo apt update"
        echo "  $ sudo apt install postgresql postgresql-contrib"
        exit 1
    fi

    local pg_version=$(psql --version)
    log_success "PostgreSQL found: $pg_version"
}

check_postgres_user() {
    log_info "Checking postgres user access..."

    if ! sudo -u postgres psql -c "SELECT 1" &>/dev/null; then
        log_error "Cannot access PostgreSQL as postgres user"
        log_info "Try: sudo -u postgres psql"
        exit 1
    fi

    log_success "PostgreSQL access verified"
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --password)
                DB_PASSWORD="$2"
                shift 2
                ;;
            --host)
                DB_HOST="$2"
                shift 2
                ;;
            --port)
                DB_PORT="$2"
                shift 2
                ;;
            --user)
                DB_USER="$2"
                shift 2
                ;;
            --help)
                print_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done
}

print_usage() {
    cat << EOF
Usage: ./setup_database.sh [OPTIONS]

Options:
    --password PASSWORD    Database password (default: kitchmatic_secure_password_2025)
    --host HOST           Database host (default: localhost)
    --port PORT           Database port (default: 5432)
    --user USER           Database user (default: kitchmatic_user)
    --help               Show this help message

Examples:
    ./setup_database.sh
    ./setup_database.sh --password "MySecurePassword123!"
    ./setup_database.sh --host 192.168.1.3 --password "secure_pass"
EOF
}

check_user_exists() {
    log_info "Checking if user '$DB_USER' exists..."

    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_user WHERE usename = '$DB_USER'" | grep -q 1; then
        log_warning "User '$DB_USER' already exists"
        return 1
    else
        log_info "User '$DB_USER' does not exist (will create)"
        return 0
    fi
}

check_database_exists() {
    log_info "Checking if database '$DB_NAME' exists..."

    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1; then
        log_warning "Database '$DB_NAME' already exists"
        return 1
    else
        log_info "Database '$DB_NAME' does not exist (will create)"
        return 0
    fi
}

create_user() {
    log_info "Creating database user '$DB_USER'..."

    if sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null; then
        log_success "User created successfully"
    else
        log_error "Failed to create user"
        return 1
    fi
}

update_user_password() {
    log_info "Updating password for user '$DB_USER'..."

    if sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null; then
        log_success "Password updated successfully"
    else
        log_error "Failed to update password"
        return 1
    fi
}

create_database() {
    log_info "Creating database '$DB_NAME'..."

    if sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null; then
        log_success "Database created successfully"
    else
        log_error "Failed to create database"
        return 1
    fi
}

apply_schema() {
    log_info "Applying database schema from schema.sql..."

    local schema_file="$(dirname "$0")/schema.sql"

    if [[ ! -f "$schema_file" ]]; then
        log_error "schema.sql not found at $schema_file"
        return 1
    fi

    if PGPASSWORD="$DB_PASSWORD" psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f "$schema_file" &>/dev/null; then
        log_success "Schema applied successfully"
    else
        log_error "Failed to apply schema"
        log_info "Try running manually:"
        echo "  psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f database/schema.sql"
        return 1
    fi
}

apply_migrations() {
    log_info "Applying database migrations..."

    local migrations_dir="$(dirname "$0")/migrations"

    if [[ ! -d "$migrations_dir" ]]; then
        log_warning "Migrations directory not found at $migrations_dir"
        return 0
    fi

    # Apply all migration files in order
    for migration_file in "$migrations_dir"/*.sql; do
        if [[ -f "$migration_file" ]]; then
            local filename=$(basename "$migration_file")
            log_info "Applying migration: $filename"

            if PGPASSWORD="$DB_PASSWORD" psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f "$migration_file" &>/dev/null; then
                log_success "Migration applied: $filename"
            else
                log_warning "Migration partially applied: $filename (some statements may have failed)"
            fi
        fi
    done
}

verify_connection() {
    log_info "Verifying database connection..."

    if PGPASSWORD="$DB_PASSWORD" psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT version();" &>/dev/null; then
        log_success "Database connection verified"
        return 0
    else
        log_error "Failed to connect to database"
        return 1
    fi
}

verify_schema() {
    log_info "Verifying schema installation..."

    local tables=$(PGPASSWORD="$DB_PASSWORD" psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")

    log_success "Database contains $tables tables"

    # List created tables
    log_info "Tables in database:"
    PGPASSWORD="$DB_PASSWORD" psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "\dt" | sed 's/^/  /'
}

configure_environment() {
    log_info "Creating database configuration file..."

    local config_file="database_config.env"

    cat > "$config_file" << EOF
# Kitchmatic Database Configuration
# Generated by setup_database.sh on $(date)

# Database Connection
DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD

# Connection Pooling (for application)
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30

# Logging
DB_ECHO_SQL=false
EOF

    log_success "Configuration saved to $config_file"
    echo "  Source this file: source $config_file"
}

print_summary() {
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo "║   Setup Complete!                          ║"
    echo "╚════════════════════════════════════════════╝"
    echo ""
    echo "Database Information:"
    echo "  Host:     $DB_HOST"
    echo "  Port:     $DB_PORT"
    echo "  Database: $DB_NAME"
    echo "  User:     $DB_USER"
    echo ""
    echo "Connection examples:"
    echo "  psql -h $DB_HOST -U $DB_USER -d $DB_NAME"
    echo ""
    echo "Environment variables to use:"
    echo "  export DB_HOST=$DB_HOST"
    echo "  export DB_PORT=$DB_PORT"
    echo "  export DB_NAME=$DB_NAME"
    echo "  export DB_USER=$DB_USER"
    echo "  export DB_PASSWORD=$DB_PASSWORD"
    echo ""
    echo "Or source the configuration file:"
    echo "  source database_config.env"
    echo ""
}

# ========================================
# Main Execution
# ========================================

main() {
    print_banner

    # Parse command line arguments
    parse_arguments "$@"

    # Preliminary checks
    check_postgresql
    check_postgres_user

    # Display configuration
    echo ""
    log_info "Using configuration:"
    echo "  Host:     $DB_HOST"
    echo "  Port:     $DB_PORT"
    echo "  Database: $DB_NAME"
    echo "  User:     $DB_USER"
    echo ""

    # Ask for confirmation
    read -p "Continue with setup? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Setup cancelled"
        exit 0
    fi

    echo ""
    log_info "Starting database setup..."
    echo ""

    # Step 1: Create user if not exists
    if ! check_user_exists; then
        update_user_password
    else
        create_user
    fi

    echo ""

    # Step 2: Create database if not exists
    if ! check_database_exists; then
        :  # Database already exists
    else
        create_database
    fi

    echo ""

    # Step 3: Apply schema and migrations
    apply_schema
    echo ""
    apply_migrations
    echo ""

    # Step 4: Verify installation
    verify_connection
    echo ""
    verify_schema
    echo ""

    # Step 5: Create configuration file
    configure_environment

    # Summary
    print_summary

    log_success "Database setup completed successfully!"
}

# Run main function
main "$@"
