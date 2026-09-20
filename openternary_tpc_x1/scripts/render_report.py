#!/usr/bin/env python3
"""Render the Japanese Markdown report to self-contained, offline HTML."""
from pathlib import Path
import re
import html
import mistune

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / 'REPORT.md').read_text(encoding='utf-8')
markdown = mistune.create_markdown(escape=True, plugins=['table', 'strikethrough', 'url'])
body = markdown(text)
headings = []
def heading(match):
    index = len(headings) + 1
    title = re.sub(r'<[^>]+>', '', match.group(1))
    headings.append((index, title))
    return f'<h2 id="section-{index}">{match.group(1)}</h2>'
body = re.sub(r'<h2>(.*?)</h2>', heading, body, flags=re.S)
links = ''.join(f'<a href="#section-{i}">{html.escape(html.unescape(t))}</a>' for i,t in headings)
css = '''
:root{color-scheme:light}*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:#edf1f5;color:#213143;font-family:system-ui,-apple-system,"Yu Gothic",Meiryo,sans-serif;line-height:1.9}
main{max-width:1110px;margin:32px auto 48px;background:#fff;padding:42px 58px;border-top:7px solid #174f72;box-shadow:0 8px 32px #2233440c}
.label{letter-spacing:.14em;color:#174f72;font-size:.78rem;font-weight:700;margin-bottom:14px}
h1{font-size:2rem;line-height:1.45;margin:.5em 0 1em}h2{margin:2.6rem 0 1rem;border-bottom:2px solid #dce6ed;padding-bottom:.5rem;font-size:1.45rem;scroll-margin-top:18px}
h3{margin-top:1.8rem;font-size:1.15rem}p{margin:1rem 0}strong{color:#12314c}a{color:#175f90;text-underline-offset:3px}
nav{border:1px solid #cfdae3;background:#f4f7fa;padding:16px 20px;margin:20px 0 32px}nav summary{cursor:pointer;font-weight:700}nav .toc{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px 24px;margin-top:12px;font-size:.85rem}nav a{text-decoration:none;padding:2px 0}
.table-wrap{overflow:auto;width:100%;margin:1.3rem 0}table{border-collapse:collapse;min-width:100%;font-size:.92rem}td,th{border:1px solid #d2dde6;padding:10px 13px;text-align:left;vertical-align:top;min-width:100px}th{background:#eff4f8}tr:nth-child(even) td{background:#fafcfd}
pre{padding:16px 20px;background:#f3f6f8;overflow:auto;border:1px solid #dce4eb;line-height:1.65;font-size:.86rem}code{font-family:ui-monospace,Consolas,monospace;overflow-wrap:anywhere}p code,li code,td code{background:#eff3f6;padding:1px 4px;border-radius:3px}blockquote{border-left:4px solid #7696af;padding:1px 20px;margin:1rem 0;background:#f6f8fb}hr{border:0;border-top:3px solid #e5ebf0;margin:3.2rem 0}
footer{max-width:1000px;margin:0 auto 32px;padding:0 20px;color:#627284;font-size:.82rem;text-align:center}
@media(max-width:700px){main{margin:0;padding:24px 18px;box-shadow:none}h1{font-size:1.55rem}h2{font-size:1.28rem}body{font-size:15px}nav .toc{grid-template-columns:1fr}td,th{padding:8px 10px}footer{margin:24px auto}}
@media print{main{margin:0;padding:0;border:0;box-shadow:none}body{background:#fff}nav{display:none}h2,h3{break-after:avoid}tr,pre{break-inside:avoid}a{color:inherit}}
'''
body = body.replace('<table>', '<div class="table-wrap"><table>').replace('</table>', '</table></div>')
page = f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenTernary TPC-X1 — 設計・実装・検証レポート</title><style>{css}</style></head>
<body><main><div class="label">OPENTERNARY / TPC-X1 / RESEARCH &amp; ENGINEERING</div>
<nav aria-label="目次"><details><summary>レポート目次を開く</summary><div class="toc">{links}</div></details></nav>
{body}</main><footer>2026-09-20 • オフライン閲覧用 • 実行記録の正本は reports/results.json と各 raw log • 実機性能は未測定</footer></body></html>'''
(ROOT / 'REPORT.html').write_text(page, encoding='utf-8')
print(f'Rendered {len(headings)} sections; {len(page.encode("utf-8")):,} bytes')
