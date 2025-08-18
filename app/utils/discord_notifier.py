"""
Discord 交易通知服务
用于发送交易成功通知到Discord频道
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger
from config import settings


class DiscordNotifier:
    """Discord 通知服务"""
    
    def __init__(self):
        self.webhook_url = self._get_webhook_url()
        self.session = None
    
    def _get_webhook_url(self) -> Optional[str]:
        """获取Discord webhook URL"""
        try:
            from config import secrets
            return secrets.get('discord', {}).get('transaction_channel')
        except Exception as e:
            logger.warning(f"Failed to load Discord webhook URL: {e}")
            return None
    
    async def _ensure_session(self):
        """确保HTTP会话存在"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def _close_session(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _format_option_symbol(self, option_symbol: str) -> Dict[str, str]:
        """解析期权符号并格式化显示"""
        try:
            # 解析期权符号 (例: AAPL240216C00190000)
            underlying = ""
            date_start_idx = 0
            
            for i, char in enumerate(option_symbol):
                if char.isdigit():
                    underlying = option_symbol[:i]
                    date_start_idx = i
                    break
            
            if not underlying or date_start_idx == 0:
                return {"underlying": option_symbol, "display": option_symbol}
            
            date_part = option_symbol[date_start_idx:date_start_idx+6]
            option_type_char = option_symbol[date_start_idx+6]
            strike_part = option_symbol[date_start_idx+7:]
            
            # 格式化日期
            year = f"20{date_part[:2]}"
            month = date_part[2:4]
            day = date_part[4:6]
            exp_date = f"{year}-{month}-{day}"
            
            # 格式化行权价
            strike_price = float(strike_part) / 1000
            
            # 期权类型
            option_type = "Call" if option_type_char.upper() == 'C' else "Put"
            
            display = f"{underlying} {exp_date} ${strike_price:.2f} {option_type}"
            
            return {
                "underlying": underlying,
                "expiration": exp_date,
                "strike": strike_price,
                "type": option_type,
                "display": display
            }
        except Exception as e:
            logger.warning(f"Failed to parse option symbol {option_symbol}: {e}")
            return {"underlying": option_symbol, "display": option_symbol}
    
    def _create_embed(self, order_data: Dict[str, Any], account_name: str) -> Dict[str, Any]:
        """创建Discord嵌入消息"""
        symbol = order_data.get('symbol', 'Unknown')
        qty = order_data.get('qty', 0)
        side = order_data.get('side', 'unknown').upper()
        order_type = order_data.get('order_type', 'unknown').upper()
        order_id = order_data.get('id', 'Unknown')
        asset_class = order_data.get('asset_class', 'stock')
        limit_price = order_data.get('limit_price')
        
        # 确定颜色
        color = 0x00FF00 if side == 'BUY' else 0xFF0000  # 绿色买入，红色卖出
        
        # 创建标题和描述
        if asset_class == 'option':
            option_info = self._format_option_symbol(symbol)
            title = f"🎯 期权交易成功 - {side}"
            description = f"**{option_info['display']}**"
            symbol_display = option_info['display']
        else:
            title = f"📈 股票交易成功 - {side}"
            description = f"**{symbol}**"
            symbol_display = symbol
        
        # 构建字段
        fields = [
            {
                "name": "📊 交易详情",
                "value": f"**符号:** {symbol_display}\n**数量:** {qty:,}\n**方向:** {side}",
                "inline": True
            },
            {
                "name": "💼 账户信息",
                "value": f"**账户:** {account_name}\n**订单ID:** {order_id[:8]}...",
                "inline": True
            },
            {
                "name": "⚙️ 订单类型",
                "value": f"**类型:** {order_type}" + (f"\n**限价:** ${limit_price:.2f}" if limit_price else ""),
                "inline": True
            }
        ]
        
        # 添加时间戳
        timestamp = datetime.utcnow().isoformat()
        
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "fields": fields,
            "timestamp": timestamp,
            "footer": {
                "text": "Opitios Alpaca Trading Service",
                "icon_url": "https://alpaca.markets/favicon.ico"
            }
        }
        
        return embed
    
    async def send_trade_notification(self, order_data: Dict[str, Any], account_name: str, is_bulk: bool = False) -> bool:
        """发送交易通知到Discord"""
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured, skipping notification")
            return False
        
        try:
            await self._ensure_session()
            
            embed = self._create_embed(order_data, account_name)
            
            # 添加批量交易标识
            if is_bulk:
                embed["title"] = f"🔄 {embed['title']} (批量交易)"
            
            payload = {
                "embeds": [embed],
                "username": "Alpaca Trading Bot",
                "avatar_url": "https://alpaca.markets/favicon.ico"
            }
            
            async with self.session.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 204:
                    logger.info(f"Discord notification sent successfully for order {order_data.get('id', 'Unknown')}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Discord notification failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False
    
    async def send_bulk_trade_summary(self, results: list, symbol: str, qty: int, side: str, asset_class: str = "stock") -> bool:
        """发送批量交易汇总通知"""
        if not self.webhook_url:
            return False
        
        try:
            await self._ensure_session()
            
            successful_orders = sum(1 for r in results if r.get('success', False))
            failed_orders = len(results) - successful_orders
            total_accounts = len(results)
            
            # 确定颜色和图标
            if asset_class == 'option':
                icon = "🎯"
                asset_name = "期权"
                if asset_class == 'option':
                    option_info = self._format_option_symbol(symbol)
                    symbol_display = option_info['display']
                else:
                    symbol_display = symbol
            else:
                icon = "📈"
                asset_name = "股票"
                symbol_display = symbol
            
            color = 0x00FF00 if successful_orders > failed_orders else 0xFFAA00
            
            embed = {
                "title": f"{icon} 批量{asset_name}交易汇总 - {side.upper()}",
                "description": f"**{symbol_display}** x {qty:,}",
                "color": color,
                "fields": [
                    {
                        "name": "📊 执行结果",
                        "value": f"**总账户:** {total_accounts}\n**成功:** {successful_orders}\n**失败:** {failed_orders}",
                        "inline": True
                    },
                    {
                        "name": "✅ 成功账户",
                        "value": "\n".join([
                            f"• {r.get('account_name', r.get('account_id', 'Unknown'))}"
                            for r in results if r.get('success', False)
                        ][:5]) + (f"\n... 还有 {successful_orders - 5} 个" if successful_orders > 5 else ""),
                        "inline": True
                    }
                ],
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "Opitios Alpaca Trading Service - 批量交易",
                    "icon_url": "https://alpaca.markets/favicon.ico"
                }
            }
            
            # 如果有失败的账户，添加失败信息
            if failed_orders > 0:
                failed_accounts = [
                    f"• {r.get('account_name', r.get('account_id', 'Unknown'))}: {r.get('error', 'Unknown error')[:50]}..."
                    for r in results if not r.get('success', False)
                ][:3]
                
                embed["fields"].append({
                    "name": "❌ 失败账户",
                    "value": "\n".join(failed_accounts) + (f"\n... 还有 {failed_orders - 3} 个" if failed_orders > 3 else ""),
                    "inline": False
                })
            
            payload = {
                "embeds": [embed],
                "username": "Alpaca Trading Bot",
                "avatar_url": "https://alpaca.markets/favicon.ico"
            }
            
            async with self.session.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 204:
                    logger.info(f"Discord bulk trade summary sent successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Discord bulk summary failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send Discord bulk summary: {e}")
            return False
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self._close_session()


# 全局Discord通知器实例
discord_notifier = DiscordNotifier()


async def send_trade_notification(order_data: Dict[str, Any], account_name: str, is_bulk: bool = False) -> bool:
    """发送交易通知的便捷函数"""
    return await discord_notifier.send_trade_notification(order_data, account_name, is_bulk)


async def send_bulk_trade_summary(results: list, symbol: str, qty: int, side: str, asset_class: str = "stock") -> bool:
    """发送批量交易汇总的便捷函数"""
    return await discord_notifier.send_bulk_trade_summary(results, symbol, qty, side, asset_class)