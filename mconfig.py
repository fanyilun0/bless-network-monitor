# API配置
API_URL = "https://gateway-run.bls.dev/api/v1/nodes"

# Token配置示例
# TOKENS_CONFIG = [
#     {
#         'name': 'Token1',  # token标识名称
#         'token': 'your_token_1',
#         'previous_state': {}  # 用于存储上一次状态
#     },
#     {
#         'name': 'Token2',
#         'token': 'your_token_2',
#         'previous_state': {}
#     },
#     # 可以添加更多token配置...
# ]
# Webhook配置
WEBHOOK_URL = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key='

# 代理配置
PROXY_URL = 'http://localhost:7890'
USE_PROXY = False
ALWAYS_SEND = True
# 时间配置
INTERVAL = 300  # 5分钟检查一次
TIME_OFFSET = 8  
