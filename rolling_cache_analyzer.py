#!/usr/bin/env python3
"""
MSFS2024 RollingCache 分析工具
分析 ROLLINGCACHE-*.CCC 文件的结构和内容差异
"""

import os
import struct
import hashlib
from typing import Dict, List, Tuple, Optional
import argparse


class RollingCacheAnalyzer:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_size = os.path.getsize(file_path)
        self.chunk_size = 1024 * 1024  # 1MB chunks for analysis
        
    def read_header(self, size: int = 1024) -> bytes:
        """读取文件头部"""
        with open(self.file_path, 'rb') as f:
            return f.read(size)
    
    def read_footer(self, size: int = 1024) -> bytes:
        """读取文件尾部"""
        with open(self.file_path, 'rb') as f:
            f.seek(-size, 2)  # 从文件末尾往前seek
            return f.read(size)
    
    def find_non_zero_regions(self, max_regions: int = 100) -> List[Tuple[int, int]]:
        """找到非零数据区域"""
        regions = []
        current_start = None
        
        with open(self.file_path, 'rb') as f:
            position = 0
            while position < self.file_size and len(regions) < max_regions:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                
                # 检查chunk是否包含非零数据
                has_data = any(b != 0 for b in chunk)
                
                if has_data and current_start is None:
                    current_start = position
                elif not has_data and current_start is not None:
                    regions.append((current_start, position))
                    current_start = None
                
                position += len(chunk)
            
            # 如果文件结束时还在一个数据区域中
            if current_start is not None:
                regions.append((current_start, self.file_size))
        
        return regions
    
    def calculate_hash_sections(self, num_sections: int = 16) -> List[str]:
        """计算文件不同部分的哈希值"""
        section_size = self.file_size // num_sections
        hashes = []
        
        with open(self.file_path, 'rb') as f:
            for i in range(num_sections):
                f.seek(i * section_size)
                data = f.read(section_size)
                hash_value = hashlib.md5(data).hexdigest()
                hashes.append(hash_value)
        
        return hashes
    
    def analyze_structure(self) -> Dict:
        """分析文件结构"""
        print(f"分析文件: {os.path.basename(self.file_path)}")
        print(f"文件大小: {self.file_size:,} bytes ({self.file_size / (1024**3):.2f} GB)")
        
        # 读取文件头
        header = self.read_header(1024)
        print(f"文件头 (前64字节): {header[:64].hex()}")
        
        # 检查是否有特定的文件标识
        if len(header) >= 4:
            magic = struct.unpack('<I', header[:4])[0]
            print(f"可能的Magic Number: 0x{magic:08X}")
        
        # 找到非零区域
        print("查找非零数据区域...")
        non_zero_regions = self.find_non_zero_regions()
        print(f"找到 {len(non_zero_regions)} 个非零数据区域:")
        
        total_data_size = 0
        for i, (start, end) in enumerate(non_zero_regions[:10]):  # 只显示前10个
            size = end - start
            total_data_size += size
            print(f"  区域 {i+1}: 0x{start:08X} - 0x{end:08X} (大小: {size:,} bytes)")
        
        if len(non_zero_regions) > 10:
            print(f"  ... 还有 {len(non_zero_regions) - 10} 个区域")
        
        print(f"总数据大小: {total_data_size:,} bytes ({total_data_size / self.file_size * 100:.2f}%)")
        
        # 计算各部分哈希
        print("计算文件各部分哈希值...")
        hashes = self.calculate_hash_sections()
        
        return {
            'file_path': self.file_path,
            'file_size': self.file_size,
            'header': header,
            'non_zero_regions': non_zero_regions,
            'section_hashes': hashes,
            'total_data_size': total_data_size
        }


def compare_files(file_analyses: List[Dict]):
    """比较多个文件的分析结果"""
    print("\n" + "="*80)
    print("文件比较分析")
    print("="*80)
    
    # 比较文件头
    print("\n文件头比较 (前32字节):")
    for analysis in file_analyses:
        name = os.path.basename(analysis['file_path'])
        header_hex = analysis['header'][:32].hex()
        print(f"{name:30}: {header_hex}")
    
    # 比较数据密度
    print("\n数据密度比较:")
    for analysis in file_analyses:
        name = os.path.basename(analysis['file_path'])
        density = analysis['total_data_size'] / analysis['file_size'] * 100
        regions = len(analysis['non_zero_regions'])
        print(f"{name:30}: {density:6.2f}% ({regions} 个数据区域)")
    
    # 比较哈希值差异
    print("\n哈希值差异分析:")
    if len(file_analyses) >= 2:
        base_hashes = file_analyses[0]['section_hashes']
        base_name = os.path.basename(file_analyses[0]['file_path'])
        
        for i, analysis in enumerate(file_analyses[1:], 1):
            compare_name = os.path.basename(analysis['file_path'])
            compare_hashes = analysis['section_hashes']
            
            different_sections = []
            for j, (base_hash, comp_hash) in enumerate(zip(base_hashes, compare_hashes)):
                if base_hash != comp_hash:
                    different_sections.append(j)
            
            print(f"{base_name} vs {compare_name}:")
            print(f"  不同的区块: {len(different_sections)}/{len(base_hashes)}")
            if different_sections:
                print(f"  不同区块索引: {different_sections[:10]}{'...' if len(different_sections) > 10 else ''}")


def analyze_cache_structure(file_path: str):
    """深入分析缓存结构"""
    print(f"\n深入分析缓存结构: {os.path.basename(file_path)}")
    print("-" * 50)
    
    with open(file_path, 'rb') as f:
        # 尝试解析可能的头部结构
        header_data = f.read(512)
        
        # 查找可能的结构模式
        print("搜索可能的结构模式...")
        
        # 检查是否有重复的模式或块大小标识
        f.seek(0)
        chunk_size = 4096  # 4KB chunks
        pattern_counts = {}
        
        for i in range(min(1000, os.path.getsize(file_path) // chunk_size)):
            chunk = f.read(chunk_size)
            if len(chunk) < chunk_size:
                break
                
            # 查找重复的4字节模式
            for j in range(0, len(chunk) - 4, 4):
                pattern = chunk[j:j+4]
                if pattern != b'\x00\x00\x00\x00':
                    pattern_hex = pattern.hex()
                    pattern_counts[pattern_hex] = pattern_counts.get(pattern_hex, 0) + 1
        
        # 显示最常见的模式
        if pattern_counts:
            print("最常见的非零4字节模式:")
            sorted_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)
            for pattern, count in sorted_patterns[:10]:
                print(f"  {pattern}: {count} 次")


def main():
    parser = argparse.ArgumentParser(description='MSFS2024 RollingCache 分析工具')
    parser.add_argument('files', nargs='+', help='要分析的 CCC 文件路径')
    parser.add_argument('--deep', action='store_true', help='执行深入的结构分析')
    
    args = parser.parse_args()
    
    # 分析每个文件
    analyses = []
    for file_path in args.files:
        if not os.path.exists(file_path):
            print(f"错误: 文件不存在 - {file_path}")
            continue
            
        analyzer = RollingCacheAnalyzer(file_path)
        analysis = analyzer.analyze_structure()
        analyses.append(analysis)
        
        if args.deep:
            analyze_cache_structure(file_path)
        
        print("\n" + "-"*80 + "\n")
    
    # 比较文件
    if len(analyses) > 1:
        compare_files(analyses)


if __name__ == "__main__":
    main()
