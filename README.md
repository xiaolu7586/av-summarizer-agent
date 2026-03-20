# 全能总结助手

> OpenClaw Agent 配置 — 可用于任何兼容 OpenClaw 协议的 AI 产品

## 简介

支持 8 种内容类型的智能总结 Agent。输入音视频、PDF、图片、网页或文本，自动生成结构化 Markdown 报告，并输出思维导图 PNG。

## 核心功能

- 🎙️ **音视频转录** — 本地文件 / 抖音 / YouTube / Bilibili，自动识别场景类型
- 📄 **多格式支持** — PDF、图片、网页 URL、文本文档，无需转录直接总结
- 🧠 **场景智能识别** — 自动识别会议 / 访谈 / 课程 / 播客 / 通用，调整总结策略
- 🗺️ **思维导图 PNG** — 每次总结后自动生成可视化思维导图
- 💬 **飞书直接发图** — 支持飞书渠道时自动将思维导图发送给用户

---

## 🚀 零配置启动

以下功能**无需任何配置**即可使用：

> PDF 总结 · 图片理解 · 网页抓取总结 · 文本文档总结 · 思维导图生成

Agent 内置可选配置项（转录 API Key），用于解锁音视频转录能力。详见下方「可选增强能力」。

---

## ✨ 可选增强能力

### 增强 1：音视频转录（解锁核心能力）

配置后可处理：本地音视频文件、抖音链接、YouTube / Bilibili 等在线视频。

**需要：** OpenAI 兼容的转录 API Key（OpenAI Whisper API 或 Deepgram 等）

在 Agent 配置中填入：
- `转录 API Key` — 必填（如 `sk-...`）
- `转录 API Base URL` — 选填，留空默认使用 OpenAI

**获取 OpenAI API Key：** [platform.openai.com](https://platform.openai.com) → API Keys → Create new secret key

**注意：** 抖音链接使用内置下载器，无需额外工具；YouTube/Bilibili 等需安装 yt-dlp。

### 增强 2：在线视频下载（YouTube / Bilibili 等）

**需要：** yt-dlp

```bash
brew install yt-dlp       # macOS
winget install yt-dlp     # Windows
sudo apt install yt-dlp   # Linux
```

### 增强 3：思维导图 PNG 导出

**需要：** Node.js + Google Chrome + Python 3 + Pillow

```bash
pip install Pillow
```

Chrome 需已安装（[下载](https://www.google.com/chrome/)）。不满足时自动跳过，仍输出文字报告。

### 增强 4：视频格式转换（大文件压缩）

**需要：** ffmpeg（可选，处理超过 25MB 的视频或非常见格式）

```bash
brew install ffmpeg       # macOS
winget install ffmpeg     # Windows
```

---

## 支持的输入类型

| 类型 | 示例 | 是否需要转录 API |
|------|------|----------------|
| 本地音频 | mp3, wav, m4a | ✅ 需要 |
| 本地视频 | mp4, mov, mkv | ✅ 需要 |
| 抖音链接 | v.douyin.com/... | ✅ 需要 |
| 在线视频 | YouTube, Bilibili | ✅ 需要 + yt-dlp |
| PDF 文件 | report.pdf | ❌ 不需要 |
| 图片 | jpg, png, webp | ❌ 不需要 |
| 网页 URL | https://... | ❌ 不需要 |
| 文本文档 | txt, md, docx | ❌ 不需要 |

---

## 输出格式

每次总结统一生成：

```
summarizer-files/<时间戳>/
  <文件名>-transcript.txt     ← 转录原文（音视频类型）
  <文件名>-summary.md         ← 场景分析报告
  <文件名>-summary-final.md   ← 最终总结报告
  <文件名>-mindmap.md         ← 思维导图源文件
  <文件名>-mindmap.png        ← 思维导图图片
```

报告结构：纪要标题 · 类型 · 摘要 · AI 建议 · 待办事项 · 金句

---

## 场景识别类型

| 场景 | 关键词触发 | 总结重点 |
|------|-----------|---------|
| 会议 | 讨论、决定、任务、负责人 | 决策事项 + 待办 + 负责人 |
| 访谈 | 用户、痛点、需求、体验 | 受访者画像 + 核心洞察 |
| 课程 | 课程、知识、概念、大纲 | 知识大纲 + 核心概念 |
| 播客 | 播客、嘉宾、话题、分享 | 话题列表 + 嘉宾观点 |
| 通用 | 以上均未命中 | 核心要点 + 关键结论 |

---

## Skills

| Skill | 功能 |
|-------|------|
| `summarize-pro` | 8 种输入类型转录 + 场景识别 + 分析报告生成 |
| `markmap-mindmap-export` | Markdown 大纲 → 思维导图 HTML + PNG 导出 |

---

## 快速开始

```
"帮我总结这个会议录音：meeting.mp3"    → 转录 + 场景识别 + 总结 + 思维导图
"帮我总结这篇文章"（附 URL）            → 抓取网页正文 + 总结
"总结这个 PDF"（附文件）               → 读取 PDF + 总结
"帮我总结这个抖音视频：<链接>"          → 内置下载器 + 转录 + 总结
```

---

## 相关项目

- [wechat-writing-agent](https://github.com/xiaolu7586/wechat-writing-agent) — 微信公众号写作专家
- [stockexpert-agent](https://github.com/xiaolu7586/stockexpert-agent) — 股票专家 Agent
