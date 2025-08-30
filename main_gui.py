import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import time
import datetime
import os
import configparser
from typing import List, Dict, Any
import traceback
import sys
import io

# 导入main.py中的功能函数
from main import (
    read_srt, parse_srt, merge_subtitles, convert_time_format,
    kimi_generate_titles, kimi_proofread_segments, format_output,
    SubtitleItem, MergedSegment, load_config
)


class CancellableKimiWrapper:
    """可取消的Kimi API包装器"""
    def __init__(self, cancel_flag, event_queue):
        self.cancel_flag = cancel_flag
        self.event_queue = event_queue
    
    def generate_titles_with_progress(self, text_list):
        """带进度显示和取消支持的标题生成"""
        titles = []
        total = len(text_list)
        
        for idx, text in enumerate(text_list):
            if self.cancel_flag.is_set():
                return None
            
            self.event_queue.put({
                "type": "step_progress", 
                "name": "titles", 
                "current": idx + 1, 
                "total": total
            })
            
            # 调用单个文本的标题生成（模拟原始函数的单步调用）
            try:
                single_title = self._generate_single_title(text)
                titles.append(single_title)
                
                self.event_queue.put({
                    "type": "title_generated", 
                    "index": idx, 
                    "title": single_title
                })
            except Exception as e:
                self.event_queue.put({"type": "log", "message": f"第{idx+1}段标题生成失败: {e}"})
                titles.append(f"标题{idx+1}")
        
        return titles
    
    def proofread_segments_with_progress(self, text_list):
        """带进度显示和取消支持的正文校对"""
        proofread = []
        total = len(text_list)
        
        for idx, text in enumerate(text_list):
            if self.cancel_flag.is_set():
                return None
            
            self.event_queue.put({
                "type": "step_progress", 
                "name": "proofread", 
                "current": idx + 1, 
                "total": total
            })
            
            try:
                single_proofread = self._proofread_single_text(text)
                proofread.append(single_proofread)
                
                self.event_queue.put({
                    "type": "proofread_generated", 
                    "index": idx, 
                    "text": single_proofread
                })
            except Exception as e:
                self.event_queue.put({"type": "log", "message": f"第{idx+1}段正文校对失败: {e}"})
                proofread.append(text)  # 保持原文
        
        return proofread
    
    def _generate_single_title(self, text):
        """生成单个标题（调用真实API）"""
        try:
            # 动态创建client
            from openai import OpenAI
            import configparser
            
            # 重新读取配置以确保使用最新设置
            config = configparser.ConfigParser()
            if os.path.exists("kimi_config.ini"):
                config.read("kimi_config.ini", encoding="utf-8")
                if "kimi" in config:
                    section = config["kimi"]
                    api_key = section.get("api_key", "")
                    base_url = section.get("base_url", "https://api.moonshot.cn/v1")
                    model_name = section.get("model", "moonshot-v1-8k")
                else:
                    raise Exception("配置文件中未找到[kimi]段")
            else:
                raise Exception("配置文件kimi_config.ini不存在")
            
            if not api_key:
                raise Exception("API Key未设置")
            
            client = OpenAI(api_key=api_key, base_url=base_url)
            
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
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "你是 Kimi，由 Moonshot AI 提供的人工智能助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.6,
                )
            
            # 使用重试机制
            import time
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    completion = call()
                    title = completion.choices[0].message.content.strip().split('\n')[0].strip()
                    return title
                except Exception as e:
                    if hasattr(e, 'status_code') and e.status_code == 429:
                        self.event_queue.put({"type": "log", "message": f"API限流，等待重试... ({retry_count+1}/{max_retries})"})
                        time.sleep(1.2)
                        retry_count += 1
                    else:
                        raise e
            
            raise Exception("API调用重试次数超限")
            
        except Exception as e:
            self.event_queue.put({"type": "log", "message": f"标题生成API调用失败: {e}"})
            # 使用简单的标题生成逻辑作为备选
            if "技术" in text or "科技" in text:
                return "科技发展新动态"
            elif "经济" in text or "市场" in text:
                return "经济市场分析" 
            elif "教育" in text or "学习" in text:
                return "教育学习话题"
            else:
                import random
                return f"内容摘要{random.randint(1, 999)}"
    
    def _proofread_single_text(self, text):
        """校对单个文本（调用真实API）"""
        try:
            # 动态创建client
            from openai import OpenAI
            import configparser
            
            # 重新读取配置以确保使用最新设置
            config = configparser.ConfigParser()
            if os.path.exists("kimi_config.ini"):
                config.read("kimi_config.ini", encoding="utf-8")
                if "kimi" in config:
                    section = config["kimi"]
                    api_key = section.get("api_key", "")
                    base_url = section.get("base_url", "https://api.moonshot.cn/v1")
                    model_name = section.get("model", "moonshot-v1-8k")
                else:
                    raise Exception("配置文件中未找到[kimi]段")
            else:
                raise Exception("配置文件kimi_config.ini不存在")
            
            if not api_key:
                raise Exception("API Key未设置")
            
            client = OpenAI(api_key=api_key, base_url=base_url)
            
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
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "你是 Kimi，由 Moonshot AI 提供的人工智能助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.6,
                )
            
            # 使用重试机制
            import time
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    completion = call()
                    proofread_text = completion.choices[0].message.content.strip().split('\n')[0].strip()
                    return proofread_text
                except Exception as e:
                    if hasattr(e, 'status_code') and e.status_code == 429:
                        self.event_queue.put({"type": "log", "message": f"校对API限流，等待重试... ({retry_count+1}/{max_retries})"})
                        time.sleep(1.2)
                        retry_count += 1
                    else:
                        raise e
            
            raise Exception("校对API调用重试次数超限")
            
        except Exception as e:
            self.event_queue.put({"type": "log", "message": f"校对API调用失败: {e}"})
            # 简单的校对逻辑作为备选：添加标点符号
            result = text.strip()
            if not result.endswith(('。', '！', '？')):
                result += '。'
            return result


