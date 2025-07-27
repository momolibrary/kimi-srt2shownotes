# Kimi 辅助将 SRT 转换为 Shownotes 工具

本项目是一个基于 Moonshot Kimi API 的 SRT 字幕处理工具，支持自动合并字幕、生成新闻式标题、智能校对文本，并输出格式化结果。
输入为标准格式的Srt文本文件
输出为带标题的Shownotes文本文件

## 功能简介
- **SRT 字幕解析**：读取并解析标准 SRT 字幕文件。
- **智能合并**：将字幕按指定长度500字左右合并为段落。
- **AI 标题生成**：为每个合并段落自动生成新闻风格标题。
- **AI 校对**：对每个段落正文进行智能校对，仅修正标点和错别字。
- **格式化输出**：输出“时间+标题+正文”格式的文本，并自动保存为 txt 文件。

## 使用方法
1. **安装依赖**
   
   需先安装 [openai](https://pypi.org/project/openai/) Python SDK：
   
   ```powershell
   pip install openai
   ```

2. **配置 API Key**
   
   在 `main.py` 中，将 `api_key="Your_api_key"` 替换为你自己的 Moonshot Kimi API Key。

3. **运行脚本**
   
   在命令行中运行：
   
   ```powershell
   python main.py <srt文件路径>
   ```
   
   例如：
   ```powershell
   python main.py example.srt
   ```

4. **输出说明**
   - 处理完成后，结果会输出到控制台，并自动保存为 `kimi_output_时间戳.txt` 文件。
   - 输出格式：
     ```
     hh:MM:ss 标题
     正文

     hh:MM:ss 标题
     正文
    ...
     ```

## 主要流程
1. 读取 SRT 文件
2. 解析为结构化字幕数据
3. 合并为指定长度的段落
4. 为每段生成标题
5. 校对每段正文
6. 输出并保存结果

## 注意事项
- API 有速率限制，脚本已自动处理。免费额度的RPM为3。
- 标题和校对均由 Kimi AI 生成，需保证 API Key 有足够额度。

## 依赖环境
- Python 3.7+
- openai >= 1.0.0

## 联系方式
如有问题或建议，请联系作者。
