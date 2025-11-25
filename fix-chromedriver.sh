#!/bin/bash
# Fix ChromeDriver Version Mismatch
# This script updates ChromeDriver to match your Chrome version

set -e

echo "============================================"
echo "ChromeDriver Version Fix Script"
echo "============================================"
echo ""

# Get Chrome version
CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+\.\d+')
CHROME_MAJOR=$(echo $CHROME_VERSION | cut -d. -f1)

echo "Detected Chrome version: $CHROME_VERSION"
echo "Chrome major version: $CHROME_MAJOR"
echo ""

# Check current ChromeDriver
if [ -f "/usr/local/bin/chromedriver" ]; then
    CURRENT_DRIVER=$(/usr/local/bin/chromedriver --version 2>/dev/null || echo "Unknown")
    echo "Current ChromeDriver: $CURRENT_DRIVER"
    echo ""
fi

# For Chrome 115+, use Chrome for Testing endpoints
if [ $CHROME_MAJOR -ge 115 ]; then
    echo "Chrome version is 115+, using Chrome for Testing API..."
    
    # Get the correct ChromeDriver version
    DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR}")
    
    if [ -z "$DRIVER_VERSION" ]; then
        echo "Error: Could not find ChromeDriver for Chrome $CHROME_MAJOR"
        echo "Trying to get any stable version..."
        DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE")
    fi
    
    echo "ChromeDriver version to install: $DRIVER_VERSION"
    
    # Download URL
    DOWNLOAD_URL="https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip"
    
    echo "Downloading from: $DOWNLOAD_URL"
    
    # Download and install
    cd /tmp
    wget -q "$DOWNLOAD_URL" -O chromedriver.zip
    
    if [ ! -f "chromedriver.zip" ]; then
        echo "Error: Download failed"
        exit 1
    fi
    
    unzip -q chromedriver.zip
    sudo mv chromedriver-linux64/chromedriver /usr/local/bin/
    sudo chmod +x /usr/local/bin/chromedriver
    rm -rf chromedriver.zip chromedriver-linux64
    
else
    # For Chrome 114 and below (legacy method)
    echo "Chrome version is below 115, using legacy API..."
    
    DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR}")
    
    echo "ChromeDriver version to install: $DRIVER_VERSION"
    
    DOWNLOAD_URL="https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip"
    
    cd /tmp
    wget -q "$DOWNLOAD_URL" -O chromedriver.zip
    unzip -q chromedriver.zip
    sudo mv chromedriver /usr/local/bin/
    sudo chmod +x /usr/local/bin/chromedriver
    rm chromedriver.zip
fi

echo ""
echo "============================================"
echo "✓ ChromeDriver Updated Successfully!"
echo "============================================"
echo ""

# Verify installation
NEW_DRIVER=$(/usr/local/bin/chromedriver --version)
echo "New ChromeDriver version: $NEW_DRIVER"
echo "Chrome version: $CHROME_VERSION"
echo ""

# Test compatibility
echo "Testing Selenium with new ChromeDriver..."
source /home/ubuntu/venvs/bots/bin/activate

python3 << 'PYEOF'
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

try:
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    print("✓ Selenium test successful!")
    print(f"✓ Browser user agent: {driver.execute_script('return navigator.userAgent')}")
    driver.quit()
    print("✓ All tests passed!")
except Exception as e:
    print(f"✗ Test failed: {e}")
    exit(1)
PYEOF

deactivate

echo ""
echo "============================================"
echo "You can now run your bot:"
echo "  /home/ubuntu/bots/run-bot.sh"
echo "============================================"
