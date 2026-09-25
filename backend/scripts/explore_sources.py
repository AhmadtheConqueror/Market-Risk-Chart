"""
Exploration script for official macro data sources using lxml and requests/urllib.
"""
import ssl
import urllib.request
import re
from lxml import html as lxml_html

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_html(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

def explore_cpi():
    print("\n--- Exploring NBS CPI ---")
    url = "https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials"
    content = fetch_html(url)
    if not content:
        return
    tree = lxml_html.fromstring(content)
    # Search table rows or download links
    for a in tree.xpath("//a"):
        href = a.get("href", "")
        text = (a.text_content() or "").strip()
        parent_text = (a.getparent().text_content() or "").strip() if a.getparent() is not None else ""
        if any(w in text.lower() or w in href.lower() or w in parent_text.lower() for w in ["cpi", "inflation", "august", "2026", "zip", "download", "xlsx"]):
            print(f"CPI match: text='{text[:60]}' | parent='{parent_text[:80]}' | href='{href}'")

def explore_gdp():
    print("\n--- Exploring NBS GDP ---")
    url = "https://microdata.nigerianstat.gov.ng/index.php/catalog/147/related-materials"
    content = fetch_html(url)
    if not content:
        return
    tree = lxml_html.fromstring(content)
    for a in tree.xpath("//a"):
        href = a.get("href", "")
        text = (a.text_content() or "").strip()
        parent_text = (a.getparent().text_content() or "").strip() if a.getparent() is not None else ""
        if any(w in text.lower() or w in href.lower() or w in parent_text.lower() for w in ["gdp", "q2", "q1", "2026", "zip", "download", "xlsx"]):
            print(f"GDP match: text='{text[:60]}' | parent='{parent_text[:80]}' | href='{href}'")

def explore_nuprc():
    print("\n--- Exploring NUPRC ---")
    for url in [
        "https://www.nuprc.gov.ng/oil-production-status-report/",
        "https://www.nuprc.gov.ng/category/oil-production/",
        "https://www.nuprc.gov.ng/"
    ]:
        print(f"Checking {url}")
        content = fetch_html(url)
        if content:
            tree = lxml_html.fromstring(content)
            for a in tree.xpath("//a"):
                href = a.get("href", "")
                text = (a.text_content() or "").strip()
                if any(w in text.lower() or w in href.lower() for w in ["crude", "oil production", "condensate", "status report", "august 2026", "2026"]):
                    print(f"NUPRC match: text='{text}' | href='{href}'")

def explore_pmi():
    print("\n--- Exploring PMI ---")
    for url in [
        "https://www.pmi.spglobal.com/Public/Home/PressRelease/Index?language=en",
        "https://www.pmi.spglobal.com/Public/Release/PressReleases"
    ]:
        print(f"Checking {url}")
        content = fetch_html(url)
        if content:
            tree = lxml_html.fromstring(content)
            for a in tree.xpath("//a"):
                href = a.get("href", "")
                text = (a.text_content() or "").strip()
                if "nigeria" in text.lower() or "nigeria" in href.lower():
                    print(f"PMI match: text='{text}' | href='{href}'")

if __name__ == "__main__":
    explore_cpi()
    explore_gdp()
    explore_nuprc()
    explore_pmi()
