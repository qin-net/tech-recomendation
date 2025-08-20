from flask import Flask, render_template, request, jsonify
import requests
import os
import json
import logging
import re
from openai import OpenAI
from config import Config

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 创建Flask应用实例
app = Flask(__name__)
# 从配置类加载配置
app.config.from_object(Config)

# 初始化OpenAI客户端（用于设备评分功能）
openai_client = OpenAI(
    api_key=Config.DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# ===== 产品推荐功能 =====
def parse_recommendations(ai_response):
    """解析AI返回的文本推荐为结构化的JSON格式"""
    recommendations = []
    
    # 改进的分割逻辑：按数字编号分割产品
    sections = re.split(r'\n\s*\d+\.\s+', ai_response)
    sections = [s.strip() for s in sections if s.strip()]
    
    # 提取导语
    intro_match = re.search(r'根据您的需求".*?"，为您推荐以下(.*?)产品：([\s\S]*?)(\d+\.|\n选购建议)', ai_response)
    intro = intro_match.group(2).strip() if intro_match else ""
    
    # 尝试提取选购建议
    tips_match = re.search(r'选购建议[:：]?([\s\S]+)', ai_response)
    tips = tips_match.group(1).strip() if tips_match else ""
    
    # 解析产品推荐
    for section in sections:
        # 跳过非产品部分
        if "选购建议" in section or "适用人群" not in section:
            continue
            
        try:
            # 强化产品名称提取
            name_match = re.search(r'产品型号\s*[:：]\s*([^\n]+)', section)
            if name_match:
                name = name_match.group(1).strip()
            else:
                name_match = re.search(r'^(.+?)(?:（|\()[^)]+', section) or \
                             re.search(r'^(.+?):', section) or \
                             re.search(r'^(.+?)\s{2,}', section)
                name = name_match.group(1).strip() if name_match else ""
            
            # 强化型号提取 - 直接查找参数之前的内容
            if not name:
                name = re.split(r'\n(处理器:|内存:|存储:|价格区间:|适用人群:)', section)[0].strip()
            
            # 特殊处理：移除可能存在的多余前缀
            name = re.sub(r'^\d+\.\s*|产品型号\s*[:：]\s*', '', name)
            
            # 关键改进：确保名称包含品牌+型号
            if len(name.split()) < 2 or not any(char.isdigit() for char in name):
                model_match = re.search(r'型号\s*[:：]\s*([^\n]+)', section)
                if model_match:
                    name = (name + " " + model_match.group(1).strip()).strip()
                else:
                    brand_match = re.search(r'品牌\s*[:：]\s*([^\n]+)', section)
                    if brand_match and name:
                        name = brand_match.group(1).strip() + " " + name
                    
            # 提取价格范围
            price_match = re.search(r'价格区间\s*[:：]\s*([^\n]+)', section)
            price = price_match.group(1).strip() if price_match else "价格未提供"
            
            # 优化价格格式
            if "~" not in price and "至" not in price:
                price_fallback = re.search(r'(\d+)\s*元\s*[到至~-]\s*(\d+)\s*元', section)
                if price_fallback:
                    price = f"{price_fallback.group(1)}~{price_fallback.group(2)}元"
            
            # 规格参数提取映射
            param_map = {
                "处理器": r'处理器\s*[:：]\s*([^\n]+)',
                "显卡": r'显卡\s*[:：]\s*([^\n]+)',
                "内存": r'内存\s*[:：]\s*([^\n]+)',
                "存储": r'存储\s*[:：]\s*([^\n]+)',
                "屏幕": r'屏幕\s*[:：]\s*([^\n]+)',
                "电池": r'电池\s*[:：]\s*([^\n]+)',
                "重量": r'重量\s*[:：]\s*([^\n]+)',
                "适用人群": r'适用人群\s*[:：]\s*([^\n]+)'
            }
            
            specs = {}
            for param, pattern in param_map.items():
                match = re.search(pattern, section)
                if match:
                    specs[param] = match.group(1).strip()
            
            # 确保至少提取到部分规格
            if not specs:
                logger.warning(f"未提取到规格参数: {section}")
                continue
                
            recommendations.append({
                "name": name,
                "price": price,
                "specs": specs
            })
        except Exception as e:
            logger.error(f"解析产品时出错: {str(e)}")
            continue
    
    # 如果没有解析出任何产品，返回原始文本
    if not recommendations:
        return None, ai_response
    
    return intro, {
        "intro": intro,
        "recommendations": recommendations,
        "tips": tips
    }

@app.route('/recommend')
def recommend_page():
    """产品推荐页面"""
    return render_template('recommend.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """聊天API端点"""
    try:
        # 获取请求数据
        data = request.get_json()
        logger.debug(f"收到聊天请求数据: {data}")
        
        if not data:
            logger.error("请求数据格式错误：无JSON数据")
            return jsonify({'error': '请求数据格式错误'}), 400
            
        user_message = data.get('message', '')
        system_prompt = data.get('system_prompt', app.config['DEFAULT_SYSTEM_PROMPT'])
        
        # 检查用户消息是否为空
        if not user_message:
            logger.error("消息不能为空")
            return jsonify({'error': '消息不能为空'}), 400

        # 构建请求头
        headers = {
            'Authorization': f"Bearer {app.config['DEEPSEEK_API_KEY']}",
            'Content-Type': 'application/json'
        }
        
        # 构建请求载荷
        payload = {
            "model": app.config['DEEPSEEK_MODEL'],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "stream": False
        }
        
        # 发送API请求
        response = requests.post(
            app.config['DEEPSEEK_API_URL'],
            headers=headers,
            json=payload,
            timeout=60
        )
        
        # 处理API响应
        if response.status_code == 200:
            response_data = response.json()
            
            if 'choices' in response_data and response_data['choices']:
                ai_response = response_data['choices'][0].get('message', {}).get('content', '')
                if ai_response:
                    return jsonify({'message': ai_response})
                else:
                    logger.error("AI返回了空内容")
                    return jsonify({'error': 'AI返回了空内容'}), 500
            else:
                logger.error(f"AI返回数据格式不正确: {response_data}")
                return jsonify({'error': 'AI返回数据格式不正确'}), 500
        else:
            error_text = response.text
            logger.error(f"API调用失败: {response.status_code} - {error_text}")
            return jsonify({'error': f'API调用失败: {response.status_code} - {error_text}'}), response.status_code
            
    except requests.exceptions.Timeout:
        logger.error("API调用超时")
        return jsonify({'error': 'API调用超时'}), 500
    except requests.exceptions.RequestException as e:
        logger.error(f"网络请求错误: {str(e)}")
        return jsonify({'error': f'网络请求错误: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"服务器错误: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@app.route('/api/recommend', methods=['POST'])
def recommend():
    """产品推荐API端点"""
    try:
        # 获取请求数据
        data = request.get_json()
        logger.debug(f"收到推荐请求数据: {data}")
        
        if not data:
            logger.error("请求数据格式错误：无JSON数据")
            return jsonify({'error': '请求数据格式错误'}), 400
            
        user_preference = data.get('preference', '')
        product_type = data.get('product_type', 'phone')  # 默认为手机推荐
        
        # 标准化产品类型
        if product_type not in ['phone', 'laptop']:
            product_type = 'phone'
            
        # 检查用户偏好是否为空
        if not user_preference:
            logger.error("请输入您的需求")
            return jsonify({'error': '请输入您的需求'}), 400
            
        # 构建系统提示词
        system_prompt = app.config['RECOMMENDATION_SYSTEM_PROMPT']
        
        # 确保系统提示词包含要求返回规范格式的指令
        if "以规范格式返回" not in system_prompt:
            system_prompt += (
                "\n\n重要提示：请按照以下格式返回推荐结果:"
                "\n1. 每个推荐产品单独编号"
                "\n2. 每款产品包含以下参数: 产品型号, 价格区间, 处理器, 显卡, 内存, 存储, 屏幕, 电池, 重量, 适用人群"
                "\n3. 最后提供选购建议"
            )
        
        # 构建请求头
        headers = {
            'Authorization': f"Bearer {app.config['DEEPSEEK_API_KEY']}",
            'Content-Type': 'application/json'
        }
        
        # 构建请求载荷
        payload = {
            "model": app.config['DEEPSEEK_MODEL'],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请根据以上要求为我推荐{product_type}，我的需求是：{user_preference}"}
            ],
            "stream": False
        }
        
        # 发送API请求
        response = requests.post(
            app.config['DEEPSEEK_API_URL'],
            headers=headers,
            json=payload,
            timeout=60
        )
        
        # 处理API响应
        if response.status_code == 200:
            response_data = response.json()
            if 'choices' in response_data and response_data['choices']:
                ai_response = response_data['choices'][0].get('message', {}).get('content', '')
                
                if ai_response:
                    # 尝试解析为结构化的推荐数据
                    intro, structured_response = parse_recommendations(ai_response)
                    
                    if structured_response and 'recommendations' in structured_response:
                        logger.debug("成功解析推荐结果为结构化数据")
                        # 添加产品类型信息
                        structured_response['product_type'] = product_type
                        return jsonify(structured_response)
                    else:
                        logger.warning("无法解析推荐结果，返回原始文本")
                        return jsonify({"message": ai_response})
                else:
                    logger.error("AI返回了空内容")
                    return jsonify({'error': 'AI返回了空内容'}), 500
            else:
                logger.error(f"AI返回数据格式不正确: {response_data}")
                return jsonify({'error': 'AI返回数据格式不正确'}), 500
        else:
            error_text = response.text
            logger.error(f"API调用失败: {response.status_code} - {error_text}")
            return jsonify({'error': f'API调用失败: {response.status_code} - {error_text}'}), response.status_code
            
    except Exception as e:
        logger.error(f"服务器错误: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

# ===== 设备评分功能 =====
@app.route('/analysis', methods=['GET', 'POST'])
def analysis():
    """设备评分页面"""
    if request.method == 'POST':
        device = request.form.get('device')
        if device:
            # 评分提示词
            prompt = f"""
            你是一个专业的电子产品评测专家。请对以下设备进行专业、全面的评分：
            设备名称: {device}
            
            评分要求:
            1. 提供以下6个维度的评分（10分制，保留1位小数）：
               - 处理器性能
               - 电池续航
               - 屏幕显示
               - 摄像头质量
               - 系统流畅度
               - 性价比
            
            2. 最后给出一个总体评分（10分制，保留1位小数）
            
            3. 评分格式要求（严格按照此格式输出）：
               处理器性能: X.X分
               电池续航: X.X分
               屏幕显示: X.X分
               摄像头质量: X.X分
               系统流畅度: X.X分
               性价比: X.X分
               总评: X.X分
            
            4. 简要说明每个评分原因（100字以内，性价比部分在150字左右，总评在250字左右，并且写明价格，对于电脑的评分，可以对特定方面如：摄像头质量等方面相对降低评分标准）
            """
            
            # 调用DeepSeek API
            response = openai_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个专业电子设备评测专家"},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            
            # 处理API响应
            ai_response = response.choices[0].message.content
            
            # 使用正则表达式提取评分
            scores = {
                "处理器性能": re.search(r"处理器性能: (\d+\.\d+)分", ai_response).group(1) if re.search(r"处理器性能: (\d+\.\d+)分", ai_response) else "N/A",
                "电池续航": re.search(r"电池续航: (\d+\.\d+)分", ai_response).group(1) if re.search(r"电池续航: (\d+\.\d+)分", ai_response) else "N/A",
                "屏幕显示": re.search(r"屏幕显示: (\d+\.\d+)分", ai_response).group(1) if re.search(r"屏幕显示: (\d+\.\d+)分", ai_response) else "N/A",
                "摄像头质量": re.search(r"摄像头质量: (\d+\.\d+)分", ai_response).group(1) if re.search(r"摄像头质量: (\d+\.\d+)分", ai_response) else "N/A",
                "系统流畅度": re.search(r"系统流畅度: (\d+\.\d+)分", ai_response).group(1) if re.search(r"系统流畅度: (\d+\.\d+)分", ai_response) else "N/A",
                "性价比": re.search(r"性价比: (\d+\.\d+)分", ai_response).group(1) if re.search(r"性价比: (\d+\.\d+)分", ai_response) else "N/A",
                "总评": re.search(r"总评: (\d+\.\d+)分", ai_response).group(1) if re.search(r"总评: (\d+\.\d+)分", ai_response) else "N/A"
            }
            
            return render_template('analysis.html', device=device, scores=scores, ai_response=ai_response)
    
    return render_template('analysis.html')

# ===== 主页路由 =====
@app.route('/')
def index():
    """主页面，提供功能导航"""
    return render_template('index.html')
@app.route('/introduction')
def introduction():
    """产品介绍页面"""
    return render_template('introduction.html')

# 应用入口点
# 添加在文件末尾
if __name__ == '__main__':
    # 判断是否在打包环境中运行
    if getattr(sys, 'frozen', False):
        # 如果是打包环境，设置模板和静态文件路径
        template_dir = os.path.join(sys._MEIPASS, 'templates')
        static_dir = os.path.join(sys._MEIPASS, 'static')
        app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.run(debug=True)