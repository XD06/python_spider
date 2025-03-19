import json

import requests
from concurrent.futures  import ThreadPoolExecutor, as_completed 
from urllib.parse  import urljoin
import ai

ai_historys=[]
with open('url.json', 'r', encoding='utf-8') as file:
    url_c = json.load(file)
KEY_HOT = {"1":{
    "36kr": "/36kr",
    "51cto": "/51cto",
    "52pojie": "/52pojie",
    "acfun": "/acfun",
    "baidu": "/baidu",
    "bilibili": "/bilibili",
    "coolapk": "/coolapk",
    "csdn": "/csdn"
},"2":{
    "dgtle": "/dgtle",
    "douban-group": "/douban-group",
    "douban-movie": "/douban-movie",
    "douyin": "/douyin",
    "earthquake": "/earthquake",
    "geekpark": "/geekpark",
    "genshin": "/genshin",
    "guokr": "/guokr"}, "3":{

    "hellogithub": "/hellogithub",
    "history": "/history",
    "honkai": "/honkai",
    "hostloc": "/hostloc",
    "hupu": "/hupu",
    "huxiu": "/huxiu"
    }, "4":{
    "ifanr": "/ifanr",
    "ithome-xijiayi": "/ithome-xijiayi",
    "ithome": "/ithome",
    "jianshu": "/jianshu",
    "juejin": "/juejin",
    "kuaishou": "/kuaishou",
    "lol": "/lol"
    }, "5":{
    "miyoushe": "/miyoushe",
    "netease-news": "/netease-news",
    "ngabbs": "/ngabbs",
    "nodeseek": "/nodeseek",
    "nytimes": "/nytimes",
    "qq-news": "/qq-news",
    "sina-news": "/sina-news",
    "sina": "/sina"},
    "6":{
    "smzdm": "/smzdm",
    "sspai": "/sspai",
    "starrail": "/starrail",
    "thepaper": "/thepaper",
    "tieba": "/tieba",
    "toutiao": "/toutiao",
    "v2ex": "/v2ex"}, "7":{
    "weatheralarm": "/weatheralarm",
    "weibo": "/weibo",
    "weread": "/weread",
    "yystv": "/yystv",
    "zhihu-daily": "/zhihu-daily",
    "zhihu": "/zhihu"
}
}

 
# 基础检测函数 
def check_url(path, base_url="https://bt.dskblog.top",  timeout=3):
    """检测单个链接的可用性"""
    full_url = urljoin(base_url, path)
    try:
        response = requests.head(full_url,  timeout=timeout, allow_redirects=True)
        return full_url, response.status_code  
    except Exception as e:
        return full_url, f"Error: {str(e)}"
 
# 批量检测主函数 
def batch_check_urls(url_paths, max_workers=20, verbose=True):
    """
    执行批量检测 
    :param url_paths: 路径列表 如 ["/36kr", "/baidu"]
    :param max_workers: 最大并发数 
    :param verbose: 是否显示检测过程 
    :return: (成功列表, 失败列表)
    """
    success, failed = [], []
    total = len(url_paths)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_url,  path): path for path in url_paths}
        
        for i, future in enumerate(as_completed(futures), 1):
            url, status = future.result() 
            if isinstance(status, int) and 200 <= status < 400:
                success.append((url,  status))
                if verbose:
                    print(f"\033[32m[#{i}/{total}] {url} 可用 (状态码: {status})\033[0m")
            else:
                failed.append((url,  status))
                if verbose:
                    print(f"\033[31m[#{i}/{total}] {url} 异常 - {status}\033[0m")
    
    if verbose:
        print(f"\n检测完成！成功 {len(success)} 条，失败 {len(failed)} 条")
        print(f"成功率: {len(success)/total:.2%}")
    
    return success, failed 
def rear_check():
    ss_list = []
    ff_list = []
    all_paths = [p for group in KEY_HOT.values()  for p in group.values()] 
    
    # 步骤二：执行检测（可调节参数）
    success_list, failed_list = batch_check_urls(
        url_paths=all_paths,
        max_workers=15,    # 根据网络状况调整 
        verbose=True,       # 关闭可提升性能 
    )
    # 步骤三：结果处理示例 
    print("再次检验错误的url：")
    for url, err in failed_list:
       url,code=check_url(url)
       if code==200:
           try:
               success_list.append((url,code))
               failed_list.remove((url,code))
           except:
                pass
       else:
        print(f"{url} - {code}")
    for succ in success_list:
        ss_list.append(succ[0])
    for fail in failed_list:
        ff_list.append(fail[0])
    #print(ss_list)
    #print(ff_list)
    return ss_list,ff_list

def data_clear_save(p_string):
    cleaned_data = p_string.strip().replace('```json', '').replace('```', '').strip()

    # 步骤2：转换字典
    try:
        parsed_dict = json.loads(cleaned_data)
    except Exception as e:
        print(f"数据格式错误：{e}")
        exit()

    # 步骤3：写入文件
    with open("usable_url.json", "w", encoding="utf-8") as f:
        json.dump(parsed_dict, f, ensure_ascii=False, indent=2)

    print("✅ 文件生成成功：usable_url.json")

if __name__ == "__main__":
    s_list,f_list=rear_check()
    ai_responses,ai_historys= ai.ai_api(url_c["url_classify"]+str(s_list))
    data_clear_save(ai_responses)
    # print(s_list[0][0])
    # for i in s_list:
    #     print(f"{i}")
    # for n in f_list:
    #     print(f"{n}")