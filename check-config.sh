#!/bin/bash
#
# ProxyOX - Configuration Checker for Linux
# Validates config.yaml before starting the service
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CONFIG_FILE="${1:-config.yaml}"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  ProxyOX Configuration Checker${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ Error: Configuration file '$CONFIG_FILE' not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Configuration file found: ${BLUE}$CONFIG_FILE${NC}"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: Python 3 is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python 3 is available"

# Check if PyYAML is installed
if ! python3 -c "import yaml" 2>/dev/null; then
    echo -e "${YELLOW}⚠ Warning: PyYAML is not installed${NC}"
    echo -e "  Installing requirements..."
    pip3 install -r requirements.txt --quiet
fi

echo -e "${GREEN}✓${NC} Dependencies are installed"
echo ""

# Run Python validation script if available
if [ -f "check-config.py" ]; then
    echo -e "${BLUE}Running detailed validation...${NC}"
    echo ""
    
    python3 check-config.py "$CONFIG_FILE"
    exit_code=$?
    
    exit $exit_code
else
    # Fallback: Basic YAML syntax check
    echo -e "${YELLOW}⚠ Detailed validator not found, running basic check...${NC}"
    echo ""
    
    if python3 -c "
import yaml
import sys

try:
    with open('$CONFIG_FILE', 'r') as f:
        config = yaml.safe_load(f)
    
    # Basic structure check
    if not isinstance(config, dict):
        print('❌ Config must be a dictionary')
        sys.exit(1)
    
    if 'frontends' not in config:
        print('❌ Missing frontends section')
        sys.exit(1)
    
    if 'backends' not in config:
        print('❌ Missing backends section')
        sys.exit(1)
    
    print('✓ YAML syntax is valid')
    print('✓ Basic structure is correct')
    print('')
    print('Frontends:', len(config.get('frontends', [])))
    print('Backends:', len(config.get('backends', [])))
    
except yaml.YAMLError as e:
    print(f'❌ YAML parsing error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Error: {e}')
    sys.exit(1)
" 2>&1; then
        echo ""
        echo -e "${GREEN}✓ Basic validation passed${NC}"
        exit 0
    else
        echo ""
        echo -e "${RED}✗ Validation failed${NC}"
        exit 1
    fi
fi
