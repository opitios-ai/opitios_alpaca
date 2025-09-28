#!/usr/bin/env python3
"""
API Endpoints Testing Script for Opitios Alpaca Trading Service
Tests all API endpoints with configurable environment URLs
"""
import requests
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Configuration - can be set via environment variables
# BASE_URL = os.getenv('API_BASE_URL', 'http://100.64.79.48:8090')  # Default to test environment
BASE_URL = os.getenv('API_BASE_URL', 'http://100.64.79.48:8090')  # Default to test environment
STOCK_ACCOUNT = os.getenv('STOCK_ACCOUNT', 'bowen_paper_trading')
OPTION_ACCOUNT = os.getenv('OPTION_ACCOUNT', 'bowen_paper_trading')
TIMEOUT = int(os.getenv('API_TIMEOUT', '10'))

class EndpointTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Opitios-Endpoint-Tester/1.0'
        })
        
    def test_endpoint(self, method: str, endpoint: str, expected_status: int = 200, 
                     params: Optional[Dict] = None, data: Optional[Dict] = None,
                     description: str = "") -> None:
        """Test a single endpoint and print one-line result"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(full_url, params=params, timeout=TIMEOUT)
            elif method.upper() == 'POST':
                response = self.session.post(full_url, json=data, params=params, timeout=TIMEOUT)
            elif method.upper() == 'DELETE':
                response = self.session.delete(full_url, params=params, timeout=TIMEOUT)
            else:
                print(f"[{timestamp}] {method} {endpoint} - ERROR - Unsupported method")
                return
            
            if response.status_code == expected_status:
                print(f"[{timestamp}] {method} {endpoint} - OK - {description}")
            else:
                # Truncate error message for one-line display
                error_msg = response.text[:50].replace('\n', ' ') if response.text else 'No response body'
                print(f"[{timestamp}] {method} {endpoint} - FAILED - Status {response.status_code}: {error_msg}")
                
        except requests.exceptions.Timeout:
            print(f"[{timestamp}] {method} {endpoint} - TIMEOUT - Request timed out after {TIMEOUT}s")
        except requests.exceptions.ConnectionError:
            print(f"[{timestamp}] {method} {endpoint} - CONNECTION_ERROR - Cannot connect to {self.base_url}")
        except Exception as e:
            print(f"[{timestamp}] {method} {endpoint} - ERROR - {str(e)[:50]}")

    def run_all_tests(self):
        """Run comprehensive tests for all API endpoints"""
        print(f"Testing API endpoints at: {self.base_url}")
        print(f"Stock Account: {STOCK_ACCOUNT}")
        print(f"Option Account: {OPTION_ACCOUNT}")
        print(f"Timeout: {TIMEOUT}s")
        print("=" * 60)
        
        # Health and Connection
        self.test_endpoint('GET', '/api/v1/health', 200, 
                          description='Service health check')
        
        self.test_endpoint('GET', '/api/v1/test-connection', 200,
                          description='Connection test')
        
        # Account Information
        self.test_endpoint('GET', '/api/v1/account', 200, 
                          {'account_id': STOCK_ACCOUNT},
                          description=f'Account info for {STOCK_ACCOUNT}')
        
        self.test_endpoint('GET', '/api/v1/account', 200,
                          {'account_id': OPTION_ACCOUNT},
                          description=f'Account info for {OPTION_ACCOUNT}')
        
        # Positions
        self.test_endpoint('GET', '/api/v1/positions', 200,
                          {'account_id': STOCK_ACCOUNT},
                          description=f'Positions for {STOCK_ACCOUNT}')
        
        self.test_endpoint('GET', '/api/v1/positions', 200,
                          {'account_id': OPTION_ACCOUNT},
                          description=f'Positions for {OPTION_ACCOUNT}')
        
        # Stock Data Endpoints
        self.test_endpoint('POST', '/api/v1/stocks/quotes/batch', 200,
                          data={'symbols': ['AAPL', 'TSLA', 'GOOGL']},
                          description='Batch stock quotes')
        
        self.test_endpoint('GET', '/api/v1/stocks/AAPL/quote', 200,
                          description='Single stock quote (GET)')
        
        self.test_endpoint('POST', '/api/v1/stocks/quote', 200,
                          data={'symbol': 'TSLA'},
                          description='Single stock quote (POST)')
        
        # Stock Bars - should now return data successfully
        self.test_endpoint('GET', '/api/v1/stocks/AAPL/bars', 200,
                          {'timeframe': '1Day', 'limit': 5, 'start_date': '2025-08-25', 'end_date': '2025-08-29'},
                          description='Stock bars')
        
        # Options Endpoints - should now return data successfully
        self.test_endpoint('POST', '/api/v1/options/chain', 200,
                          data={'underlying_symbol': 'AAPL', 'expiration_date': '2025-09-05'},
                          description='Options chain (POST)')
        
        self.test_endpoint('GET', '/api/v1/options/AAPL/chain', 200,
                          {'expiration_date': '2025-09-05'},
                          description='Options chain (GET)')
        
        self.test_endpoint('POST', '/api/v1/options/quote', 200,
                          data={'option_symbol': 'AAPL250905C00230000'},
                          description='Single option quote')
        
        self.test_endpoint('POST', '/api/v1/options/quotes/batch', 200,
                          data={'option_symbols': ['AAPL250905C00230000', 'AAPL250905P00230000']},
                          description='Batch option quotes')
        
        # Trading Endpoints (Test orders with very low prices)
        self.test_endpoint('POST', '/api/v1/stocks/order', 200,
                          {'account_id': STOCK_ACCOUNT},
                          {
                              'symbol': 'AAPL',
                              'qty': 1,
                              'side': 'buy',
                              'type': 'limit',
                              'limit_price': 0.01,
                              'time_in_force': 'day',
                              'bulk_place': False
                          },
                          description='Stock limit order (test)')
        
        self.test_endpoint('POST', '/api/v1/options/order', 200,
                          {'account_id': OPTION_ACCOUNT},
                          {
                              'option_symbol': 'AAPL250905C00230000',
                              'qty': 1,
                              'side': 'buy',
                              'type': 'limit', 
                              'limit_price': 0.01,
                              'time_in_force': 'day',
                              'bulk_place': False
                          },
                          description='Option limit order (test)')
        
        # Order Management
        self.test_endpoint('GET', '/api/v1/orders', 200,
                          {'account_id': STOCK_ACCOUNT, 'limit': 5},
                          description=f'Orders for {STOCK_ACCOUNT}')
        
        self.test_endpoint('GET', '/api/v1/orders', 200,
                          {'account_id': OPTION_ACCOUNT, 'limit': 5},
                          description=f'Orders for {OPTION_ACCOUNT}')
        
        # Quick Trading Endpoints
        self.test_endpoint('POST', '/api/v1/stocks/TSLA/buy', 200,
                          {'qty': 1, 'order_type': 'limit', 'limit_price': 0.01, 'account_id': STOCK_ACCOUNT},
                          description='Quick buy endpoint (test)')
        
        self.test_endpoint('POST', '/api/v1/stocks/AAPL/sell', 200,
                          {'qty': 1, 'order_type': 'limit', 'limit_price': 1000.00, 'account_id': STOCK_ACCOUNT},
                          description='Quick sell endpoint (test)')
        
        print("=" * 60)
        print("API endpoint testing completed")


if __name__ == "__main__":
    print("Opitios Alpaca Trading Service - API Endpoint Tester")
    print("Environment Configuration:")
    print(f"  API_BASE_URL: {BASE_URL}")
    print(f"  STOCK_ACCOUNT: {STOCK_ACCOUNT}")
    print(f"  OPTION_ACCOUNT: {OPTION_ACCOUNT}")
    print(f"  API_TIMEOUT: {TIMEOUT}")
    print("")
    print("Usage:")
    print("  # Test default environment")
    print("  python test_api_endpoints.py")
    print("")
    print("  # Test different environment")
    print("  API_BASE_URL=https://prod.api.example.com python test_api_endpoints.py")
    print("")
    print("  # Test with different accounts")
    print("  STOCK_ACCOUNT=prod_stock OPTION_ACCOUNT=prod_option python test_api_endpoints.py")
    print("")
    
    tester = EndpointTester()
    tester.run_all_tests()