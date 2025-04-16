import os
import json
import hashlib
import time
from typing import Dict, Any, Optional
import config


class CacheManager:
    """
    缓存管理器，用于存储和检索大模型请求的结果，避免重复请求
    """
    def __init__(self, cache_dir: str = None):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = cache_dir or os.path.join(config.DEFAULT_OUTPUT_DIR, "cache")
        # 确保缓存目录存在
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def generate_cache_key(self, file_path: str, mode: str, model: str) -> str:
        """
        根据文件路径和处理模式生成缓存键
        
        Args:
            file_path: 输入文件路径
            mode: 处理模式 (text 或 vl)
            model: 使用的模型名称
            
        Returns:
            str: 缓存键
        """
        # 获取文件修改时间，确保文件变化时缓存失效
        file_mtime = os.path.getmtime(file_path)
        
        # 使用文件路径、修改时间、模式和模型名称生成唯一标识
        cache_id = f"{file_path}|{file_mtime}|{mode}|{model}"
        return hashlib.md5(cache_id.encode()).hexdigest()
    
    def get_cache_path(self, cache_key: str) -> str:
        """
        获取缓存文件路径
        
        Args:
            cache_key: 缓存键
            
        Returns:
            str: 缓存文件路径
        """
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def has_cache(self, file_path: str, mode: str, model: str) -> bool:
        """
        检查是否存在对应的缓存
        
        Args:
            file_path: 输入文件路径
            mode: 处理模式
            model: 使用的模型名称
            
        Returns:
            bool: 是否存在缓存
        """
        if not os.path.exists(file_path):
            return False
            
        cache_key = self.generate_cache_key(file_path, mode, model)
        cache_path = self.get_cache_path(cache_key)
        
        return os.path.exists(cache_path)
    
    def save_cache(self, file_path: str, mode: str, model: str, data: Any) -> bool:
        """
        保存数据到缓存
        
        Args:
            file_path: 输入文件路径
            mode: 处理模式
            model: 使用的模型名称
            data: 要缓存的数据
            
        Returns:
            bool: 是否成功保存
        """
        try:
            cache_key = self.generate_cache_key(file_path, mode, model)
            cache_path = self.get_cache_path(cache_key)
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'file_path': file_path,
                    'mode': mode,
                    'model': model,
                    'timestamp': time.time(),
                    'data': data
                }, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"保存缓存失败: {e}")
            return False
    
    def load_cache(self, file_path: str, mode: str, model: str) -> Optional[Any]:
        """
        从缓存加载数据
        
        Args:
            file_path: 输入文件路径
            mode: 处理模式
            model: 使用的模型名称
            
        Returns:
            Optional[Any]: 缓存的数据，如果不存在则返回None
        """
        if not self.has_cache(file_path, mode, model):
            return None
        
        try:
            cache_key = self.generate_cache_key(file_path, mode, model)
            cache_path = self.get_cache_path(cache_key)
            
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            return cache_data['data']
        except Exception as e:
            print(f"加载缓存失败: {e}")
            return None
    
    def clear_cache(self, file_path: str = None, mode: str = None, model: str = None) -> int:
        """
        清除缓存
        
        Args:
            file_path: 输入文件路径，为None则忽略
            mode: 处理模式，为None则忽略
            model: 使用的模型名称，为None则忽略
            
        Returns:
            int: 清除的缓存数量
        """
        cleared_count = 0
        
        try:
            # 如果所有参数都为None，则清除所有缓存
            if file_path is None and mode is None and model is None:
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith('.json'):
                        os.remove(os.path.join(self.cache_dir, filename))
                        cleared_count += 1
                return cleared_count
            
            # 否则，遍历缓存文件，检查匹配条件
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    cache_path = os.path.join(self.cache_dir, filename)
                    
                    try:
                        with open(cache_path, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                        
                        # 检查是否满足删除条件
                        should_delete = True
                        
                        if file_path is not None and cache_data['file_path'] != file_path:
                            should_delete = False
                        
                        if mode is not None and cache_data['mode'] != mode:
                            should_delete = False
                        
                        if model is not None and cache_data['model'] != model:
                            should_delete = False
                        
                        if should_delete:
                            os.remove(cache_path)
                            cleared_count += 1
                    except:
                        # 如果读取失败，跳过该文件
                        continue
            
            return cleared_count
        except Exception as e:
            print(f"清除缓存失败: {e}")
            return cleared_count 