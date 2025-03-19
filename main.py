import queue
import requests
import os
from bs4 import BeautifulSoup, Comment
from fake_useragent import UserAgent
import random
from playwright.sync_api import sync_playwright
from readability import Document
import re
from urllib.parse import urljoin  # 新增导入
import time
import logging
from urllib.robotparser import RobotFileParser
import concurrent.futures
from queue import Queue
from hashlib import md5
from urllib.parse import urlparse
import textwrap
import extract_url
from readability.debug import text_content
COUNT= 0
root_path = os.path.abspath(os.path.dirname(__file__))  # 获取脚本所在目录的绝对路径
output_path = os.path.join(root_path, "output.md")      # 拼接根目录下的目标路径
MAX_WORKERS = 15  # 并发线程数（建议3-5）
REQUEST_INTERVAL = (1, 3)  # 请求间隔秒数（随机范围）
MAX_RETRIES = 1          # 最大重试次数
MIN_QUALITY_SCORE = 10  # 最低质量分数
BASE_WAIT_TIME = 2       # 基础等待时间（秒）
# 配置文件头新增
CONTENT_PREVIEW_LENGTH = 200  # 结果预览长度
MAX_DISPLAY_IMAGES = 3        # 最大显示图片数
PROXY_POOL = os.getenv('CRAWLER_PROXIES', '').split(',')  # 从环境变量读取
# 代理IP池（示例，需替换为实际可用的代理）
# PROXY_POOL = [
#     "http://proxy1.example.com:8080",
#     "http://proxy2.example.com:8080",
#     "http://proxy3.example.com:8080"
# ]
# 在文件开头添加日志模块

