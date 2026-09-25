"""
Detailed inspection of NBS CPI and GDP catalog pages.
"""
from lxml import html
import re

def inspect_cpi():
    print("=== NBS CPI CATALOG ===")
    path = r"C:\Users\DELL\.gemini\antigravity-ide\brain\e0ff0509-ed67-442c-a004-21babebfaad4\scratch\nbs_cpi_catalog.html"
    doc = html.parse(path)
    root = doc.getroot()

    # Look for table rows or resource container
    for tr in root.xpath("//tr")[:6]:
        tds = tr.xpath(".//td | .//th")
        texts = [" ".join(td.text_content().split()) for td in tds]
        links = [a.get("href") for a in tr.xpath(".//a")]
        print(f"ROW: {texts} | LINKS: {links}")

def inspect_gdp():
    print("\n=== NBS GDP CATALOG ===")
    path = r"C:\Users\DELL\.gemini\antigravity-ide\brain\e0ff0509-ed67-442c-a004-21babebfaad4\scratch\nbs_gdp_catalog.html"
    doc = html.parse(path)
    root = doc.getroot()
    for tr in root.xpath("//tr")[:12]:
        tds = tr.xpath(".//td | .//th")
        texts = [" ".join(td.text_content().split()) for td in tds]
        links = [a.get("href") for a in tr.xpath(".//a")]
        print(f"ROW: {texts} | LINKS: {links}")

if __name__ == "__main__":
    inspect_cpi()
    inspect_gdp()
