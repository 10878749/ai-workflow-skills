"""Build the public static site and reproducible downloads. No private project access required."""
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
VERSION = "0.1.0"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def zip_files(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as output:
        for file, relative in sorted(files, key=lambda item: str(item[1])):
            info = zipfile.ZipInfo(str(relative).replace("\\", "/"), date_time=(2026, 11, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, file.read_bytes())


def case_card(case):
    e = escape
    if case["image"]:
        visual = '<img src="' + case["image"] + '" alt="页间阅读盲盒的保留界面截图" loading="lazy" width="1440" height="1004"><span class="visual-note">项目保留截图 / 2026-09</span>'
    elif case["id"] == "guangying":
        visual = '<div class="evidence-visual"><span class="visual-title">独立 RAG 对照实验 · 保留记录</span><div class="visual-line"><span>开发检索题 Hit@4</span><strong>12 / 12</strong></div><div class="visual-line"><span>真实模型调用</span><strong>0 次</strong></div><span class="visual-caption">软件验证与专业效果分开记录</span></div>'
    else:
        visual = '<div class="evidence-visual"><span class="visual-title">独立编译包 · 保留结果</span><div class="visual-line"><span>构建 / 自检退出码</span><strong>0 / 0</strong></div><div class="visual-line"><span>原核心文件核对</span><strong>173 份未变</strong></div><span class="visual-caption">换路径核验 ≠ 全新虚拟机实测</span></div>'
    return '<article class="case" id="case-' + case["id"] + '"><div class="case-visual">' + visual + '</div><div class="case-meta">' + e(case["name"]) + ' / ' + e(case["label"]) + '</div><h3>' + e(case["title"]) + '</h3><p>' + e(case["intro"]) + '</p><div class="case-footer"><button type="button" class="case-button" data-case="' + case["id"] + '">阅读案例</button><a href="evidence/' + case["id"] + '.html">证据说明</a></div></article>'


def skill_row(skill):
    e = escape
    glyph = {"产品决策": "◇", "工程实施": "⌘", "验证交付": "✓", "工作闭环": "↻"}[skill["group"]]
    return '<article class="skill-row" data-id="' + skill["id"] + '"><div class="skill-name"><span class="skill-glyph" aria-hidden="true">' + glyph + '</span><div><h3>' + e(skill["title"]) + '</h3><div class="skill-id">' + skill["id"] + '</div></div></div><p class="skill-summary">' + e(skill["summary"]) + '</p><div class="skill-actions"><button type="button" data-skill="' + skill["id"] + '" aria-label="查看' + e(skill["title"]) + '">查看方法</button><a href="downloads/' + skill["id"] + '-' + VERSION + '.zip" download aria-label="下载' + e(skill["title"]) + '">下载</a></div></article>'


def note_page(title, body):
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + escape(title) + '</title><style>body{font:16px/1.85 system-ui,"Microsoft YaHei",sans-serif;color:#193149;max-width:860px;margin:40px auto;padding:0 24px 50px}h1{font-size:32px;line-height:1.4}h2{font-size:21px;margin-top:34px}p,li{max-width:75ch}a{color:#244fbe;text-underline-offset:4px}code,pre{font:12px/1.85 Consolas,monospace;overflow-wrap:anywhere}pre{white-space:pre-wrap;background:#f2f6fa;padding:16px}.notice{background:#edf4fa;border-left:3px solid #244fbe;padding:18px}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #dce5ee;padding:10px;text-align:left;vertical-align:top}small{color:#53677a}.source{padding:16px 0;border-bottom:1px solid #dce5ee;overflow-wrap:anywhere}</style></head><body><a href="../index.html">返回工作流工具集</a><h1>' + escape(title) + '</h1>' + body + '</body></html>'


def main():
    data = json.loads((ROOT / "content/site.json").read_text(encoding="utf-8"))
    (DIST / "assets").mkdir(parents=True, exist_ok=True)
    for file in (ROOT / "site").iterdir():
        if file.suffix in (".css", ".js"):
            shutil.copy2(file, DIST / "assets" / file.name)
    media = ROOT / "content/media"
    if media.is_dir():
        for file in media.iterdir():
            if file.is_file(): shutil.copy2(file, DIST / "assets" / file.name)
    entries = []
    for skill in data["skills"]:
        directory = ROOT / "skills" / skill["id"]
        files = sorted(p for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        entries.append(dict(id=skill["id"], title=skill["title"], files=[dict(path=p.relative_to(directory).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]))
        for file in files:
            destination = DIST / "skills" / skill["id"] / file.relative_to(directory)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, destination)
    manifest = dict(name="ai-workflow-kit", version=VERSION, author="10878749", license="MIT", skills=entries,
                    scope="10 project workflows and independently authored work-loop-lite. No full private loop, project repositories, model credentials or third-party skill caches.")
    write(ROOT / "release-manifest.json", json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    shutil.copy2(ROOT / "release-manifest.json",DIST / "release-manifest.json")
    for name in ("LICENSE", "THIRD_PARTY.md"):
        shutil.copy2(ROOT / name,DIST / ("LICENSE.txt" if name=="LICENSE" else name))
    write(DIST / "assets/site-data.js","window.WORKFLOW_KIT="+json.dumps(data,ensure_ascii=False).replace("<","\\u003c")+";\n")
    write(DIST / "assets/favicon.svg",'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#edf3fa"/><path d="M14 22h8v28h-8zm14 8h8v20h-8zm14-14h8v34h-8z" fill="#244fbe"/></svg>')
    template = (ROOT / "site/index.html").read_text(encoding="utf-8")
    template = template.replace("__CASES__","".join(case_card(case) for case in data["cases"]))
    template = template.replace("__SKILLS__","".join(skill_row(skill) for skill in data["skills"]))
    extra = lambda row: '<div class="extra"><strong>'+escape(row["title"])+'</strong><small>'+escape(row["id"])+'</small><small>'+escape(row["status"])+('</small><a href="'+escape(row["url"],quote=True)+'" target="_blank" rel="noopener noreferrer">原项目</a>' if row["url"] else '</small>')+'</div>'
    template = template.replace("__EXTRAS__","".join(extra(row) for row in data["extras"]))
    write(DIST / "index.html",template)
    for case in data["cases"]:
        e=escape
        body='<p>'+e(case["intro"])+'</p><div class="notice"><strong>核对方式</strong><p>'+e(data["evidence_note"])+'</p><p>本次整理日期：2026-11-09。以下历史验证日期：'+case["date"]+'。</p></div>'
        for heading,values in (("遇到的问题",[case["problem"]]),("关键判断",case["decisions"]),("实际产物与保留结果",case["outcomes"])):
            body+='<h2>'+heading+'</h2><ul>'+''.join('<li>'+e(value)+'</li>' for value in values)+'</ul>'
        body+='<h2>结果摘要</h2><table><tbody>'+''.join('<tr><th>'+e(str(key))+'</th><td>'+e(str(value))+'</td></tr>' for key,value in case["facts"].items())+'</tbody></table>'
        body+='<h2>未验证项与适用边界</h2><p>'+e(case["limits"])+'</p><h2>来源文件指纹</h2><p>相对路径标识原项目中的来源位置。原文件并未公开打包，公开摘要不能替代对完整源码的独立审计。</p>'
        for item in case["sources"]:
            body+='<div class="source"><strong>'+e(item["file"])+'</strong><br><small>'+('行 '+str(item["lines"][0])+'–'+str(item["lines"][1]) if item.get("lines") else '保留截图')+'</small><br><code>SHA256 '+item["sha256"]+'</code></div>'
        write(DIST / "evidence" / (case["id"]+".html"),note_page(case["name"]+'：公开证据说明',body))
        write(ROOT / "evidence" / (case["id"]+".json"),json.dumps(case,ensure_ascii=False,indent=2)+"\n")
    body='<p>选择适合当前任务的技能；页面中的示例是方法导航，不会发起 AI 调用。</p><h2>下载安装</h2><ol><li>从首页下载技能合集并解压。</li><li>运行 <code>python scripts/install.py --skill reuse-first</code> 预览目标。</li><li>确认后增加 <code>--apply</code> 安装，或使用 <code>--dest</code> 指定宿主目录。</li><li>打开新聊天，用 <code>$reuse-first</code> 提出实际任务。</li></ol><h2>安装行为</h2><p>Python 3.10+，标准库，无需网络。安装前校验所选文件，已有不同内容不会覆盖。CODEX_HOME 优先，否则检测旧版 .codex/skills，再使用 .agents/skills。普通安装不修改项目或调用模型。</p><h2>版本与许可</h2><p>v0.1.0，MIT。只包含 10 项专项技能和独立的工作闭环基础版。完整内部 Loop 未公开。原项目的业务源码和第三方软件不随包分发。</p><h2>兼容性说明</h2><p>技能目录与离线安装可在本地复核。其他 Agent 宿主需按其规则配置；插件清单只是分发入口，不表示已通过应用商店审核。真实业务效果取决于模型、工具、上下文与任务。</p>'
    write(DIST / "docs/README.html",note_page('试用与说明',body))
    shared=[(ROOT/name,Path(name)) for name in ("LICENSE","README.md","THIRD_PARTY.md","release-manifest.json",".codex-plugin/plugin.json")]
    package_files=shared+[(ROOT/"scripts/install.py",Path("scripts/install.py"))]
    for skill in entries:
        folder=ROOT/"skills"/skill["id"]
        selected=[(folder/row["path"],Path("skills")/skill["id"]/row["path"]) for row in skill["files"]]
        package_files.extend(selected)
        zip_files(DIST/"downloads"/(skill["id"]+'-'+VERSION+'.zip'),[(file,Path(skill["id"])/file.relative_to(folder)) for file,_ in selected]+[(ROOT/"LICENSE",Path(skill["id"])/"LICENSE")])
    zip_files(DIST/"downloads"/('ai-workflow-kit-'+VERSION+'.zip'),[(file,Path("ai-workflow-kit")/relative) for file,relative in package_files])
    sources=[]
    for folder in ("skills","site","content","scripts","evidence",".codex-plugin",".github"):
        for file in (ROOT/folder).rglob("*"):
            if file.is_file() and "__pycache__" not in file.parts:
                sources.append((file,Path("ai-workflow-kit")/file.relative_to(ROOT)))
    sources += [(file,Path("ai-workflow-kit")/relative) for file,relative in shared if relative.parts[0] != ".codex-plugin"]
    sources += [(ROOT/".gitignore",Path("ai-workflow-kit/.gitignore"))]
    zip_files(DIST/"downloads"/('portfolio-source-'+VERSION+'.zip'),sources)
    checksums=[sha(file)+"  "+file.name for file in sorted((DIST/"downloads").glob("*.zip"))]
    write(DIST/"downloads/SHA256SUMS.txt","\n".join(checksums)+"\n")
    print(json.dumps(dict(skills=len(entries),case_pages=len(data["cases"]),archives=len(checksums)),ensure_ascii=False))


if __name__ == "__main__": main()
