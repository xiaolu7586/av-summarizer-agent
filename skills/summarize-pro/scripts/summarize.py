#!/usr/bin/env python3
"""
summarize.py - Audio/Video Transcription + Scenario Analysis

Cross-platform (macOS / Linux / Windows).
Transcription: 平台转录 API (no user API Key needed).
Scenario Recognition: Keyword matching (no API needed).
Summarization: Handled by Agent using user-configured LLM (not in this script).
Optional: ffmpeg (format conversion/compression), yt-dlp (URL download).
"""

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ─── Print helpers ───────────────────────────────────────
QUIET_MODE = False

def print_info(msg):
    if not QUIET_MODE:
        print(f"ℹ️  {msg}", file=sys.stderr)

def print_success(msg):
    print(f"✅ {msg}", file=sys.stderr)

def print_warning(msg):
    print(f"⚠️  {msg}", file=sys.stderr)

def print_error(msg):
    print(f"❌ {msg}", file=sys.stderr)

def print_step(msg):
    if not QUIET_MODE:
        print(f"👉 {msg}", file=sys.stderr)

def print_header(msg):
    if not QUIET_MODE:
        print(f"🦞 {msg}", file=sys.stderr)

def print_progress(msg):
    print(f"{msg}", file=sys.stderr)


# ─── OS-aware install hint ───────────────────────────────
def install_hint(pkg):
    system = platform.system()
    if system == "Darwin":
        return f"brew install {pkg}"
    elif system == "Windows":
        if shutil.which("winget"):
            return f"winget install {pkg}"
        elif shutil.which("choco"):
            return f"choco install {pkg}"
        elif shutil.which("scoop"):
            return f"scoop install {pkg}"
        return f"winget install {pkg}"
    else:  # Linux
        if shutil.which("apt-get"):
            return f"sudo apt-get install {pkg}"
        elif shutil.which("dnf"):
            return f"sudo dnf install {pkg}"
        elif shutil.which("pacman"):
            return f"sudo pacman -S {pkg}"
        return f"(please install {pkg} with your package manager)"


# ─── Check transcription availability ───────────────────
def check_transcription_available():
    """Check OpenClaw user identity exists (required for platform API)."""
    openclaw_home = os.path.join(os.path.expanduser("~"), ".openclaw")
    userinfo_path = os.path.join(openclaw_home, "identity", "openclaw-userinfo.json")
    if os.path.isfile(userinfo_path):
        print_info("Transcription: 平台转录 API")
        return True

    print_error("OpenClaw user identity not found")
    print("")
    print("Please ensure OpenClaw is properly installed and you are logged in.")
    print(f"Expected: {userinfo_path}")
    print("")
    sys.exit(1)


# ─── Douyin URL detection & download (inline) ───────────
DOUYIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "EdgiOS/121.0.2277.107 Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def is_douyin_url(url):
    """Check if URL is a Douyin link."""
    return bool(re.search(r'douyin\.com|iesdouyin\.com', url))


def _douyin_http_get(url, max_redirects=5):
    """GET request with redirect following, returns (final_url, body)."""
    import urllib.request as urlreq
    import urllib.error as urlerr
    for _ in range(max_redirects):
        req = urlreq.Request(url, headers=DOUYIN_HEADERS)
        try:
            resp = urlreq.urlopen(req, timeout=30)
            return resp.url, resp.read().decode("utf-8", errors="ignore")
        except urlerr.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                url = e.headers["Location"]
                continue
            raise
    raise Exception(f"Too many redirects: {url}")


def _douyin_resolve_modal_id(share_text):
    """Extract modal_id from share text or URL."""
    # modal_id=xxx or modal_id:xxx
    m = re.search(r"modal_id[=:](\d+)", share_text)
    if m:
        return m.group(1)
    # /video/xxx
    m = re.search(r"/video/(\d+)", share_text)
    if m:
        return m.group(1)
    # Pure digits (16+)
    m = re.search(r"(\d{16,})", share_text.strip())
    if m:
        return m.group(1)

    # Extract URL and follow redirects
    url_match = re.search(r"https?://[^\s]+", share_text)
    if not url_match:
        return None
    final_url, _ = _douyin_http_get(url_match.group(0))
    m = re.search(r"/video/(\d+)", final_url)
    if m:
        return m.group(1)
    m = re.search(r"modal_id[=:](\d+)", final_url)
    if m:
        return m.group(1)
    return None


