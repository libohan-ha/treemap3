from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import whisper
import requests
import os
import threading
import uuid
from werkzeug.utils import secure_filename
import ffmpeg
import shutil
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
import io
from PIL import Image
import tempfile

app = Flask(__name__)

UPLOAD_FOLDER = '/tmp/uploads'
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'mp4', 'avi', 'mov', 'webm'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def download_youtube(url, filename):
    """下载YouTube视频音频"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'/tmp/temp_{filename}.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)
    return f'/tmp/temp_{filename}.mp3'

def get_text_summary(text):
    """获取文本总结（同时返回思维导图和文章格式）"""
    api_url = 'https://xiaoai.plus/v1/chat/completions'
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-wkJ8C4yXkzkXiwUm2e0322A6Bf254239824bC7D6F91a3468"
    }
    
    # 生成思维导图格式
    mindmap_data = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [
            {"role": "system", "content": """请将内容整理成markdown格式的思维导图，使用以下格式：

# 核心主题
## 主要观点1
### 要点1.1
### 要点1.2
## 主要观点2
### 要点2.1
### 要点2.2
## 主要观点3
### 要点3.1
### 要点3.2

注意事项：
1. 使用markdown标准的#、##、###来表示层级
2. 每个层级使用简短的关键词或短语
3. 确保结构清晰，层次分明
4. 最多使用3层层级
5. 使用中文标点符号"""},
            {"role": "user", "content": text}
        ]
    }
    mindmap_response = requests.post(api_url, headers=headers, json=mindmap_data)
    mindmap = mindmap_response.json()['choices'][0]['message']['content']
    
    # 新的文章格式提示词
    article_data = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [
            {"role": "system", "content": """角色设定：
你是一位拥有10年文案撰写经验的文案编辑，专门为小红书平台上【追求财富、个人成长和自律的25至30岁青年用户】量身定做内容。你需要根据提供的内容，撰写小红书文案，增强其吸引力和情感共鸣，激发用户的广泛互动。

技能要求：
1. 创建吸引人的标题
- 根据内容创建至少3个小红风格标题
- 标题需要内容相关且具有吸引力
- 每个标题都要包含合适的emoji表情

2. 结构化内容撰写
- 以吸引人的开头介绍话题背景信息
- 抛出问题引发思考
- 给出相应的解决方法
- 提供实际生活案例佐证
- 使用一、二、三、四等序号保持结构清晰
- 确保要点明确

3. 创作生活化、口语化的文案
- 使用幽默、比喻等创意元素
- 采用口语化表达方式
- 增强情感共鸣
- 使用贴近生活的例子

4. 限字文案创作
- 确保文案总字数在1000字以内
- 标题和内容都要简明扼要

5. 文案排版设计
- 段落清晰，结构有序
- 适当使用emoji表情
- 使文案生动有趣
- 重点内容要突出显示

输出格式：
【标题方案】
1. 第一个标题 emoji
2. 第二个标题 emoji
3. 第三个标题 emoji

【文案正文】
开篇引导...
一、...
二、...
三、...
总结互动...

#标签1 #标签2 #标签3"""},
            {"role": "user", "content": text}
        ]
    }
    article_response = requests.post(api_url, headers=headers, json=article_data)
    article = article_response.json()['choices'][0]['message']['content']
    
    return {
        "mindmap": mindmap,
        "article": article
    }

# 存储任务状态
tasks = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    urls = request.json.get('urls', [])
    if not urls:
        return jsonify({"error": "请提供至少一个YouTube URL"}), 400
    
    task_ids = []
    for url in urls:
        task_id = str(uuid.uuid4())
        task_ids.append(task_id)
        
        def process_video(url=url, task_id=task_id):
            try:
                # 1. 下载音频
                tasks[task_id] = {"status": "下载中...", "url": url}
                audio_file = download_youtube(url, task_id)
                
                # 2. 转文字
                tasks[task_id]["status"] = "转换文字中..."
                model = whisper.load_model("tiny")
                result = model.transcribe(audio_file)
                
                # 3. 获取总结
                tasks[task_id]["status"] = "生成总结中..."
                summary = get_text_summary(result["text"])
                
                tasks[task_id] = {
                    "status": "完成",
                    "url": url,
                    "result": summary["article"],
                    "mindmap": summary["mindmap"]
                }
                
            except Exception as e:
                tasks[task_id] = {
                    "status": "失败",
                    "url": url,
                    "result": str(e)
                }
            finally:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
        
        thread = threading.Thread(target=process_video)
        thread.start()
    
    return jsonify({"task_ids": task_ids})

