# -*- coding: utf-8 -*-
"""
手动下载 Chroma embedding 模型
"""

import os
import requests
import tarfile
import io
from pathlib import Path

MODEL_URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
CACHE_DIR = Path.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2"
MODEL_FILE = CACHE_DIR / "onnx.tar.gz"

def download_with_progress(url, dest_path):
    """带进度条的文件下载"""
    if dest_path.exists():
        file_size = dest_path.stat().st_size
        print(f"已存在模型文件，大小: {file_size / 1024 / 1024:.2f} MB")
        if file_size > 70 * 1024 * 1024:
            print("模型文件可能已下载完成，跳过下载")
            return True
    
    print(f"开始下载模型: {url}")
    print(f"保存到: {dest_path}")
    
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        chunk_size = 1024 * 1024
        
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r进度: {percent:.1f}% ({downloaded / 1024 / 1024:.1f} MB / {total_size / 1024 / 1024:.1f} MB)", end='')
        
        print(f"\n下载完成！文件大小: {dest_path.stat().st_size / 1024 / 1024:.2f} MB")
        return True
        
    except Exception as e:
        print(f"\n下载失败: {e}")
        return False

def extract_tar_gz(tar_path, extract_dir):
    """解压 tar.gz 文件"""
    print(f"开始解压: {tar_path}")
    
    try:
        with tarfile.open(tar_path, 'r:gz') as tar:
            tar.extractall(path=extract_dir)
        print("解压完成！")
        return True
    except Exception as e:
        print(f"解压失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_model():
    """验证模型文件"""
    print("\n验证模型文件...")
    
    required_files = [
        "tokenizer.json",
        "onnx/model.onnx",
        "config.json"
    ]
    
    for f in required_files:
        file_path = CACHE_DIR / f
        if file_path.exists():
            print(f"  [OK] {f}")
        else:
            print(f"  [缺失] {f}")
            return False
    
    print("模型验证通过！")
    return True

def main():
    print("=" * 60)
    print("Chroma Embedding 模型手动下载工具")
    print("=" * 60)
    
    if MODEL_FILE.exists():
        print(f"已存在: {MODEL_FILE}")
        print(f"文件大小: {MODEL_FILE.stat().st_size / 1024 / 1024:.2f} MB")
    
    print(f"\n缓存目录: {CACHE_DIR}")
    
    success = download_with_progress(MODEL_URL, MODEL_FILE)
    
    if success:
        print("\n" + "=" * 60)
        print("模型下载完成！")
        print("现在可以使用 Chroma 向量数据库了。")
        print("=" * 60)
    else:
        print("\n下载失败，请检查网络连接后重试。")

if __name__ == "__main__":
    main()
