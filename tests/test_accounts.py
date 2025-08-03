import asyncio
from app.account_pool import AccountConnectionPool

async def test_individual_accounts():
    print('=== Testing Individual Account Functionality ===')
    
    # 初始化连接池
    pool = AccountConnectionPool()
    await pool.initialize()
    
    # 测试每个账户
    accounts = ['account_001', 'account_002', 'account_003']
    
    for account_id in accounts:
        print(f'\n--- Testing {account_id} ---')
        
        try:
            # 使用正确的异步上下文管理器
            async with pool.get_account_connection(account_id) as connection:
                # 测试连接
                result = await connection.test_connection()
                print(f'  Connection test: {result["status"]}')
                
                if result['status'] == 'connected':
                    print(f'  Account Number: {result["account_number"]}')
                    print(f'  Buying Power: ${result["buying_power"]:,.2f}')
                    print(f'  Portfolio Value: ${result["portfolio_value"]:,.2f}')
                    
                    # 测试股票报价
                    quote_result = await connection.get_stock_quote('AAPL')
                    if 'error' not in quote_result:
                        print(f'  AAPL Quote - Bid: ${quote_result["bid_price"]}, Ask: ${quote_result["ask_price"]}')
                    else:
                        print(f'  Quote Error: {quote_result["error"]}')
                
            print(f'  [SUCCESS] {account_id} test completed successfully')
            
        except Exception as e:
            print(f'  [FAILED] {account_id} test failed: {e}')

if __name__ == "__main__":
    asyncio.run(test_individual_accounts())