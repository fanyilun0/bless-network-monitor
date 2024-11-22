import asyncio
import aiohttp
from datetime import datetime, timedelta
import copy
import random
import json
import zstandard as zstd  # 需要先安装：pip install zstandard

previous_state = {}

# 导入配置
from config import (
    API_URL, 
    API_TOKEN, 
    WEBHOOK_URL, 
    PROXY_URL, 
    USE_PROXY, 
    INTERVAL, 
    TIME_OFFSET,
    ALWAYS_NOTIFY
)


def get_random_user_agent():
    """获取随机User-Agent"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
    ]
    return random.choice(user_agents)


async def send_message_async(webhook_url, message_content, use_proxy, proxy_url):
    headers = {'Content-Type': 'application/json'}
    
    payload = {
        "msgtype": "text",
        "text": {
            "content": message_content
        }
    }
    
    proxy = proxy_url if use_proxy else None
    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, json=payload, headers=headers, proxy=proxy) as response:
            if response.status == 200:
                print("Message sent successfully!")
            else:
                print(f"Failed to send message: {response.status}, {await response.text()}")


async def fetch_nodes_data(session):
    """获取节点数据"""
    headers = {
        "authority": "gateway-run.bls.dev",
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "authorization": f"Bearer {API_TOKEN}",
        "content-type": "application/json",
        "origin": "https://bless.network",
        "referer": "https://bless.network/",
        "user-agent": get_random_user_agent()
    }

    try:
        async with session.get(API_URL, headers=headers) as response:
            print(f"响应状态码: {response.status}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print(f"Server: {response.headers.get('server')}")
            
            if response.status == 200:
                # 获取原始压缩数据
                compressed_data = await response.read()
                print(f"Content-Encoding: {response.headers.get('content-encoding')}")
                
                try:
                    # 使用 zstd 解压数据，使用流式解压
                    dctx = zstd.ZstdDecompressor()
                    # 创建一个输入缓冲区
                    with dctx.stream_reader(compressed_data) as reader:
                        decompressed_data = reader.read()
                    
                    # 解析 JSON
                    data = json.loads(decompressed_data)
                    print(f"成功获取数据，节点数量: {len(data) if isinstance(data, list) else 'N/A'}")
                    
                    # 在成功获取数据后添加统计信息
                    if isinstance(data, list):
                        total_reward = sum(node['totalReward'] for node in data)
                        total_today_reward = sum(node['todayReward'] for node in data)
                        online_nodes = sum(1 for node in data if node['isConnected'])
                        
                        print("\n=== 节点统计信息 ===")
                        print(f"总节点数量: {len(data)}")
                        print(f"在线节点数量: {online_nodes}")
                        print(f"总奖励: {total_reward}")
                        print(f"今日总奖励: {total_today_reward}")
                        print("\n=== 各节点详情 ===")
                        for node in data:
                            print(f"\n节点 {node['pubKey'][:20]}...")
                            print(f"  状态: {'在线' if node['isConnected'] else '离线'}")
                            print(f"  总奖励: {node['totalReward']}")
                            print(f"  今日奖励: {node['todayReward']}")
                            print(f"  Sessions数量: {len(node['sessions'])}")
                    
                    return data
                    
                except zstd.ZstdError as e:
                    print(f"ZSTD解压错误: {str(e)}")
                    print(f"压缩数据大小: {len(compressed_data)} 字节")
                    raise
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误: {str(e)}")
                    print(f"解压后的数据前200字节: {decompressed_data[:200]}")
                    raise
            else:
                response_text = await response.text()
                print(f"错误响应: {response_text}")
                raise Exception(f"API请求失败: {response.status}")
                
    except aiohttp.ClientError as e:
        print(f"网络请求错误: {str(e)}")
        raise
    except Exception as e:
        print(f"其他异常: {str(e)}")
        raise

def compare_states(previous, current):
    """比较两个状态的差异"""
    changes = []
    
    for node in current:
        node_id = node['_id']
        prev_node = next((n for n in previous if n['_id'] == node_id), None)
        
        if not prev_node:
            changes.append(f"新增节点: {node['pubKey']}")
            continue
            
        # 检查连接状态变化
        if node['isConnected'] != prev_node['isConnected']:
            status = "上线" if node['isConnected'] else "离线"
            changes.append(f"节点 {node['pubKey']} {status}")
            
        # 检查奖励变化
        if node['totalReward'] != prev_node['totalReward']:
            reward_diff = node['totalReward'] - prev_node['totalReward']
            changes.append(f"节点 {node['pubKey']} 总奖励变化: +{reward_diff}")
            
        if node['todayReward'] != prev_node['todayReward']:
            reward_diff = node['todayReward'] - prev_node['todayReward']
            changes.append(f"节点 {node['pubKey']} 今日奖励变化: +{reward_diff}")
            
        # 检查sessions变化
        if len(node['sessions']) != len(prev_node['sessions']):
            changes.append(f"节点 {node['pubKey']} sessions数量变化: {len(prev_node['sessions'])} -> {len(node['sessions'])}")
    
    return changes

def build_message(changes):
    """构建消息内容"""
    if not changes:
        return None
        
    adjusted_time = datetime.now() + timedelta(hours=TIME_OFFSET)
    timestamp = adjusted_time.strftime('%Y-%m-%d %H:%M:%S')
    
    message_lines = [
        "【节点状态变化监控】",
        f"时间: {timestamp}\n",
        "变化详情:"
    ]
    
    for change in changes:
        message_lines.append(f"- {change}")
        
    return "\n".join(message_lines)

async def monitor_nodes(interval, webhook_url, use_proxy, proxy_url, always_notify=False):
    """监控节点状态"""
    global previous_state
    
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                current_state = await fetch_nodes_data(session)
                
                if current_state:
                  print("\n=== 状态检查 ===")
                  if previous_state:
                      print("比较前后状态差异...")
                      changes = compare_states(previous_state, current_state)
                      print(f"检测到 {len(changes) if changes else 0} 个变化")
                      
                      # 如果有变化或者设置了始终通知，则发送消息
                      if changes or always_notify:
                          print(f"需要发送消息: {'有状态变化' if changes else '始终通知模式'}")
                          message = build_message(changes) if changes else build_status_message(current_state)
                          if message:
                              await send_message_async(webhook_url, message, use_proxy, proxy_url)
                  else:
                      print("首次运行，发送初始状态报告...")
                      # 首次运行也发送状态报告
                      message = build_status_message(current_state)
                      if message:
                          print("\n待发送的消息内容:")
                          print("-------------------")
                          print(message)
                          print("-------------------")
                          await send_message_async(webhook_url, message, use_proxy, proxy_url)
                  
                  print("更新previous_state...")
                  previous_state = copy.deepcopy(current_state)
                  print("状态更新完成")
                
        except Exception as e:
            print(f"监控过程出错: {str(e)}")
            await asyncio.sleep(5)
            continue
            
        await asyncio.sleep(interval)

def build_status_message(current_state):
    """构建状态消息"""
    adjusted_time = datetime.now() + timedelta(hours=TIME_OFFSET)
    timestamp = adjusted_time.strftime('%Y-%m-%d %H:%M:%S')
    
    total_reward = sum(node['totalReward'] for node in current_state)
    total_today_reward = sum(node['todayReward'] for node in current_state)
    online_nodes = sum(1 for node in current_state if node['isConnected'])
    
    message_lines = [
        "【节点状态报告】",
        f"时间: {timestamp}\n",
        f"节点总数: {len(current_state)}",
        f"在线节点: {online_nodes}",
        f"总奖励: {total_reward}",
        f"今日奖励: {total_today_reward}\n",
        "节点详情:"
    ]
    
    for node in current_state:
        message_lines.append(
            f"- {node['pubKey'][:20]}... "
            f"{'在线' if node['isConnected'] else '离线'} "
            f"总奖励:{node['totalReward']} "
            f"今日奖励:{node['todayReward']}"
        )
    
    return "\n".join(message_lines)

if __name__ == "__main__":
    asyncio.run(monitor_nodes(
        interval=INTERVAL,
        webhook_url=WEBHOOK_URL,
        use_proxy=USE_PROXY,
        proxy_url=PROXY_URL,
        always_notify=ALWAYS_NOTIFY  # 添加这个参数来启用始终通知
    ))
