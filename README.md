# AI 产品与工程工作流工具集

将真实项目实践整理成可复用技能：10 项专项工作流与 1 项工作闭环基础版。

作者标识：10878749。与 AI 协作设计、开发与核查。原项目底层算法、第三方库和素材分别保留原归属；本集合不主张所有依赖均为原创。

展示与下载：https://10878749.github.io/ai-workflow-skills/

备用展示站：https://ai-workflow-kit-wj.fumika981117.chatgpt.site

公开仓库：https://github.com/10878749/ai-workflow-skills

## 下载安装

需要 Python 3.10+；安装器仅使用标准库，不联网。

也可通过现有 Skills CLI 从公开仓库选择技能和 Agent：

```text
npx skills add 10878749/ai-workflow-skills --skill reuse-first -a codex
```

该安装器需要 Node.js，版本要求以 https://github.com/vercel-labs/skills 为准。首次会下载第三方 CLI；本轮未在真实全局环境执行此远程安装命令。离线包可按下面方式安装。

```text
python scripts/install.py --skill reuse-first
python scripts/install.py --skill reuse-first --apply
```

第一条仅预览；第二条才执行。安装前核对文件摘要，不覆盖已有不同内容。

```text
python scripts/install.py --all --apply
python scripts/install.py --skill work-loop-lite --dest YOUR_SKILL_DIRECTORY --apply
```

默认目标：有 CODEX_HOME 则使用其 skills；已有 ~/.codex/skills 则沿用；否则使用 ~/.agents/skills。也可以显式指定宿主要求的目录。不要把不同宿主的目录约定混用。

没有 Python 时，可让 coding agent 阅读本 README，并将所选 `skills/<name>` 安装到当前宿主的技能目录，保留已有内容。安装后在新聊天中用 `$reuse-first` 等调用。卸载时仅移除确认属于本包且未被自行修改的技能文件夹，不修改全局规则。

## 三个可复核的项目案例

- 光赢大师：独立 RAG 对照实验、资料外发边界与分层验证；真实模型效果未验收。
- 页间：AI 推敲与轻量抽书、请求级取消和中断恢复；历史线上复测受限如实保留。
- WeldSTA：核心编译包、依赖隔离、换路径哈希与自检；不是全新 Windows 或完整软件功能验收。

公开 `evidence/*.json` 提供脱敏摘要、保留结果与原文件指纹；不是原项目源码或完整日志。历史结果均标明日期，本次整理没有重新调用模型或部署原项目。

## 本地预览与重建

网站源码包包含以下构建脚本；仅技能安装包不含网站构建文件。

```text
python scripts/build.py
python -m http.server 8080 --directory dist
```

打开 http://127.0.0.1:8080 。也可直接打开 dist/index.html，交互不依赖站外资源。`scripts/build.py` 只读取本仓库公开内容，不访问作者原项目目录。

`.codex-plugin/plugin.json` 是技能集合的兼容分发清单；尚未声称插件商店审核或跨宿主行为验证。也可通过支持 GitHub 仓库的技能安装器安装本目录结构；远程安装入口以实际公开仓库为准。

## 公开与私有

基础版单独编写，可完成一次任务的目标、基线、实施、验证和交接。内部完整 Loop、个性化编排、完整案例/评估库、生产配置、客户资料与凭据不在此仓库或下载包中。

第三方技能只作来源导航，不随本包复制分发。原始内部总览也不在发布目录。

## 发布

本目录支持静态托管。GitHub Pages 工作流会在 `main` 分支收到推送时构建并发布 `dist/`，也可手动运行。下载与源码归档由构建脚本自动生成，页面、案例、样式和安装包均随网站一起托管。

首次启用：

1. 打开 https://github.com/10878749/ai-workflow-skills/settings/pages ，将 **Build and deployment → Source** 设为 **GitHub Actions**。
2. 打开 https://github.com/10878749/ai-workflow-skills/actions/workflows/pages.yml ，单击 **Run workflow**，选择 `main`，再单击 **Run workflow**。
3. 等待 **Publish portfolio** 成功后，访问 https://10878749.github.io/ai-workflow-skills/ 。这是启用后的目标地址；仅提交工作流不表示网站已经上线。

后续修改公开源码并推送到 `main` 即可自动更新。所有页面资源与下载路径使用相对地址，可部署在 GitHub Pages 的 `/ai-workflow-skills/` 子路径下，无需原 Sites 服务提供资源。GitHub Pages 的国内直连体验需在目标网络实测。

Sites 的托管身份仅用于原站部署，不进入公开源码 ZIP。原展示站可继续作为备用入口。

许可：MIT，参见 LICENSE；归属与素材说明参见 THIRD_PARTY.md。
