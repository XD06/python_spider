import requests
import json

url = "https://google.serper.dev/news"

payload = json.dumps({
  "q": "最新政策",
  "gl": "cn",
  "hl": "zh-cn",
   "tbs": "qdr:w"
})
headers = {
  'X-API-KEY': '55c9e21dab8255e5f6b27608d10ca25c8da78e40',
  'Content-Type': 'application/json'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)