@app.route('/status/<task_id>')
def status(task_id):
    if task_id in tasks:
        return jsonify({"data": tasks[task_id]})
    return jsonify({"error": "任务不存在"})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "没有文件"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "没有选择文件"}), 400
        
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            task_id = str(uuid.uuid4())
            
            # 确保上传目录存在
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            # 保存上传的文件
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}_{filename}")
            file_path = os.path.normpath(file_path)  # 规范化路径
            file.save(file_path)
            
            def process_file():
                try:
                    tasks[task_id] = {"status": "处理中...", "url": filename}
                    
                    # 处理音频
                    if filename.lower().endswith('.mp3'):
                        audio_file = file_path
                    else:
                        tasks[task_id]["status"] = "提取音频中..."
                        audio_file = extract_audio(file_path, task_id)
                    
                    # 转文字
                    tasks[task_id]["status"] = "转换文字中..."
                    model = whisper.load_model("tiny")
                    result = model.transcribe(audio_file)
                    
                    # 获取总结
                    tasks[task_id]["status"] = "生成总结中..."
                    summary = get_text_summary(result["text"])
                    
                    tasks[task_id] = {
                        "status": "完成",
                        "url": filename,
                        "result": summary["article"],
                        "mindmap": summary["mindmap"]
                    }
                    
                except Exception as e:
                    tasks[task_id] = {
                        "status": "失败",
                        "url": filename,
                        "result": str(e)
                    }
                finally:
                    # 清理临时文件
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        if 'audio_file' in locals() and audio_file != file_path:
                            if os.path.exists(audio_file):
                                os.remove(audio_file)
                    except Exception as e:
                        print('Error cleaning up files:', str(e))
            
            thread = threading.Thread(target=process_file)
            thread.start()
            
            return jsonify({"task_id": task_id})
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
    return jsonify({"error": "不支持的文件类型"}), 400

def extract_audio(video_path, task_id):
    """从视频文件提取音频"""
    try:
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}_audio.mp3")
        audio_path = os.path.normpath(audio_path)  # 规范化路径
        
        if video_path.lower().endswith('.mp3'):
            # 如果已经是 mp3 文件，直接复制
            shutil.copy2(video_path, audio_path)
        else:
            # 使用 ffmpeg 处理视频文件
            try:
                stream = ffmpeg.input(video_path)
                stream = ffmpeg.output(stream, audio_path, acodec='libmp3lame')
                ffmpeg.run(stream, overwrite_output=True, capture_stderr=True)
            except ffmpeg.Error as e:
                print('FFmpeg error:', e.stderr.decode() if e.stderr else str(e))
                raise
        
        return audio_path
    except Exception as e:
        print('Error in extract_audio:', str(e))
        raise

@app.route('/convert_svg_to_jpg', methods=['POST'])
def convert_svg_to_jpg():
    try:
        svg_data = request.data
        
        # 使用系统临时目录
        temp_dir = tempfile.gettempdir()
        temp_svg = os.path.join(temp_dir, f'temp_{uuid.uuid4()}.svg')
        temp_png = os.path.join(temp_dir, f'temp_{uuid.uuid4()}.png')
        
        try:
            print(f'Creating SVG file at: {temp_svg}')  # 调试信息
            # 写入 SVG 数据
            with open(temp_svg, 'wb') as f:
                f.write(svg_data)
            
            print('Converting SVG to PNG')  # 调试信息
            # 转换 SVG 到 PNG
            drawing = svg2rlg(temp_svg)
            renderPM.drawToFile(drawing, temp_png, fmt='PNG', dpi=300)
            
            print('Converting PNG to JPG')  # 调试信息
            # 使用 Pillow 转换为 JPG
            with Image.open(temp_png) as img:
                # 创建白色背景
                background = Image.new('RGB', img.size, 'white')
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[3])
                else:
                    background.paste(img)
                
                # 保存为 JPG
                output = io.BytesIO()
                background.save(output, format='JPEG', quality=95)
                output.seek(0)
                
                print('Sending file')  # 调试信息
                return send_file(
                    output,
                    mimetype='image/jpeg',
                    as_attachment=True,
                    download_name='mindmap.jpg'
                )
                
        finally:
            # 清理临时文件
            print('Cleaning up temporary files')  # 调试信息
            if os.path.exists(temp_svg):
                os.remove(temp_svg)
            if os.path.exists(temp_png):
                os.remove(temp_png)
                
    except Exception as e:
        print('Convert SVG to JPG error:', str(e))  # 详细的错误信息
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8080)