# 初始化日志配置
logging.basicConfig(
    filename='crawler.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def extract_images(html, base_url):  # 新增图片提取函数
    """从HTML中提取图片链接"""
    soup = BeautifulSoup(html, 'lxml')
    images = set()

    # 查找所有img标签
    for img in soup.find_all('img', src=True):
        src = img['src'].strip()
        # 过滤数据URI和空链接
        if src and not src.startswith('data:image'):
            # 转换相对路径为绝对路径
            absolute_url = urljoin(base_url, src)
            images.add(absolute_url)

    return list(images)

# def generate_headers():
#     """生成随机请求头"""
#     ua = UserAgent()
#     return {
#         "User-Agent": ua.random,
#         "Accept-Language": "zh-CN,zh;q=0.9",
#         "Host": "baijiahao.baidu.com",
#         "Referer": "https://www.baidu.com/",
#         "Alt-Used": "baijiahao.baidu.com"
#     }
def generate_headers():
    """生成视频网站专用请求头"""
    device_id = f"{random.randint(10000000,99999999)}-{os.urandom(8).hex()}"  # 生成设备指纹
    return {
        "User-Agent": generate_realistic_ua(),
        "X-Requested-With": "XMLHttpRequest",  # 关键头
        "X-Client-FlowID": device_id,  # 匹配设备指纹
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors", 
        "Sec-Fetch-Site": "same-origin",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        # 新增视频播放专用头
        "X-Player-Version": "3.2.1",
        "X-Device-Info": f"platform=web;device_id={device_id}"
    }

# 在generate_headers函数之后添加（约第95行后）
def generate_realistic_ua():
    """生成更真实的User-Agent"""
    platforms = [
          ('Windows NT 10.0; Win64; x64', 'Win64'),
        ('Macintosh; Intel Mac OS X 10_15_7', 'MacIntel'),
        ('X11; Linux x86_64', 'Linux x86_64')
    ]
    chrome_version = f"{random.randint(90,125)}.0.{random.randint(1000,9999)}.{random.randint(0,99)}"
    # os_info = random.choice(platforms)
    # chrome_versions = [
    #     f'Chrome/{random.randint(90,125)}.0.{random.randint(1000,9999)}.{random.randint(10,999)}',
    #     f'Edg/{random.randint(90,125)}.0.{random.randint(1000,9999)}.0',
    #     f'Firefox/{random.randint(90, 125)}.0'  # 新增Firefox
    # ]
    return {
        "user-agent": f"Mozilla/5.0 ({platforms[0]}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36",
        "sec-ch-ua-platform": platforms[1],
        "sec-ch-ua": f'"Chromium";v="{chrome_version}", "Google Chrome";v="{chrome_version}", "Not-A.Brand";v="24"'
    }
    # return f"Mozilla/5.0 ({os_info[1]}) AppleWebKit/537.36 (KHTML, like Gecko) {random.choice(chrome_versions)} Safari/537.36"


def clean_html(content):
    """清理HTML中的无关内容"""
    # 移除注释
    for comment in content.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    dynamic_selectors = [
        'div[data-refresh]',  # 带刷新属性的元素
        'div[data-update-time]',  # 带时间戳的元素
        '.live-comment',  # 实时评论
        '[aria-live="polite"]'  # ARIA动态区域
    ]

    for selector in dynamic_selectors:
        for element in content.select(selector):
            element.decompose()

    # 移除脚本和样式
    for tag in ['script', 'style', 'no script', 'iframe', 'button', 'svg']:
        for element in content.find_all(tag):
            element.decompose()

    # 移除空白标签
    for tag in content.find_all():
        if len(tag.get_text(strip=True)) == 0:
            tag.decompose()

    return content

def clean_text(text):
    """综合文本清理函数"""
    # 1. 合并连续换行
    text = re.sub(r'\n{3,}', '\n\n', text)  # 保留最多2个换行
    # 2. 移除首尾空白
    text = text.strip()
    # 3. 移除多余空格
    text = re.sub(r'[ \t]+', ' ', text)
    # 4. 处理特殊空行
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text


from readability import Document


def extract_content(html):
    """综合内容提取（结合Readability和自定义策略）"""
    result = {'title': '', 'body': ''}
    soup = BeautifulSoup(html, 'lxml')

    # 第一阶段：使用Readability提取内容
    readability_body = ""
    try:
        doc = Document(html)
        readability_html = doc.summary()
        readability_soup = BeautifulSoup(readability_html, 'lxml')
        readability_body = clean_text(readability_soup.get_text('\n', strip=True))
        readability_title = doc.title()
    except Exception as e:
        readability_body = ""
        readability_title = ""
        logging.debug(f"Readability解析失败: {str(e)}")

    # 第二阶段：自定义标题提取
    title_sources = [
        ('meta[property="og:title"]', 'content'),
        ('meta[name="twitter:title"]', 'content'),
        ('title', 'text'),
        ('h1', 'text'),
        ('div.article-title', 'text'),
        ('header h1', 'text'),
    ]

    custom_title = ""
    for selector, attr in title_sources:
        if tag := soup.select_one(selector):
            if title := tag.get(attr, '').strip():
                custom_title = title
                break

    # 标题择优策略
    result['title'] = custom_title or readability_title or "无标题"
    result['title'] = result['title'][:100].strip()  # 限制标题长度

    # 第三阶段：内容提取策略
    content_strategies = [
        ('article', 'all'),
        ('div.article-content', 'all'),
        ('div.content, main', 'text'),
        ('div#content', 'text'),
        ('body', 'smart'),
        ('div.post-content', 'all'),
        ('div.entry-content', 'all'),
    ]

    # 自定义提取结果
    best_custom = {'body': '', 'score': 0}
    for selector, mode in content_strategies:
        text = ""
        if content := soup.select_one(selector):
            try:
                if mode == 'all':
                    text = content.get_text('\n', strip=True)
                elif mode == 'text':
                    text = '\n'.join([p.get_text() for p in content.find_all(['p', 'div'])])
                elif mode == 'smart':
                    text = smart_text_extract(content)

                current_score = content_quality_score({'text': text})
                if current_score > best_custom['score']:
                    best_custom = {'body': text, 'score': current_score}
            except Exception as e:
                logging.debug(f"选择器 {selector} 提取失败: {str(e)}")

    # 第四阶段：结果择优
    readability_score = content_quality_score({'text': readability_body})
    final_content = ""

    # 评分比较策略（增加10%偏重）
    if readability_score * 1.1 > best_custom['score']:
        final_content = readability_body
    else:
        final_content = best_custom['body']

    # 最终清理和验证
    final_content = clean_text(final_content)
    if not validate_content(final_content):
        final_content = best_custom['body'] or readability_body  # 双重回退
    min_acceptable_score = max(MIN_QUALITY_SCORE, 20)  # 设置安全阈值
    result['body'] = final_content if content_quality_score({'text': final_content}) >= MIN_QUALITY_SCORE  else ""

    # 增加最低保障
    if not result['body'] and len(final_content) > 80:
        result['body'] = final_content[:2000] + "...[内容质量评分不足，已提供预览]"

    return result

def smart_text_extract(element):
    """智能文本提取（严格模式）"""
    # 保留现有清理逻辑
    for tag in element(
            ['script', 'style', 'nav', 'footer', 'aside', 'nav', 'header', 'noscript', '.ad-box', '.comment-area',
             '.related-news']):
        tag.decompose()

    # 严格段落过滤
    paragraphs = []
    seen_lines = set()  # 段落级去重
    min_length = 15  # 提高最小段落长度

    for node in element.find_all(['p', 'div']):
        text = node.get_text(' ', strip=True)
        # 双重验证：长度+重复性+结构验证
        if (len(text) > min_length
                and text not in seen_lines
                and len(re.findall(r'[\u4e00-\u9fa5]', text)) > min_length * 0.4):
            seen_lines.add(text)
            paragraphs.append(text)

    return '\n\n'.join(paragraphs[:30])  # 限制最大段落数


def validate_content(text, min_length=100):
    if len(text) < min_length:
        return False
    zh_chars = len(re.findall(r'[\u4e00-\u9fa5]', text))
    # 允许纯数字/英文内容并降低中文比例要求
    return (zh_chars / len(text) > 0.1) or (len(re.findall(r'\w+', text)) > 20)



def is_crawlable(url):
    """判断网页是否可爬取"""
    try:
        # 1. 检查robots.txt
        rp = RobotFileParser()
        rp.set_url(urljoin(url, "/robots.txt"))
        rp.read()
        if not rp.can_fetch("*", url):
            return False

        # 2. HEAD请求预检查
        response = requests.head(url,
            headers=generate_headers(),
            proxies={"http": random.choice(PROXY_POOL)} if PROXY_POOL else None,
            timeout=10
        )
        if response.status_code not in [200, 301, 302]:
            return False

        # 3. 内容类型检查
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' not in content_type:
            return False

        return True
    except Exception as e:
        logging.warning(f"Can't crawl {url}: {str(e)}")
        return False


# 通用弹窗处理策略
def handle_popups(page):
    # 自动关闭弹窗
    page.on("dialog", lambda dialog: dialog.dismiss())

    # 移除常见弹窗元素
    popup_selectors = [
        'div[class*="modal"]',
        'div[class*="popup"]',
        'div[class*="cookie"]',
        'div[id^="pop"]',
        'div[aria-modal="true"]',
        'div[class*="ad"]',  # 新增
        'div[class*="banner"]'  # 新增
    ]

    try:
        page.evaluate(f"""() => {{
            document.querySelectorAll('{",".join(popup_selectors)}')
                .forEach(el => el.remove());
        }}""")
    except Exception as e:
        logging.debug(f"弹窗清理异常: {str(e)}")
    # try:
    #     page.evaluate("""() => {
    #         window.__NUXT__ = {state: {user: {isLogin: true}}};  // 伪登录态
    #         window._playerConfig = {debug: false}; 
    #     }""")
    # except:
    #     pass
    # 点击关闭按钮
    close_buttons = [
        'button.close',
        '.modal-close',
        '[aria-label="关闭"]'
    ]
    for btn in close_buttons:
        try:
            page.click(btn, timeout=1000)
        except:
            pass

# 在handle_popups函数之后添加（约第234行后）
def simulate_human_behavior(page):
    """模拟人类操作"""
    # 随机鼠标移动
    page.mouse.move(
        random.randint(0, 1000),
        random.randint(0, 400)
    )
    # 随机滚动
    page.evaluate("""() => {
        window.scrollBy(0, document.body.scrollHeight * Math.random());
        setTimeout(() => {
            window.scrollBy(0, document.body.scrollHeight * 0.5);
        }, 1000 + Math.random()*500);
    }""")
    # 随机停留
    time.sleep(random.uniform(1.2, 3.5))
def wait_for_stable_content(page):
    """等待视频相关动态内容稳定"""
    page.evaluate("""
    () => {
        const observer = new MutationObserver(() => {});
        observer.observe(document.querySelector('video'), {
            subtree: true,
            childList: true,
            attributes: true
        });
        return new Promise(resolve => setTimeout(resolve, 1500));
    }
    """)

def get_content(url, proxy=None, COUNT=COUNT):
    try:
        with sync_playwright() as p:
            headers = generate_headers()
            proxy = proxy or random.choice(PROXY_POOL)
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--autoplay-policy=document-user-activation-required",  # 禁用自动播放
                    "--single-process",  # 新增单进程模式
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",  # 关闭安全特性
                    "--disable-dev-shm-usage",
                    f"--user-agent={generate_realistic_ua()}",
                    f"--window-size={random.randint(1200, 1400)},{random.randint(800, 900)}",
                    "--disable-web-security",
                    "--disable-notifications",
                    "--disable-automation-extension",  # 新增关键参数
                    "--disable-component-update",
                    "--enable-automation",   
                    "--no-sandbox"
                ],
                ignore_default_args=["--disable-component-update"],
                chromium_sandbox=False
            )
            context = browser.new_context(
                locale='zh-CN',
                timezone_id="Asia/Shanghai",
                permissions=[],
                java_script_enabled=True,
                bypass_csp=False,
                ignore_https_errors=False,
                color_scheme='light',
                reduced_motion='reduce',
                extra_http_headers={
                    'Connection': 'keep-alive',
                    'Accept-Encoding': 'gzip, deflate'
                }
            )
            page = context.new_page()
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });
                window.chrome = {runtime: {}};
            """)
            # 在page.goto之前执行（约第230行）
            page.add_init_script("""
            Object.defineProperty(HTMLVideoElement.prototype, 'play', {
            value: () => Promise.resolve(),
            writable: false
            });
            """)
            page.on("dialog", lambda dialog: dialog.dismiss())
            page.goto(url, timeout=30000, wait_until="domcontentloaded")#load
           # 修改后的代码（约第230行）
            page.evaluate("""() => {
                try {
                    // 仅当webdriver存在时重新定义
                    if (navigator.webdriver !== undefined) {
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => false,
                            configurable: true  // 允许重新配置
                        });
                    }
                    
                    // 补充其他需要覆盖的属性
                    const originalPlugins = navigator.plugins;
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1,2,3],
                        configurable: true
                    });
                } catch(e) {
                    console.log('环境注入安全异常:', e);
                }
            }""")
            handle_popups(page)
            simulate_human_behavior(page)
            #wait_for_stable_content(page)
            # page.wait_for_selector("p, div.paragraph, article, div.content", timeout=15000)
            page.wait_for_function("""() => {

                        const text = document.body.innerText;

                        return text.length > 500 || 

                            document.querySelector('article, .main-content') ||

                            /[\u4e00-\u9fa5]{20}/.test(text);

                    }""", timeout=15000)
            # 新增智能等待策略
            try:
                # 主等待：网络空闲+核心内容加载
                page.wait_for_load_state("networkidle", timeout=15000)
                # 二次验证：确保至少有一个段落加载
                page.wait_for_selector(
                    "p:not(:empty), div.paragraph",
                    state="attached",
                    timeout=10000
                )
            except Exception as e:
                logging.warning(f"等待异常: {str(e)}")
            finally:
                time.sleep(random.uniform(1.2, 2.8))
            html = page.content()
            colors = [
                "\033[31m",  # 红色
                "\033[32m",  # 绿色
                "\033[33m",  # 黄色
                "\033[34m",  # 蓝色
                "\033[35m",  # 紫色
                "\033[36m",  # 青色
                "\033[37m",  # 白色
            ]

            # 复位颜色
            reset = "\033[0m"

            # 定义打印不同颜色的函数
            def print_colored(text):
                color = random.choice(colors)  # 随机选择一种颜色
                print(f"这一个标记{color}{text}{reset}")  # 打印并重置颜色

            print_colored(COUNT)
            COUNT = COUNT + 1
            images = extract_images(html, url)
            content_data = extract_content(html)
            title = content_data.get('title', '无标题')[:30] if isinstance(content_data, dict) else '标题提取失败'
            body = content_data.get('body', '') if isinstance(content_data, dict) else str(content_data)
            return {
                'title': title,
                'text': body,
                'images': images,
                'url': url
            }
    except Exception as e:
        error_msg = f"URL: {url} | 错误类型: {type(e).__name__} | 详细信息: {str(e)}"
        logging.error(error_msg)
        print(f"抓取失败: {error_msg}")
    finally:
        if browser:
            try:
                context.close()  # 先关闭上下文
                # browser.close()  # 再关闭浏览器
            except:
                pass

def is_valid_content(content):
    """多维度验证内容有效性"""
    if not content:
        return False
    text = content.get('text', '')
    images = content.get('images', [])

    # 组合判断条件
    return len(text) >= 100 and \
        "error" not in text.lower()


def content_quality_score(content):
    """内容质量评分（0-100分）"""
    if not content:
        return 0

    text = content.get('text', '')

    score = 0

    # 文本长度评分（占比40%）
    text_length = len(text)
    score += min(text_length / 300 * 60, 60)  # 500字得满分


    # 文本密度评分（占比30%，保留也可）
    text_density = len(text) / (len(text.split()) + 1e-5)
    score += 30 if text_density > 4 else text_density * 7.5

    # 常见扣分项
    if "404" in text or "not found" in text.lower():
        score -= 50
    if any(word in text for word in ["错误", "异常", "无法访问"]):
        score -= 30

    return max(0, min(100, score))



def get_url_fingerprint(url):
    """生成URL唯一指纹"""
    parsed = urlparse(url)
    # 标准化URL（忽略协议、参数顺序等）
    core_url = f"{parsed.netloc}{parsed.path}".lower()
    return md5(core_url.encode()).hexdigest()


def crawl_task(url_queue, result_queue):
    processed = set()
    while True:
        try:
            # 阻塞式获取任务，1秒超时退出
            url = url_queue.get(block=True, timeout=1)
            if (fp := get_url_fingerprint(url)) in processed:
                continue
            processed.add(fp)

            # 重试逻辑
            for attempt in range(MAX_RETRIES + 1):
                content = get_content(url)
                if not isinstance(content, dict):
                            content = {'title': '', 'text': '', 'images': [], 'url': url}
                if content and is_valid_content(content):
                    if isinstance(content, dict) and content.get('text'):
                        result_queue.put(content)
                    break
                time.sleep(BASE_WAIT_TIME ** attempt)

            url_queue.task_done()  # 必须调用task_done
        except queue.Empty:
            break
        except Exception as e:
            logging.error(f"任务异常: {str(e)}")


from simhash import Simhash


def rear_text(text: str)->str:
    if not text:
        return ""  # 防止空内容处理异常
    replacements = {
        r'\t': '\t',  # 保留制表符
        r'\n': '\n',  # 保留换行符
        r'\r': '\r',  # 保留回车符
        r'\\': '\\',  # 保留单个反斜杠
    }
    for k, v in replacements.items():
        text = text.replace(k, v)

    # 清理控制字符（保留\t\n\r）
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

    # 合并连续空白（保留全角空格）
    text = re.sub(r'[ \u3000]+', ' ', text)  # 所有空格类字符转普通空格
    text = re.sub(r'\n{3,}', '\n\n', text)  # 最多保留两个换行

    # 智能间距处理
    text = re.sub(r'([\u4e00-\u9fff])([A-Za-z])', r'\1 \2', text)  # 中+英
    text = re.sub(r'([A-Za-z])([\u4e00-\u9fff])', r'\1 \2', text)  # 英+中

    # 清理标点后的多余空格
    text = re.sub(r'([。！？，；：])\s+', r'\1', text)

    # 保留合理段落结构
    text = re.sub(r'\n\s+', '\n', text)  # 清理行首空白
    text = text.strip()
    text= textwrap.fill(text, width=100)
    return text
    # return text


# 使用示例
if __name__ == "__main__":
    start_time = time.time()
    target_urls = []
    target_urls_sets,target_urls_sets_title = extract_url.urls_extract()
    # target_urls = [
    #     "https://baijiahao.baidu.com/s?id=1826651380645949331&wfr=spider&for=pc",
    #     "https://www.serversan.net.cn/wenda/202503-234.html",
    #     "https://www.news.cn/world/20250316/ccc6463c31504c1084a04727c18007ef/c.html",
    #     "https://www.oschina.net/news/291284",
    #     "https://top.baidu.com/board?tab=realtime"
    #     ,"https://www.news.cn/world/20250316/ba5233a3ebbf444dab2351bd11fd40a6/c.html"
    # ]
    for url in target_urls_sets.keys():
        target_urls.append(url)


    # 初始化队列（关键修正点）
    unique_urls = list(set(target_urls))
    url_queue = Queue()
    [url_queue.put(url) for url in unique_urls]  # 去重后填充
    result_queue = Queue()
    print(f"开始到初始化队列总耗时：{time.time() - start_time:.2f}秒，{(time.time()-start_time) / 60:.2f}分钟")
    # 保留原有的重试机制（整合到线程中）
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 启动所有工作线程
        futures = [executor.submit(crawl_task, url_queue, result_queue)
                   for _ in range(MAX_WORKERS)]

        # 等待所有任务完成（保持并发执行）
        concurrent.futures.wait(futures)

    # 保留原有的结果处理逻辑（增强版）
    success_count = 0
    seen_urls = set()
    print(f"开始到并发抓取网页结束总耗时：{time.time() - start_time:.2f}秒，{(time.time()-start_time) / 60:.2f}分钟")
    total_content= []
    while not result_queue.empty():
        while_time = time.time()
        try:
            content = result_queue.get()
            if content['url'] in seen_urls:
                continue
            seen_urls.add(content['url'])
            retry_count = 0  # 每个内容的独立重试计数器
            while retry_count < MAX_RETRIES:
                quality = content_quality_score(content)
                print(f"\033[31m本次内容质量评分：{quality}/100\033[0m")
                if quality > MIN_QUALITY_SCORE:
                    # 保留原有的成功处理逻辑
                    text_content = rear_text(content['text'])
                    if target_urls_sets[content["url"]] is not None:
                        title = target_urls_sets[content["url"]]#需要优化的地方
                    else:
                        title = content['title']
                    print(f"Title：{title}")
                    print(f"URL：{content['url']}")
                    #print(text_content[:CONTENT_PREVIEW_LENGTH])
                    print(f"Contents(retry_count)：{retry_count}）:\n{text_content}")
                    # 显示前200字符
                    print("相关图片：", content['images'][:3])
                    total_content.append(f"Title:{title}\n\nURL:{content['url']}\n\nContents:{text_content}\n\n")
                    success_count += 1
                    break

                # 保留原有的重试逻辑（增强版）
                wait_time = BASE_WAIT_TIME ** retry_count + random.uniform(0, 1)
                print(f"质量不足，第{retry_count + 1}次重试...等待{wait_time:.1f}秒")
                time.sleep(wait_time)
                retry_count += 1
                
                # 新增重试时的内容更新逻辑
                new_content = get_content(content['url'])  # 需要记录原始URL
                if new_content:
                    content = new_content

        except queue.Empty:
            break
        
        print(f"一次循环耗时：{time.time() - while_time:.2f}秒，{(time.time()-while_time) / 60:.2f}分钟")
    # 保留最终状态输出
    with open(output_path, "w", encoding="utf-8") as f:
                        print("保存文件中.....")
                        for line in total_content:
                            f.write(line)
    print(f"\n最终结果：成功获取 {success_count}/{len(target_urls)} 条有效内容")
    print(f"清洗处理文本循环总耗时：{time.time() - while_time:.2f}秒，{(time.time()-while_time) / 60:.2f}分钟")
    print(f"总耗时：{time.time() - start_time:.2f}秒，{(time.time()-start_time) / 60:.2f}分钟")













