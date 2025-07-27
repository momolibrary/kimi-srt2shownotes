from openai import OpenAI
import sys
from typing import List
import time
import datetime


def kimi_rpm_handle(call_func, *args, **kwargs):
    """
    通用Kimi速率限制处理，call_func为API调用函数。
    """
    while True:
        try:
            return call_func(*args, **kwargs)
        except Exception as e:
            if hasattr(e, 'status_code') and e.status_code == 429:
                print("[Kimi] 触发速率限制，等待1.2秒后重试...")
                time.sleep(1.2)
            else:
                print(f"[Kimi] 发生错误：{e}")
                raise

# 配置 Moonshot Kimi API
client = OpenAI(
    api_key="Your_api_key",  # 替换为你的 API Key
    base_url="https://api.moonshot.cn/v1",
)

def kimi_generate_titles(text_list):
    """
    为每段文本单独生成标题，返回标题列表，自动处理速率限制，并输出进度日志。
    """
    titles = []
    total = len(text_list)
    for idx, text in enumerate(text_list, 1):
        print(f"[Kimi] 正在生成第 {idx}/{total} 段标题...")
        prompt = (
            "你现在是一个专业的内容标题生成专家。我会给你一些文本片段，请你为每个片段生成标题。\n"
            "要求：\n"
            "1. 标题长度：5-15字\n"
            "2. 风格要求：\n   - 新闻式标题\n   - 简洁明了\n   - 包含核心信息\n   - 避免过于笼统的表述\n"
            "3. 内容要求：\n   - 准确反映文本主题\n   - 突出重要信息\n   - 保持客观性\n   - 符合上下文连贯性\n"
            "格式要求：\n- 输入：文本片段\n- 输出：仅返回标题，不需要解释\n"
            f"请为以下文本生成标题：\n{text}\n"
        )
        def call():
            return client.chat.completions.create(
                model = "kimi-k2-0711-preview",
                messages = [
                    {"role": "system", "content": "你是 Kimi，由 Moonshot AI 提供的人工智能助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature = 0.6,
            )
        completion = kimi_rpm_handle(call)
        title = completion.choices[0].message.content.strip().split('\n')[0].strip()
        titles.append(title)
        print(f"[Kimi] 第 {idx} 段标题生成完成：{title}")
    print("[Kimi] 所有标题生成完毕。\n")
    return titles

def kimi_proofread_segments(text_list):
    """
    为每段文本单独校对，返回校对后文本列表，自动处理速率限制，并输出进度日志。
    """
    proofread = []
    total = len(text_list)
    for idx, text in enumerate(text_list, 1):
        print(f"[Kimi] 正在校对第 {idx}/{total} 段正文...")
        print(f"校对文本：{text}")
        prompt = (
            "你现在是一个专业的口播稿校对专家。我将提供一段口播稿，请你对其进行校对。\n\n"
            "核心原则：\n"
            "- 严格禁止删除或裁剪任何内容\n"
            "- 必须保持原文的每一句话\n"
            "- 禁止对文本进行重写或改写\n"
            "- 禁止对文本进行总结或精简\n\n"
            "允许的修改仅限于：\n"
            "1. 标点符号处理：\n"
            "   - 在语意完整处添加标点符号\n"
            "   - 使用常见中文标点（，。；：""《》？！）\n"
            "2. 错别字修正：\n"
            "   - 仅修正明确的错别字\n"
            "   - 保持专有名词的准确性\n\n"
            "警告：\n"
            "- 如果输出的文本字数与输入的文本字数（不计标点）不一致，则视为失败\n"
            "- 除标点和错别字外，严禁改动原文的任何部分\n\n"
            "请对以下口播稿进行校对，并确保输出的是完整的、未经删减的文本：\n"
            f"{text}\n"
        )

        def call():
            return client.chat.completions.create(
                model = "kimi-k2-0711-preview",
                messages = [
                    {"role": "system", "content": "你是 Kimi，由 Moonshot AI 提供的人工智能助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature = 0.6,
            )
        completion = kimi_rpm_handle(call)
        text_out = completion.choices[0].message.content.strip().split('\n')[0].strip()
        proofread.append(text_out)
        print(f"[Kimi] 第 {idx} 段正文校对完成：{text_out}")
        print(f"[Kimi] 第 {idx} 段正文校对完成。")
    print("[Kimi] 所有正文校对完毕。\n")
    return proofread



# 主要数据结构和类型说明
class SubtitleItem:
    def __init__(self, index: int, start_time: str, end_time: str, text: str):
        self.index = index
        self.start_time = start_time
        self.end_time = end_time
        self.text = text


class MergedSegment:
    def __init__(self, time: str, text: str):
        self.time = time
        self.text = text

def read_srt(file_path: str) -> List[str]:
    """读取SRT文件，返回原始文本行列表"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.readlines()

def parse_srt(srt_lines: List[str]) -> List[SubtitleItem]:
    """解析SRT格式，返回结构化的字幕数据"""
    items = []
    idx = 0
    while idx < len(srt_lines):
        line = srt_lines[idx].strip()
        if line.isdigit():
            index = int(line)
            idx += 1
            if idx >= len(srt_lines): break
            time_line = srt_lines[idx].strip()
            if '-->' not in time_line:
                idx += 1
                continue
            start_time, end_time = [t.strip() for t in time_line.split('-->')]
            idx += 1
            text_lines = []
            while idx < len(srt_lines) and srt_lines[idx].strip() != '':
                text_lines.append(srt_lines[idx].strip())
                idx += 1
            text = ' '.join(text_lines)
            items.append(SubtitleItem(index, start_time, end_time, text))
        idx += 1
    return items

def convert_time_format(time_str: str) -> str:
    """
    将SRT时间格式转换为目标格式
    输入: "00:00:00,000" 
    输出: "hh:MM:ss"
    """
    h, m, s_ms = time_str.split(":")
    s = s_ms.split(",")[0]
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"


def merge_subtitles(subtitles: List[SubtitleItem], target_length: int = 500) -> List[MergedSegment]:
    """
    合并字幕文本到指定长度
    返回: 包含时间戳和合并文本的列表
    """
    segments = []
    buffer = []
    buffer_len = 0
    start_time = None
    for item in subtitles:
        if not buffer:
            start_time = convert_time_format(item.start_time)
        buffer.append(item.text)
        buffer_len += len(item.text)
        if buffer_len >= target_length:
            merged_text = ' '.join(buffer)
            segments.append(MergedSegment(start_time, merged_text))
            buffer = []
            buffer_len = 0
    if buffer:
        merged_text = ' '.join(buffer)
        segments.append(MergedSegment(start_time, merged_text))
    return segments

def format_output(segments: List[MergedSegment], titles: List[str]) -> str:
    """
    格式化输出
    返回: "hh:MM:ss 标题\n正文\n" 格式的字符串
    """
    lines = []
    for seg, title in zip(segments, titles):
        lines.append(f"{seg.time} {title}\n{seg.text}")
    return '\n\n'.join(lines)

# 主程序入口


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python main.py <srt文件路径>")
        sys.exit(1)
    file_path = sys.argv[1]
    # 1. 读取文件
    srt_lines = read_srt(file_path)
    # 2. 解析格式
    subtitles = parse_srt(srt_lines)
    # 3. 时间转换（合并时已用）
    # 4. 文本合并
    segments = merge_subtitles(subtitles, target_length=500)
    # 5. 格式化输出前，先生成标题
    merged_texts = [seg.text for seg in segments]
    titles = kimi_generate_titles(merged_texts)
    # 6. 校对正文
    print("[Kimi] 正在校对所有正文内容...")
    proofread_texts = kimi_proofread_segments(merged_texts)
    print("[Kimi] 所有正文校对完毕。\n")
    # 7. 输出：时间+标题+校对正文
    output = format_output([MergedSegment(seg.time, txt) for seg, txt in zip(segments, proofread_texts)], titles)
    print("\n[全部内容输出如下]\n")
    print(output)
    # 保存到以时间戳命名的txt文件
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    outname = f"kimi_output_{ts}.txt"
    with open(outname, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"\n[已保存到 {outname}]")