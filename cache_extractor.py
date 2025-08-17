#!/usr/bin/env python3
"""
基于已发现的结构提取Rolling Cache内容
已确认结构:
- 字节56-63: 内容偏移指针
- 字节64-71: 可能的内容长度
"""

import os
import struct
import json
from collections import Counter
from urllib.parse import urlparse
import re

class RollingCacheExtractor:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_size = os.path.getsize(file_path)
        self.pattern_size = 76
        self.pattern_end_offset = 0x1194E6F
        self.https_start_offset = 0x4000030
        
        # 确认的结构字段
        self.content_pointer_offset = 56  # 字节56-63: 内容指针
        self.content_length_offset = 64   # 字节64-71: 内容长度
        
    def extract_cache_entries(self, limit=200):
        """提取缓存条目"""
        print(f"提取缓存条目 (限制{limit}个)...")
        
        cache_entries = []
        
        with open(self.file_path, 'rb') as f:
            entries_found = 0
            
            for offset in range(0, self.pattern_end_offset, self.pattern_size):
                if entries_found >= limit:
                    break
                    
                f.seek(offset)
                pattern = f.read(self.pattern_size)
                
                if len(pattern) != self.pattern_size or pattern == b'\x00' * self.pattern_size:
                    continue
                    
                # 解析关键字段
                try:
                    content_pointer = struct.unpack('<Q', pattern[self.content_pointer_offset:self.content_pointer_offset+8])[0]
                    content_length = struct.unpack('<Q', pattern[self.content_length_offset:self.content_length_offset+8])[0]
                    
                    # 验证指针有效性
                    if not (self.https_start_offset <= content_pointer < self.file_size):
                        continue
                        
                    # 验证长度合理性
                    if content_length == 0 or content_length > 50 * 1024 * 1024:  # 最大50MB
                        content_length = None
                        
                    entry = {
                        'index': entries_found,
                        'index_offset': offset,
                        'content_pointer': content_pointer,
                        'content_length': content_length,
                        'raw_pattern': pattern.hex()
                    }
                    
                    # 提取内容
                    content_info = self._extract_content(f, content_pointer, content_length)
                    entry.update(content_info)
                    
                    if entry.get('urls'):  # 只保留有URL的条目
                        cache_entries.append(entry)
                        entries_found += 1
                        
                        if entries_found % 50 == 0:
                            print(f"  已提取 {entries_found} 个缓存条目...")
                            
                except Exception as e:
                    continue
                    
        print(f"成功提取 {len(cache_entries)} 个缓存条目")
        return cache_entries
        
    def _extract_content(self, f, pointer, expected_length):
        """提取指定位置的内容"""
        try:
            f.seek(pointer)
            
            # 确定读取长度
            if expected_length and expected_length < 10 * 1024 * 1024:  # 小于10MB
                read_length = expected_length
            else:
                read_length = 5000  # 默认读取5KB
                
            content = f.read(read_length)
            
            # 查找URLs
            urls = re.findall(rb'https://[^\s\x00-\x1f\x7f-\xff]{10,300}', content)
            urls = [url.decode('utf-8', errors='ignore') for url in urls]
            
            # 分析内容类型
            content_type = self._analyze_content_type(content)
            
            # 提取主要信息
            info = {
                'content_size': len(content),
                'urls': urls,
                'content_type': content_type,
                'preview': content[:500].hex() if content else None
            }
            
            if urls:
                main_url = urls[0]
                parsed = urlparse(main_url)
                info['primary_url'] = main_url
                info['domain'] = parsed.netloc
                info['path'] = parsed.path
                
            return info
            
        except Exception as e:
            return {'error': str(e)}
            
    def _analyze_content_type(self, content):
        """分析内容类型"""
        if not content:
            return 'empty'
            
        # 检查HTTP响应头
        if content.startswith(b'HTTP/'):
            return 'http_response'
            
        # 检查常见文件格式
        if content.startswith(b'\x89PNG'):
            return 'png_image'
        elif content.startswith(b'\xff\xd8\xff'):
            return 'jpeg_image'
        elif content.startswith(b'GIF8'):
            return 'gif_image'
        elif content.startswith(b'<?xml') or b'<' in content[:100]:
            return 'xml_data'
        elif content.startswith(b'{') and b'}' in content:
            return 'json_data'
            
        # 检查文本内容
        try:
            text = content.decode('utf-8')
            if 'Content-Type:' in text:
                return 'http_header'
            elif text.isprintable():
                return 'text_data'
        except:
            pass
            
        return 'binary_data'
        
    def analyze_cache_patterns(self, cache_entries):
        """分析缓存模式"""
        print("分析缓存模式...")
        
        analysis = {
            'total_entries': len(cache_entries),
            'domains': Counter(),
            'content_types': Counter(),
            'url_patterns': Counter(),
            'size_distribution': [],
            'length_accuracy': []
        }
        
        for entry in cache_entries:
            # 域名统计
            if entry.get('domain'):
                analysis['domains'][entry['domain']] += 1
                
            # 内容类型统计
            if entry.get('content_type'):
                analysis['content_types'][entry['content_type']] += 1
                
            # URL模式统计
            if entry.get('path'):
                path_parts = entry['path'].strip('/').split('/')
                if path_parts and path_parts[0]:
                    analysis['url_patterns'][path_parts[0]] += 1
                    
            # 大小分布
            if entry.get('content_size'):
                analysis['size_distribution'].append(entry['content_size'])
                
            # 长度准确性检查
            if entry.get('content_length') and entry.get('content_size'):
                expected = entry['content_length']
                actual = entry['content_size']
                accuracy = abs(expected - actual) / max(expected, actual) if max(expected, actual) > 0 else 0
                analysis['length_accuracy'].append(accuracy)
                
        return analysis
        
    def extract_sample_content(self, cache_entries, output_dir='extracted_content'):
        """提取样本内容到文件"""
        print(f"提取样本内容到 {output_dir}...")
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        extracted_count = 0
        
        with open(self.file_path, 'rb') as f:
            for i, entry in enumerate(cache_entries[:20]):  # 提取前20个
                if not entry.get('content_pointer'):
                    continue
                    
                try:
                    f.seek(entry['content_pointer'])
                    
                    # 确定提取长度
                    if entry.get('content_length') and entry['content_length'] < 5 * 1024 * 1024:
                        extract_length = entry['content_length']
                    else:
                        extract_length = 100 * 1024  # 默认100KB
                        
                    content = f.read(extract_length)
                    
                    # 确定文件名和扩展名
                    domain = entry.get('domain', 'unknown')
                    content_type = entry.get('content_type', 'unknown')
                    
                    if content_type == 'png_image':
                        ext = '.png'
                    elif content_type == 'jpeg_image':
                        ext = '.jpg'
                    elif content_type == 'json_data':
                        ext = '.json'
                    elif content_type == 'xml_data':
                        ext = '.xml'
                    else:
                        ext = '.bin'
                        
                    filename = f"content_{i:03d}_{domain.replace('.', '_')}{ext}"
                    filepath = os.path.join(output_dir, filename)
                    
                    with open(filepath, 'wb') as out_f:
                        out_f.write(content)
                        
                    extracted_count += 1
                    print(f"  提取: {filename} ({len(content)} bytes)")
                    
                except Exception as e:
                    print(f"  提取失败 {i}: {e}")
                    
        print(f"成功提取 {extracted_count} 个内容文件")
        
    def generate_final_report(self, cache_entries, analysis):
        """生成最终分析报告"""
        print("\n" + "="*80)
        print("Microsoft Flight Simulator 2024 Rolling Cache 最终分析报告")
        print("="*80)
        
        print(f"\n【缓存文件概览】")
        print(f"文件大小: {self.file_size / (1024**3):.2f} GB")
        print(f"索引区域: 0x0 - 0x{self.pattern_end_offset:X} ({self.pattern_end_offset / (1024**2):.1f} MB)")
        print(f"内容区域: 0x{self.https_start_offset:X} - EOF ({(self.file_size - self.https_start_offset) / (1024**3):.2f} GB)")
        
        print(f"\n【76字节索引结构 - 已确认】")
        print(f"字节 56-63: 内容偏移指针 (64位)")
        print(f"字节 64-71: 内容长度 (64位)")
        print(f"其他字段: 可能包含哈希值、时间戳、标志位等元数据")
        
        print(f"\n【缓存内容分析】")
        print(f"成功解析的缓存条目: {analysis['total_entries']}")
        
        print(f"\n主要域名分布:")
        for domain, count in analysis['domains'].most_common(10):
            percentage = count / analysis['total_entries'] * 100
            print(f"  {domain}: {count} ({percentage:.1f}%)")
            
        print(f"\n内容类型分布:")
        for content_type, count in analysis['content_types'].most_common():
            percentage = count / analysis['total_entries'] * 100
            print(f"  {content_type}: {count} ({percentage:.1f}%)")
            
        print(f"\nURL路径模式:")
        for pattern, count in analysis['url_patterns'].most_common(10):
            print(f"  /{pattern}: {count}次")
            
        if analysis['size_distribution']:
            sizes = analysis['size_distribution']
            print(f"\n内容大小统计:")
            print(f"  平均大小: {sum(sizes) / len(sizes):.0f} bytes")
            print(f"  最小大小: {min(sizes)} bytes")
            print(f"  最大大小: {max(sizes)} bytes")
            
        if analysis['length_accuracy']:
            accuracies = analysis['length_accuracy']
            avg_accuracy = sum(accuracies) / len(accuracies)
            print(f"\n长度字段准确性: {(1 - avg_accuracy) * 100:.1f}%")
            
        print(f"\n【缓存机制总结】")
        print(f"1. 这是一个高性能的基于偏移指针的缓存系统")
        print(f"2. 76字节索引条目存储元数据和指向实际内容的指针")
        print(f"3. 主要缓存Microsoft Flight Simulator的地形、纹理等资源")
        print(f"4. 内容来源主要是Akamai CDN (sunrisecontent.akamaized.net)")
        print(f"5. 支持多种内容类型，包括图像、XML数据等")
        
        # 示例条目
        if cache_entries:
            print(f"\n【示例缓存条目】")
            for i, entry in enumerate(cache_entries[:3]):
                print(f"\n条目 {i+1}:")
                print(f"  索引偏移: 0x{entry['index_offset']:X}")
                print(f"  内容指针: 0x{entry['content_pointer']:X}")
                if entry.get('content_length'):
                    print(f"  内容长度: {entry['content_length']:,} bytes")
                if entry.get('primary_url'):
                    print(f"  主要URL: {entry['primary_url'][:80]}...")
                if entry.get('content_type'):
                    print(f"  内容类型: {entry['content_type']}")
                    
    def run_extraction(self):
        """运行完整的提取分析"""
        print("开始Rolling Cache内容提取和分析")
        
        # 1. 提取缓存条目
        cache_entries = self.extract_cache_entries()
        
        # 2. 分析缓存模式
        analysis = self.analyze_cache_patterns(cache_entries)
        
        # 3. 提取样本内容
        self.extract_sample_content(cache_entries)
        
        # 4. 生成最终报告
        self.generate_final_report(cache_entries, analysis)
        
        # 5. 保存结果到JSON
        output_file = 'cache_analysis_results.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'cache_entries': cache_entries,
                'analysis': {
                    'total_entries': analysis['total_entries'],
                    'domains': dict(analysis['domains']),
                    'content_types': dict(analysis['content_types']),
                    'url_patterns': dict(analysis['url_patterns'])
                }
            }, f, indent=2, ensure_ascii=False)
            
        print(f"\n分析结果已保存到: {output_file}")
        
        return cache_entries, analysis


def main():
    file_path = r"d:\dev\rolling-cache-analysis\rolling-cache\16g-some-content\ROLLINGCACHE.CCC"
    
    if not os.path.exists(file_path):
        print(f"错误: 文件不存在: {file_path}")
        return
        
    extractor = RollingCacheExtractor(file_path)
    cache_entries, analysis = extractor.run_extraction()
    
    return cache_entries, analysis


if __name__ == "__main__":
    main()
