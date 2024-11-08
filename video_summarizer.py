import yt_dlp
import whisper
import requests
import os

def download_bilibili(url):
    """下载B站视频音频"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'temp_audio.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)
    return 'temp_audio.mp3'

def get_text_summary(text):
    """获取文本总结"""
    api_url = 'https://xiaoai.plus/v1/chat/completions'
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-j29yjWFosoZKE247028dD1F7961c49F59b78E6767b889d58"
    }
    
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "请用简洁的语言总结以下内容要点："},
            {"role": "user", "content": text}
        ]
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=data)
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"总结失败: {str(e)}"

def main():
    url = input("请输入B站视频链接：")
    
    try:
        # 1. 下载音频
        print("下载中...")
        audio_file = download_bilibili(url)
        print("下载完成！")
        
        # 2. 转文字
        print("转换文字中...")
        model = whisper.load_model("base")
        result = model.transcribe(audio_file)
        
        # 显示转换后的文字
        print("\n=========== 转换后的文字内容 ===========")
        print(result["text"])
        print("\n文字长度：", len(result["text"]))
        print("=======================================")
        
        # 确认是否继续
        if input("\n是否继续生成总结？(y/n): ").lower() != 'y':
            return
        
        # 3. 获取总结
        print("生成总结中...")
        summary = get_text_summary(result["text"])
        
        # 4. 输出结果
        print("\n=========== 视频内容总结 ===========")
        print(summary)
        print("===================================")
        
    except Exception as e:
        print(f"处理失败: {str(e)}")
    finally:
        # 清理临时文件
        if os.path.exists('temp_audio.mp3'):
            os.remove('temp_audio.mp3')

if __name__ == "__main__":
    main()