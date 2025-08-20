import threading
import time
import webbrowser
from app import app  # 导入你的Flask应用

def open_browser():
    """在应用启动后打开浏览器"""
    time.sleep(1.5)  # 等待应用启动
    webbrowser.open('http://127.0.0.1:5000/')

if __name__ == '__main__':
    # 在独立线程中打开浏览器
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    # 启动Flask应用
    app.run(debug=False, use_reloader=False)