import urllib.request
import urllib.parse
import json
import re

def search(query):
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        html = urllib.request.urlopen(req).read().decode('utf-8')
        links = re.findall(r'href="([^"]+)" class="result__url"', html)
        return links
    except Exception as e:
        print("Error:", e)
        return []

print("Chiba meibo:", search("千葉県議会 会派等別議員名簿 site:pref.chiba.lg.jp"))
print("Chiba senkyo:", search("千葉県議会議員選挙 令和5年 投開票結果 site:pref.chiba.lg.jp"))
print("Tochigi meibo:", search("栃木県議会 会派別議員名簿 site:pref.tochigi.lg.jp"))
print("Tochigi senkyo:", search("栃木県議会議員選挙 結果 site:pref.tochigi.lg.jp"))
print("Saitama meibo:", search("埼玉県議会 会派別議員名簿 site:pref.saitama.lg.jp"))
print("Saitama senkyo:", search("埼玉県議会議員選挙 結果 site:pref.saitama.lg.jp"))