class LogCapture:
    """捕获print输出并重定向到GUI"""
    def __init__(self, event_queue):
        self.event_queue = event_queue
        self.original_stdout = sys.stdout
        
    def write(self, text):
        if text.strip():  # 只记录非空内容
            self.event_queue.put({"type": "log", "message": text.strip()})
        
    def flush(self):
        pass
    
    def __enter__(self):
        sys.stdout = self
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.original_stdout


class MainWindow:
    """SRT ShowNotes 助手主窗口"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SRT ShowNotes 助手")
        self.root.geometry("1000x700")
        
        # --- 状态管理 ---
        self.cancel_flag = threading.Event()
        self.is_running = False
        self.start_time = None
        self.event_queue = queue.Queue()
        
        # --- 数据存储 ---
        self.segments_data = []  # 处理后的段落数据
        self.output_dir = os.getcwd()
        
        # --- 配置变量 ---
        self.srt_file_path = tk.StringVar()
        self.target_length = tk.IntVar(value=500)
        self.enable_titles = tk.BooleanVar(value=True)
        self.enable_proofread = tk.BooleanVar(value=True)
        self.api_key = tk.StringVar()
        self.base_url = tk.StringVar(value="https://api.moonshot.cn/v1")
        self.model_name = tk.StringVar(value="moonshot-v1-8k")
        self.output_dir_var = tk.StringVar(value=self.output_dir)
        
        # 尝试加载现有配置
        self.load_config()
        
        # --- 构建界面 ---
        self.create_widgets()
        
        # --- 启动事件轮询 ---
        self.poll_events()
    
    def load_config(self):
        """加载配置文件"""
        try:
            config = configparser.ConfigParser()
            if os.path.exists("kimi_config.ini"):
                config.read("kimi_config.ini", encoding="utf-8")
                if "kimi" in config:
                    section = config["kimi"]
                    self.api_key.set(section.get("api_key", ""))
                    self.base_url.set(section.get("base_url", "https://api.moonshot.cn/v1"))
                    self.model_name.set(section.get("model", "moonshot-v1-8k"))
        except Exception as e:
            print(f"加载配置文件失败: {e}")
    
    def save_config(self):
        """保存配置文件"""
        try:
            config = configparser.ConfigParser()
            config["kimi"] = {
                "api_key": self.api_key.get(),
                "base_url": self.base_url.get(),
                "model": self.model_name.get()
            }
            with open("kimi_config.ini", "w", encoding="utf-8") as f:
                config.write(f)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def create_widgets(self):
        """创建界面组件"""
        # --- 主框架 ---
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # --- 左侧配置面板 ---
        left_frame = ttk.LabelFrame(main_frame, text="配置面板", width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_frame.pack_propagate(False)
        
        self.create_config_panel(left_frame)
        
        # --- 右侧主要区域 ---
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # --- Notebook标签页 ---
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        self.create_notebook_tabs()
        
        # --- 底部状态栏 ---
        self.create_status_bar(right_frame)
    
    def create_config_panel(self, parent):
        """创建左侧配置面板"""
        # --- 文件选择 ---
        file_frame = ttk.LabelFrame(parent, text="文件设置")
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(file_frame, text="SRT文件:").pack(anchor=tk.W, padx=5, pady=2)
        file_select_frame = ttk.Frame(file_frame)
        file_select_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.file_label = ttk.Label(file_select_frame, textvariable=self.srt_file_path, 
                                   background="white", relief="sunken", width=25)
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(file_select_frame, text="浏览", command=self.browse_srt_file, 
                  width=8).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 输出目录
        ttk.Label(file_frame, text="输出目录:").pack(anchor=tk.W, padx=5, pady=(10, 2))
        output_frame = ttk.Frame(file_frame)
        output_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Entry(output_frame, textvariable=self.output_dir_var, width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(output_frame, text="浏览", command=self.browse_output_dir, 
                  width=8).pack(side=tk.RIGHT, padx=(5, 0))
        
        # --- 处理设置 ---
        process_frame = ttk.LabelFrame(parent, text="处理设置")
        process_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(process_frame, text="目标合并长度:").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Entry(process_frame, textvariable=self.target_length, width=20).pack(padx=5, pady=2)
        
        ttk.Checkbutton(process_frame, text="生成标题", variable=self.enable_titles).pack(anchor=tk.W, padx=5, pady=2)
        ttk.Checkbutton(process_frame, text="校对正文", variable=self.enable_proofread).pack(anchor=tk.W, padx=5, pady=2)
        
        # --- API配置 ---
        api_frame = ttk.LabelFrame(parent, text="API配置")
        api_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(api_frame, text="API Key:").pack(anchor=tk.W, padx=5, pady=2)
        self.api_key_entry = ttk.Entry(api_frame, textvariable=self.api_key, show="*", width=20)
        self.api_key_entry.pack(padx=5, pady=2)
        
        ttk.Label(api_frame, text="Base URL:").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Entry(api_frame, textvariable=self.base_url, width=20).pack(padx=5, pady=2)
        
        ttk.Label(api_frame, text="模型:").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Entry(api_frame, textvariable=self.model_name, width=20).pack(padx=5, pady=2)
        
        # 显示/隐藏API Key按钮
        show_key_frame = ttk.Frame(api_frame)
        show_key_frame.pack(padx=5, pady=2)
        
        self.show_key_var = tk.BooleanVar()
        ttk.Checkbutton(show_key_frame, text="显示API Key", variable=self.show_key_var, 
                       command=self.toggle_api_key_visibility).pack(side=tk.LEFT)
        
        ttk.Button(show_key_frame, text="保存配置", command=self.save_config).pack(side=tk.RIGHT)
        
        # --- 控制按钮 ---
        control_frame = ttk.LabelFrame(parent, text="操作控制")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="开始处理", command=self.start_processing)
        self.start_button.pack(fill=tk.X, padx=5, pady=2)
        
        self.cancel_button = ttk.Button(control_frame, text="取消任务", command=self.cancel_processing, state=tk.DISABLED)
        self.cancel_button.pack(fill=tk.X, padx=5, pady=2)
        
        # --- 进度显示 ---
        progress_frame = ttk.LabelFrame(parent, text="任务进度")
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=5, pady=2)
        
        self.status_text = tk.StringVar(value="就绪")
        ttk.Label(progress_frame, textvariable=self.status_text).pack(padx=5, pady=2)
    
    def create_notebook_tabs(self):
        """创建标签页"""
        # --- Progress标签 ---
        self.progress_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.progress_frame, text="进度")
        
        self.progress_listbox = tk.Listbox(self.progress_frame)
        progress_scroll = ttk.Scrollbar(self.progress_frame, orient=tk.VERTICAL, command=self.progress_listbox.yview)
        self.progress_listbox.config(yscrollcommand=progress_scroll.set)
        self.progress_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        progress_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # --- Segments标签 ---
        self.segments_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.segments_frame, text="段落编辑")
        
        # 添加按钮框架
        segments_button_frame = ttk.Frame(self.segments_frame)
        segments_button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(segments_button_frame, text="更新预览", command=self.update_preview).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(segments_button_frame, text="重置所有", command=self.reset_segments).pack(side=tk.LEFT)
        
        # 段落编辑区域
        self.segments_canvas = tk.Canvas(self.segments_frame)
        segments_scrollbar = ttk.Scrollbar(self.segments_frame, orient=tk.VERTICAL, command=self.segments_canvas.yview)
        self.segments_scrollable_frame = ttk.Frame(self.segments_canvas)
        
        self.segments_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.segments_canvas.configure(scrollregion=self.segments_canvas.bbox("all"))
        )
        
        self.segments_canvas.create_window((0, 0), window=self.segments_scrollable_frame, anchor="nw")
        self.segments_canvas.configure(yscrollcommand=segments_scrollbar.set)
        
        self.segments_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        segments_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # --- Preview标签 ---
        self.preview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.preview_frame, text="预览")
        
        preview_button_frame = ttk.Frame(self.preview_frame)
        preview_button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(preview_button_frame, text="复制到剪贴板", command=self.copy_to_clipboard).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(preview_button_frame, text="导出文件", command=self.export_file).pack(side=tk.LEFT)
        
        self.preview_text = tk.Text(self.preview_frame, wrap=tk.WORD, state=tk.DISABLED)
        preview_scroll = ttk.Scrollbar(self.preview_frame, orient=tk.VERTICAL, command=self.preview_text.yview)
        self.preview_text.config(yscrollcommand=preview_scroll.set)
        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # --- Logs标签 ---
        self.logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_frame, text="日志")
        
        self.logs_text = tk.Text(self.logs_frame, wrap=tk.WORD, state=tk.DISABLED)
        logs_scroll = ttk.Scrollbar(self.logs_frame, orient=tk.VERTICAL, command=self.logs_text.yview)
        self.logs_text.config(yscrollcommand=logs_scroll.set)
        self.logs_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        logs_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_status_bar(self, parent):
        """创建底部状态栏"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X)
        
        self.status_label = ttk.Label(status_frame, text="就绪")
        self.status_label.pack(side=tk.LEFT)
        
        self.time_label = ttk.Label(status_frame, text="")
        self.time_label.pack(side=tk.RIGHT)
    
    def toggle_api_key_visibility(self):
        """切换API Key显示/隐藏"""
        if self.show_key_var.get():
            self.api_key_entry.config(show="")
        else:
            self.api_key_entry.config(show="*")
    
    def browse_srt_file(self):
        """浏览选择SRT文件"""
        file_path = filedialog.askopenfilename(
            title="选择SRT文件",
            filetypes=[("SRT files", "*.srt"), ("All files", "*.*")]
        )
        if file_path:
            self.srt_file_path.set(file_path)
    
    def browse_output_dir(self):
        """浏览选择输出目录"""
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.output_dir_var.set(dir_path)
            self.output_dir = dir_path
    
    def add_log(self, message: str):
        """添加日志消息"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.insert(tk.END, log_message)
        self.logs_text.see(tk.END)
        self.logs_text.config(state=tk.DISABLED)
    
    def add_progress_step(self, step: str):
        """添加进度步骤"""
        self.progress_listbox.insert(tk.END, step)
        self.progress_listbox.see(tk.END)
    
    def update_segments_display(self):
        """更新段落编辑显示"""
        # 清空现有组件
        for widget in self.segments_scrollable_frame.winfo_children():
            widget.destroy()
        
        if not self.segments_data:
            ttk.Label(self.segments_scrollable_frame, text="暂无数据").pack(pady=20)
            return
        
        for i, segment in enumerate(self.segments_data):
            # 段落框架
            segment_frame = ttk.LabelFrame(self.segments_scrollable_frame, text=f"段落 {i+1} - {segment['time']}")
            segment_frame.pack(fill=tk.X, padx=5, pady=5)
            
            # 标题编辑
            ttk.Label(segment_frame, text="标题:").pack(anchor=tk.W, padx=5, pady=2)
            title_entry = ttk.Entry(segment_frame, width=50)
            title_entry.pack(fill=tk.X, padx=5, pady=2)
            title_entry.insert(0, segment.get('title', ''))
            segment['title_widget'] = title_entry
            
            # 正文编辑
            ttk.Label(segment_frame, text="正文:").pack(anchor=tk.W, padx=5, pady=(10, 2))
            text_widget = tk.Text(segment_frame, height=3, wrap=tk.WORD)
            text_widget.pack(fill=tk.X, padx=5, pady=2)
            text_widget.insert(tk.END, segment.get('text', ''))
            segment['text_widget'] = text_widget
    
    def update_preview(self):
        """更新预览内容"""
        if not self.segments_data:
            return
        
        # 收集用户编辑后的数据
        for segment in self.segments_data:
            if 'title_widget' in segment:
                segment['title'] = segment['title_widget'].get()
            if 'text_widget' in segment:
                segment['text'] = segment['text_widget'].get(1.0, tk.END).strip()
        
        # 生成预览文本
        lines = []
        for segment in self.segments_data:
            title = segment.get('title', '')
            text = segment.get('text', '')
            time_str = segment.get('time', '')
            lines.append(f"{time_str} {title}\n{text}")
        
        preview_content = '\n\n'.join(lines)
        
        # 更新预览显示
        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(1.0, preview_content)
        self.preview_text.config(state=tk.DISABLED)
    
    def reset_segments(self):
        """重置所有段落到原始状态"""
        if not self.segments_data:
            return
        
        for segment in self.segments_data:
            if 'title_widget' in segment:
                segment['title_widget'].delete(0, tk.END)
                segment['title_widget'].insert(0, segment.get('original_title', ''))
            if 'text_widget' in segment:
                segment['text_widget'].delete(1.0, tk.END)
                segment['text_widget'].insert(1.0, segment.get('original_text', ''))
    
    def copy_to_clipboard(self):
        """复制预览内容到剪贴板"""
        content = self.preview_text.get(1.0, tk.END)
        if content.strip():
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("成功", "内容已复制到剪贴板")
    
    def export_file(self):
        """导出文件"""
        content = self.preview_text.get(1.0, tk.END)
        if not content.strip():
            messagebox.showwarning("警告", "没有内容可导出")
            return
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"kimi_output_{timestamp}.txt"
        
        file_path = filedialog.asksaveasfilename(
            title="导出文件",
            defaultextension=".txt",
            initialname=default_name,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("成功", f"文件已保存到: {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"保存文件失败: {e}")
    
    def start_processing(self):
        """开始处理"""
        # 验证输入
        if not self.srt_file_path.get():
            messagebox.showwarning("警告", "请选择SRT文件")
            return
        
        if not os.path.exists(self.srt_file_path.get()):
            messagebox.showerror("错误", "SRT文件不存在")
            return
        
        if not self.api_key.get():
            messagebox.showwarning("警告", "请输入API Key")
            return
        
        # 重置状态
        self.cancel_flag.clear()
        self.is_running = True
        self.start_time = time.time()
        
        # 清空之前的数据
        self.segments_data = []
        self.progress_listbox.delete(0, tk.END)
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.delete(1.0, tk.END)
        self.logs_text.config(state=tk.DISABLED)
        
        # 更新界面状态
        self.start_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.status_text.set("处理中...")
        self.progress_var.set(0)
        
        # 保存配置
        self.save_config()
        
        # 启动后台线程
        worker_thread = threading.Thread(target=self.worker_thread, daemon=True)
        worker_thread.start()
        
        self.add_log("开始处理任务")
    
    def cancel_processing(self):
        """取消处理"""
        self.cancel_flag.set()
        self.add_log("用户请求取消任务")
    
    def worker_thread(self):
        """后台工作线程"""
        try:
            # 设置print输出重定向
            with LogCapture(self.event_queue):
                # 步骤1: 读取SRT文件
                self.send_event({"type": "step_start", "name": "read_file"})
                srt_lines = read_srt(self.srt_file_path.get())
                
                if self.cancel_flag.is_set():
                    self.send_event({"type": "cancelled"})
                    return
                
                # 步骤2: 解析SRT
                self.send_event({"type": "step_start", "name": "parse_srt"})
                subtitles = parse_srt(srt_lines)
                
                if self.cancel_flag.is_set():
                    self.send_event({"type": "cancelled"})
                    return
                
                # 步骤3: 合并字幕
                self.send_event({"type": "step_start", "name": "merge_subtitles"})
                segments = merge_subtitles(subtitles, self.target_length.get())
                merged_texts = [seg.text for seg in segments]
                
                if self.cancel_flag.is_set():
                    self.send_event({"type": "cancelled"})
                    return
                
                # 初始化段落数据
                segments_data = []
                for i, segment in enumerate(segments):
                    segments_data.append({
                        'index': i,
                        'time': segment.time,
                        'text': segment.text,
                        'title': f"段落{i+1}",
                        'original_text': segment.text,
                        'original_title': f"段落{i+1}"
                    })
                
                self.send_event({"type": "segments_ready", "segments": segments_data})
                
                # 步骤4: 生成标题（如果启用）
                if self.enable_titles.get():
                    self.send_event({"type": "step_start", "name": "generate_titles"})
                    
                    try:
                        # 使用可取消的包装器
                        wrapper = CancellableKimiWrapper(self.cancel_flag, self.event_queue)
                        titles = wrapper.generate_titles_with_progress(merged_texts)
                        
                        if titles is None:  # 被取消
                            self.send_event({"type": "cancelled"})
                            return
                        
                        # 更新segments_data中的标题
                        for i, title in enumerate(titles):
                            if i < len(segments_data):
                                segments_data[i]['title'] = title
                                segments_data[i]['original_title'] = title
                                
                    except Exception as e:
                        self.send_event({"type": "log", "message": f"标题生成失败: {e}"})
                        # 使用默认标题
                        for i in range(len(segments_data)):
                            segments_data[i]['title'] = f"段落{i+1}"
                            segments_data[i]['original_title'] = f"段落{i+1}"
                
                # 步骤5: 校对正文（如果启用）
                if self.enable_proofread.get():
                    self.send_event({"type": "step_start", "name": "proofread"})
                    
                    try:
                        # 使用可取消的包装器
                        wrapper = CancellableKimiWrapper(self.cancel_flag, self.event_queue)
                        proofread_texts = wrapper.proofread_segments_with_progress(merged_texts)
                        
                        if proofread_texts is None:  # 被取消
                            self.send_event({"type": "cancelled"})
                            return
                        
                        # 更新segments_data中的正文
                        for i, proofread_text in enumerate(proofread_texts):
                            if i < len(segments_data):
                                segments_data[i]['text'] = proofread_text
                                
                    except Exception as e:
                        self.send_event({"type": "log", "message": f"正文校对失败: {e}"})
                        # 保持原始正文
                
                # 完成
                if not self.cancel_flag.is_set():
                    # 生成输出文件
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_path = os.path.join(self.output_dir, f"kimi_output_{timestamp}.txt")
                    
                    # 格式化输出
                    lines = []
                    for segment in segments_data:
                        title = segment['title']
                        text = segment['text']
                        time_str = segment['time']
                        lines.append(f"{time_str} {title}\n{text}")
                    
                    output_content = '\n\n'.join(lines)
                    
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(output_content)
                    
                    self.send_event({
                        "type": "completed", 
                        "segments": segments_data,
                        "output_path": output_path
                    })
        
        except Exception as e:
            error_msg = f"处理过程中发生错误: {str(e)}"
            self.send_event({
                "type": "error", 
                "message": error_msg,
                "traceback": traceback.format_exc()
            })
    
    def send_event(self, event: Dict[str, Any]):
        """发送事件到主线程"""
        self.event_queue.put(event)
    
    def poll_events(self):
        """轮询事件队列"""
        try:
            while True:
                event = self.event_queue.get_nowait()
                self.handle_event(event)
        except queue.Empty:
            pass
        
        # 更新时间显示
        if self.is_running and self.start_time:
            elapsed = time.time() - self.start_time
            self.time_label.config(text=f"已运行: {int(elapsed)}秒")
        
        # 继续轮询
        self.root.after(150, self.poll_events)
    
    def handle_event(self, event: Dict[str, Any]):
        """处理事件"""
        event_type = event.get("type")
        
        if event_type == "step_start":
            step_name = event.get("name")
            step_map = {
                "read_file": "读取SRT文件",
                "parse_srt": "解析SRT格式",
                "merge_subtitles": "合并字幕段落",
                "generate_titles": "生成标题",
                "proofread": "校对正文"
            }
            step_text = step_map.get(step_name, step_name)
            self.add_progress_step(f"开始: {step_text}")
            self.add_log(f"开始步骤: {step_text}")
            
        elif event_type == "step_progress":
            name = event.get("name")
            current = event.get("current")
            total = event.get("total")
            progress = (current / total) * 100
            self.progress_var.set(progress)
            self.add_log(f"{name}: {current}/{total}")
            
        elif event_type == "segments_ready":
            self.segments_data = event.get("segments", [])
            self.update_segments_display()
            self.add_log(f"段落数据准备完成，共{len(self.segments_data)}段")
            
        elif event_type == "title_generated":
            index = event.get("index")
            title = event.get("title")
            self.add_log(f"第{index+1}段标题生成: {title}")
            
        elif event_type == "proofread_generated":
            index = event.get("index")
            self.add_log(f"第{index+1}段正文校对完成")
            
        elif event_type == "completed":
            self.segments_data = event.get("segments", [])
            output_path = event.get("output_path", "")
            
            self.update_segments_display()
            self.update_preview()
            
            self.add_progress_step("任务完成")
            self.add_log(f"任务完成，文件已保存: {output_path}")
            
            self.finish_processing()
            messagebox.showinfo("完成", f"任务已完成！\n文件保存到: {output_path}")
            
        elif event_type == "error":
            message = event.get("message", "未知错误")
            traceback_info = event.get("traceback", "")
            
            self.add_log(f"错误: {message}")
            if traceback_info:
                self.add_log(f"详细信息: {traceback_info}")
            
            self.finish_processing()
            messagebox.showerror("错误", message)
            
        elif event_type == "cancelled":
            self.add_progress_step("任务已取消")
            self.add_log("任务已被用户取消")
            self.finish_processing()
            
        elif event_type == "log":
            message = event.get("message", "")
            self.add_log(message)
    
    def finish_processing(self):
        """完成处理，恢复界面状态"""
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        self.status_text.set("就绪")
        self.progress_var.set(0)
        
        if self.start_time:
            elapsed = time.time() - self.start_time
            self.time_label.config(text=f"总耗时: {int(elapsed)}秒")
    
    def run(self):
        """运行应用"""
        self.root.mainloop()


if __name__ == "__main__":
    app = MainWindow()
    app.run()