def _douyin_get_video_url(modal_id):
    """Get video download URL from iesdouyin.com, returns (video_url, title)."""
    import json as _json
    page_url = f"https://www.iesdouyin.com/share/video/{modal_id}/"
    _, html = _douyin_http_get(page_url)

    match = re.search(r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", html, re.DOTALL)
    if not match:
        print_error("Douyin page structure changed: _ROUTER_DATA not found")
        return None, None

    try:
        data = _json.loads(match.group(1).strip())
    except _json.JSONDecodeError as e:
        print_error(f"Douyin page JSON parse failed: {e}")
        return None, None

    loader_data = data.get("loaderData", data)

    # Try known page keys; log all available keys on failure for debugging
    video_data = None
    tried_keys = ["video_(id)/page", "note_(id)/page"]
    for key in tried_keys:
        page_data = loader_data.get(key)
        if page_data:
            item_list = (
                page_data.get("videoInfoRes", {}).get("item_list")
                or page_data.get("videoInfoRes", {}).get("aweme_list")
            )
            if item_list and len(item_list) > 0:
                video_data = item_list[0]
                break

    if not video_data:
        available_keys = list(loader_data.keys())
        print_error(f"Douyin page structure changed: video data not found under {tried_keys}")
        print_error(f"Available loaderData keys: {available_keys}")
        return None, None

    video_url = None
    url_list = video_data.get("video", {}).get("play_addr", {}).get("url_list", [])
    if url_list:
        video_url = url_list[0]
    if not video_url:
        url_list = video_data.get("video", {}).get("download_addr", {}).get("url_list", [])
        if url_list:
            video_url = url_list[0]

    title = video_data.get("desc", f"douyin_{modal_id}")
    return video_url, title


def _get_files_dir():
    """Get the files directory for storing downloaded files."""
    workspace = os.path.join(SCRIPT_DIR, "..", "..", "..", "files")
    os.makedirs(workspace, exist_ok=True)
    return workspace


MAX_TRANSCRIBE_SIZE = 25 * 1024 * 1024  # 25MB, 平台转录 API limit


def download_douyin_video(url, output_file):
    """Download Douyin video. If file > 25MB and ffmpeg available, extract audio."""
    import urllib.request as urlreq

    print_step("Parsing Douyin link...")

    # Step 1: Resolve modal_id
    modal_id = _douyin_resolve_modal_id(url)
    if not modal_id:
        print_error("Failed to extract Douyin video ID")
        return False

    print_info(f"Video ID: {modal_id}")

    # Step 2: Get video URL from iesdouyin.com
    video_url, title = _douyin_get_video_url(modal_id)
    if not video_url:
        print_error("Failed to get Douyin video URL")
        return False

    print_info(f"Title: {title}")
    print_step("Downloading Douyin video...")

    # Step 3: Download video to files directory
    files_dir = _get_files_dir()
    video_path = os.path.join(files_dir, f"{modal_id}.mp4")

    req = urlreq.Request(video_url, headers=DOUYIN_HEADERS)
    resp = urlreq.urlopen(req, timeout=120)

    with open(video_path, "wb") as f:
        while True:
            chunk = resp.read(8192)
            if not chunk:
                break
            f.write(chunk)

    if not os.path.isfile(video_path) or os.path.getsize(video_path) == 0:
        print_error("Download resulted in empty file")
        return False

    file_size = os.path.getsize(video_path)
    size_mb = file_size / (1024 * 1024)
    print_info(f"Video size: {size_mb:.1f}MB")

    # Step 4: If file > 25MB and ffmpeg available, extract audio to reduce size
    if file_size >= MAX_TRANSCRIBE_SIZE and shutil.which("ffmpeg"):
        audio_path = os.path.join(files_dir, f"{modal_id}.mp3")
        print_step(f"Video exceeds 25MB, extracting audio with ffmpeg...")
        try:
            subprocess.run(
                ["ffmpeg", "-i", video_path, "-vn",
                 "-acodec", "libmp3lame", "-q:a", "4",
                 "-y", audio_path],
                capture_output=True, check=True, timeout=120
            )
            os.remove(video_path)
            audio_size = os.path.getsize(audio_path) / (1024 * 1024)
            print_success(f"Audio extracted: {audio_size:.1f}MB (from {size_mb:.1f}MB video)")
            return audio_path
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print_warning("ffmpeg extraction failed, using video file")
    elif file_size >= MAX_TRANSCRIBE_SIZE:
        print_warning(f"Video is {size_mb:.1f}MB (exceeds 25MB API limit, no ffmpeg available)")

    print_success(f"Douyin video downloaded: {video_path}")
    return video_path


# ─── Download audio from URL ────────────────────────────
def download_from_url(url, output_file):
    print_info(f"Downloading: {url}")

    # Douyin links: use built-in downloader only, do NOT fall back to yt-dlp
    if is_douyin_url(url):
        print_info("Detected Douyin link, using built-in downloader")
        result = download_douyin_video(url, output_file)
        if result:
            return result  # returns actual file path (mp4 or mp3)
        # Douyin download failed — yt-dlp cannot handle Douyin, exit immediately
        print_error("Douyin download failed. Cannot proceed with transcription.")
        sys.exit(1)

    # Try yt-dlp first
    if shutil.which("yt-dlp"):
        print_step("Extracting audio with yt-dlp...")
        try:
            subprocess.run(
                ["yt-dlp", "-x", "--audio-format", "mp3",
                 "--postprocessor-args", "ffmpeg:-ar 16000 -ac 1",
                 "-o", output_file, url],
                check=True, capture_output=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    # Try direct download with urllib
    try:
        import urllib.request
        urllib.request.urlretrieve(url, output_file)
        if os.path.isfile(output_file) and os.path.getsize(output_file) > 0:
            return True
    except Exception:
        pass

    print_error("Download failed")
    print_info("yt-dlp is required for online video/audio")
    print_info(f"Install: {install_hint('yt-dlp')}")
    return False


# ─── Transcribe: delegate to transcribe.py ──────────────
def transcribe_audio(input_file, output_file, language):
    transcribe_script = os.path.join(SCRIPT_DIR, "transcribe.py")

    if not os.path.isfile(transcribe_script):
        print_error(f"transcribe.py not found: {transcribe_script}")
        return False

    cmd = [sys.executable, transcribe_script, input_file]
    if language:
        cmd += ["--language", language]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if result.stderr:
            print_error(result.stderr.strip())
        return False
    # Write stdout (transcript text) to output_file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result.stdout)
    return True


# ─── Keyword-based scenario recognition ─────────────────
SCENARIO_KEYWORDS = {
    "meeting": [
        # 中文
        "讨论", "决定", "任务", "负责人", "下一步", "安排", "会议", "团队", "完成", "项目",
        # English
        "discussion", "decision", "action item", "agenda", "attendee",
        "meeting", "team", "deadline", "owner", "next step",
    ],
    "interview": [
        # 中文
        "访谈", "用户", "痛点", "需求", "问题", "回答", "请问", "体验", "使用", "反馈",
        # English
        "interview", "interviewee", "pain point", "feedback", "user",
        "experience", "may i ask", "opinion", "insight", "respondent",
    ],
    "lecture": [
        # 中文
        "课程", "学习", "知识", "概念", "理解", "重点", "大纲", "同学", "今天讲", "掌握",
        # English
        "course", "lecture", "learning", "concept", "outline",
        "key point", "student", "lesson", "chapter", "explain",
    ],
    "podcast": [
        # 中文
        "播客", "节目", "嘉宾", "话题", "观点", "分享", "故事", "经历", "觉得", "聊聊",
        # English
        "podcast", "guest", "episode", "host", "topic",
        "story", "opinion", "show", "sharing", "chat",
    ],
}

SCENARIO_PROMPTS = {
    "meeting": "请重点关注：决策事项、待办任务、负责人、时间节点。输出结构应包含：会议主题、讨论要点、决策事项、待办任务。",
    "interview": "请重点关注：受访者背景、核心痛点、需求洞察、关键观点。输出结构应包含：受访者画像、核心痛点、需求洞察、精彩观点。",
    "lecture": "请重点关注：课程大纲、核心知识点、案例说明。输出结构应包含：课程主题、知识大纲、核心概念、案例/示例。",
    "podcast": "请重点关注：话题列表、嘉宾观点、精彩金句。输出结构应包含：话题概览、嘉宾观点、精彩金句/故事。",
    "general": "请总结以下内容的核心要点和关键结论。保持结构清晰，重点突出。",
}

SCENARIO_NAMES = {
    "meeting": "会议",
    "interview": "访谈",
    "lecture": "课程",
    "podcast": "播客",
    "general": "通用内容",
}

SCENARIO_EMOJIS = {
    "meeting": "🗂",
    "interview": "🎤",
    "lecture": "📚",
    "podcast": "🎙",
    "general": "📝",
}


def analyze_content_type(text, force_type=""):
    if force_type:
        return {
            "type": force_type,
            "prompt": SCENARIO_PROMPTS.get(force_type, SCENARIO_PROMPTS["general"]),
        }

    if not QUIET_MODE:
        print_step("Scenario recognition: keyword matching...")

    preview = text[:3000].lower()
    scores = {}
    for scenario, keywords in SCENARIO_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in preview)
        scores[scenario] = score

    best_type = "general"
    best_score = 2  # threshold: need at least 3 hits
    for scenario, score in scores.items():
        if score > best_score:
            best_type = scenario
            best_score = score

    return {
        "type": best_type,
        "prompt": SCENARIO_PROMPTS.get(best_type, SCENARIO_PROMPTS["general"]),
    }


# ─── Process input: determine file type ─────────────────
# Audio/video formats (transcribe.py handles format conversion internally)
AUDIO_VIDEO_FORMATS = {
    "mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "flac", "ogg", "oga",
    "mov", "avi", "mkv", "flv", "wmv", "ts",
}
# Text formats (skip transcription)
TEXT_FORMATS = {"txt", "md"}


def process_input(input_file):
    """Determine input type.

    Returns:
      "transcribe" - needs transcription (audio/video file path or downloaded URL)
      "text"       - text file, skip transcription
      None         - error
      The actual file path to process is returned as second element.
    """
    # URL: download first
    if re.match(r'^https?://', input_file):
        print_info(f"URL detected: {input_file}")
        temp_audio = os.path.join(
            tempfile.gettempdir(), f"summarize-download-{os.getpid()}.mp3"
        )
        result = download_from_url(input_file, temp_audio)
        if result:
            # result may be True (yt-dlp/urllib) or a file path string (douyin)
            actual_file = result if isinstance(result, str) else temp_audio
            print_success("Download complete")
            return "transcribe", actual_file
        return None, None

    ext = os.path.splitext(input_file)[1].lstrip(".").lower()

    if ext in TEXT_FORMATS:
        print_info(f"Text file: .{ext}")
        return "text", input_file

    if ext in AUDIO_VIDEO_FORMATS:
        print_info(f"Audio/video format: .{ext}")
        return "transcribe", input_file

    # Unknown format - let transcribe.py try
    print_warning(f"Unknown format .{ext}, will attempt transcription")
    return "transcribe", input_file


# ─── Generate analysis report ───────────────────────────
def generate_report(transcript_file, output_file, language, force_type):
    if not QUIET_MODE:
        print_header("Generating analysis report (scenario recognition + summary guidance)")
        print("")

    if not os.path.isfile(transcript_file):
        print_error(f"Transcript file not found: {transcript_file}")
        return False

    with open(transcript_file, "r", encoding="utf-8") as f:
        transcript = f.read()

    char_count = len(transcript)
    basename = os.path.splitext(os.path.basename(transcript_file))[0]
    basename = re.sub(r'-transcript.*', '', basename)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not QUIET_MODE:
        print_info(f"Transcript: {char_count} characters")

    if char_count < 100:
        print_warning("Text too short, skipping analysis")
        return False

    if char_count > 50000 and not QUIET_MODE:
        print_warning(f"Long text ({char_count} characters), full content preserved")

    # Analyze content type
    analysis = analyze_content_type(transcript, force_type)
    content_type = analysis["type"]
    system_prompt = analysis["prompt"]
    type_name = SCENARIO_NAMES.get(content_type, "通用内容")

    if not QUIET_MODE:
        print_info(f"Content type: {content_type}")
        print_info(f"Summary strategy: {system_prompt[:60]}...")
        print_step("Generating analysis report...")
    else:
        emoji = SCENARIO_EMOJIS.get(content_type, "📝")
        print_progress(f"{emoji} Scenario: {content_type}")

    # Estimate duration (rough: 150 chars/min for Chinese)
    est_min = char_count // 150
    est_duration = f"{est_min} min" if est_min >= 1 else "< 1 min"

    # Write report
    report = f"""# 📊 Transcription Analysis Report

**File**: {basename}
**Processed**: {timestamp}
**Content Type**: {type_name} ({content_type})
**Character Count**: {char_count}
**Estimated Duration**: {est_duration}

---

## 🎯 Scenario Recognition Result

**Scenario**: {type_name}

**Summary Strategy**:
{system_prompt}

---

## 📝 Full Transcript

{transcript}

---

## 🤖 Next Step

**Agent takes over**: OpenClaw Agent will now use the user-configured LLM to generate the summary.

**Suggested Prompt**:
```
Please generate a structured summary based on the "Summary Strategy" above.
Scenario type: {type_name}
Output format: Markdown
```

---

*Generated by Summarize Pro 🦞 | Transcription only, LLM-agnostic*
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)

    if not QUIET_MODE:
        print_success(f"Analysis report saved: {output_file}")
        print("")
        print_header("🎯 Transcription complete! Agent will now generate the summary.")
        print("")
        print_info(f"Scenario: {type_name}")
        print_info(f"Characters: {char_count}")
        print_info(f"Report: {output_file}")
        print("")
        print_step("Agent will use user-configured LLM model to complete the summary")

    return True



# ─── Main processing ────────────────────────────────────
def _default_output_dir():
    """Auto output dir: <workspace_root>/summarizer-files/<timestamp>/"""
    workspace = os.path.join(SCRIPT_DIR, "..", "..", "..")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return os.path.join(workspace, "summarizer-files", timestamp)


def process_file(input_file, output_dir, language, transcribe_only,
                 summarize_only, full_mode, force_type):

    is_url = re.match(r'^https?://', input_file)
    if not is_url and not os.path.isfile(input_file):
        print_error(f"File not found: {input_file}")
        sys.exit(1)

    basename = re.sub(r'\.[^.]*$', '', os.path.basename(input_file))
    # URL inputs: use a safe basename
    if is_url:
        basename = re.sub(r'[^\w\-]', '_', basename) or "url_input"

    if not QUIET_MODE:
        print_header("Summarize Pro - Audio/Video Transcription + Scenario Analysis")
        print("")
        print_info(f"Input: {input_file}")
        print_info(f"Output: {output_dir}")
        print_info(f"Transcription: 平台转录 API")
        print_info(f"Analysis: Keyword scenario recognition")
        print_info(f"Summary: Handled by Agent using user LLM")
        print("")
    else:
        print_progress(f"🎵 Processing: {os.path.basename(input_file)}")

    os.makedirs(output_dir, exist_ok=True)

    # Summary-only mode
    if summarize_only:
        summary_file = os.path.join(output_dir, f"{basename}-summary.md")
        generate_report(input_file, summary_file, language, force_type)
        return

    transcript_file = os.path.join(output_dir, f"{basename}-transcript.txt")
    summary_file = os.path.join(output_dir, f"{basename}-summary.md")

    # Step 1: Determine input type
    if not QUIET_MODE:
        print_step("Processing input file...")
    else:
        print_progress("📂 Preparing file...")

    input_type, actual_file = process_input(input_file)

    if input_type is None:
        sys.exit(1)

    if input_type == "text":
        # Text file, just copy
        shutil.copy2(actual_file, transcript_file)
        if not QUIET_MODE:
            print_success(f"Text file copied: {transcript_file}")
    else:
        # Step 2: Transcribe via 平台转录 API
        if not QUIET_MODE:
            print_step("Transcribing via 平台转录 API...")
        else:
            print_progress("🎙️ Transcribing...")

        is_downloaded = actual_file != input_file  # URL downloads need cleanup

        if not transcribe_audio(actual_file, transcript_file, language):
            print_error("Transcription failed")
            if is_downloaded:
                _cleanup(actual_file)
            sys.exit(1)

        if not QUIET_MODE:
            print_success(f"Transcript saved: {transcript_file}")
        else:
            print_progress("✅ Transcription complete")

        if is_downloaded:
            _cleanup(actual_file)

    # Transcribe-only mode
    if transcribe_only:
        print_success("Transcription complete!")
        return

    if not QUIET_MODE:
        print("")

    # Step 3: Generate analysis report
    if QUIET_MODE:
        print_progress("🎯 Recognizing scenario...")

    generate_report(transcript_file, summary_file, language, force_type)

    if not QUIET_MODE:
        print("")
        print_header("Done!")
        print("")
        print_info("Output files:")
        print(f"  • Transcript: {transcript_file}", file=sys.stderr)
        if os.path.isfile(summary_file):
            print(f"  • Report: {summary_file}", file=sys.stderr)
    else:
        print_success("Analysis report generated")
        print(summary_file)


def _cleanup(path):
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


# ─── CLI ─────────────────────────────────────────────────
def main():
    global QUIET_MODE

    parser = argparse.ArgumentParser(
        description="Summarize Pro - Audio/Video Transcription + Intelligent Summarization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported formats:
  Audio:  mp3, wav, m4a, flac, ogg, oga, mpga, mpeg
  Video:  mp4, webm (native support)
  Video:  mov, avi, mkv, flv (requires ffmpeg)
  Text:   txt, md (direct analysis, skips transcription)
  URL:    https:// (YouTube, Bilibili, etc., requires yt-dlp)

Authentication:
  Uses 平台转录 API (no user API Key needed).
  Requires: ~/.openclaw/identity/openclaw-userinfo.json (auto-created on login).
"""
    )
    parser.add_argument("input", help="Audio/video/text file or URL")
    parser.add_argument("-o", "--output", default=None,
                        help="Output directory (default: auto-created summarizer-files/<timestamp>/ under workspace)")
    parser.add_argument("-l", "--language", default="zh", help="Language code (default: zh)")
    parser.add_argument("-t", "--transcribe-only", action="store_true", help="Transcription only")
    parser.add_argument("--summarize-only", action="store_true", help="Scenario analysis only (input must be text)")
    parser.add_argument("--type", dest="force_type", default="",
                        help="Force content type (meeting/interview/lecture/podcast/general)")
    parser.add_argument("-f", "--full", action="store_true", help="Full mode: transcribe + analysis")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode (for Agent calls)")

    args = parser.parse_args()
    QUIET_MODE = args.quiet

    check_transcription_available()

    output_dir = args.output if args.output else _default_output_dir()

    process_file(
        args.input, output_dir, args.language,
        args.transcribe_only, args.summarize_only,
        args.full, args.force_type
    )


if __name__ == "__main__":
    main()
