import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json

def urls_extract():
    # 创建可复用的Session对象（自动保持TCP连接）
    session = requests.Session()
    url_sets = {}
    # 配置重试策略（避免网络波动影响）
    retries = Retry(
        total=3,  # 最大重试次数
        backoff_factor=0.3,  # 重试等待时间：0.3s, 0.6s, 1.2s
        status_forcelist=[500, 502, 503, 504]
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))

    # 浏览器级请求头（避免被识别为爬虫）
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    }

    url = "https://bt.dskblog.top/qq-news"

    try:
        # 添加超时参数（连接5s，读取10s）

        response = session.get(url, headers=headers, timeout=(5, 10))
        response.raise_for_status()  # 自动检查HTTP错误
        content_json = json.loads(response.text)
        for i in content_json["data"]:
            url_sets[i["url"]] = i["title"]
    except requests.exceptions.RequestException as e:
        print(f"请求失败：{str(e)}")
    return url_sets,content_json['title']