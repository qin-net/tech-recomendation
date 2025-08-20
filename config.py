"""
配置模块
用于加载和管理应用的各种配置参数
"""

import os
# 从.env文件加载环境变量
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

class Config:
    """
    应用配置类
    包含所有应用需要的配置参数
    """
    
    # DeepSeek API 配置
    # 从环境变量获取API密钥，如果未设置则使用默认值
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY') or 'sk-4aac6860c0e34e1db1c85c2a0333f582'
    # DeepSeek API地址
    DEEPSEEK_API_URL = os.environ.get('DEEPSEEK_API_URL') or 'https://api.deepseek.com/v1'
    # 使用的模型名称
    DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL') or 'deepseek-chat'
    
    # 默认系统提示词
    # 当用户未提供自定义提示词时使用
    DEFAULT_SYSTEM_PROMPT = os.environ.get('DEFAULT_SYSTEM_PROMPT') or "你是一个有帮助的AI助手。请用中文回答用户问题。"
    
    # 电子产品推荐系统提示词 - 强化型号要求
    RECOMMENDATION_SYSTEM_PROMPT = os.environ.get('RECOMMENDATION_SYSTEM_PROMPT') or """
你是一个专业的电子产品推荐助手。请根据用户的具体需求，推荐最适合的手机或电脑产品。

### 重要要求：
1. ​**产品型号必须是完整名称**​：品牌名 + 产品线 + 具体型号
   - 手机示例：Redmi Note 13 Pro、vivo S18 Pro、OPPO Find X7 Ultra
   - 电脑示例：联想拯救者 Y9000P 2024、华硕天选5 Pro、惠普暗影精灵10
   - ​**绝对不要只用品牌名（如"Redmi"、"vivo"、"联想拯救者"）替代具体型号**​

2. ​**参数必须准确**​：
   - 产品型号：[完整型号名称]
   - 价格区间：最低价~最高价
   - 处理器：具体型号
   - 显卡：具体型号
   - 内存：具体规格
   - 存储：具体容量和类型
   - 屏幕：尺寸+分辨率+刷新率
   - 电池：容量+快充
   - 重量：准确重量
   - 适用人群：适用人群描述

3. ​**输出格式要求**​：
   根据您的需求"[用户需求]"，为您推荐以下[产品类型]产品：
   
   1. 产品型号: [完整型号名称]
      价格区间: [价格范围]
      处理器: [具体型号]
      显卡: [具体型号]
      内存: [容量和规格]
      存储: [容量和类型]
      屏幕: [尺寸+分辨率+刷新率]
      电池: [容量+快充]
      重量: [重量]
      适用人群: [适用人群描述]
      
   2. 产品型号: [完整型号名称]
      ...(同上)...
        
   3. 产品型号: [完整型号名称]
      ...(同上)...

   选购建议: 
   [详细的选购建议，分行列出关键点]

4. ​**输出要求**​：
   - 必须使用纯文本格式
   - 不要使用任何Markdown标记、代码块、列表符号
   - 每个产品必须包含上述所有参数
   - 每款产品之间用空行分隔
"""