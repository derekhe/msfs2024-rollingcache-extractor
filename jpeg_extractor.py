#!/usr/bin/env python3
"""
MSFS2024 RollingCache JPEG卫星图像提取器
提取所有找到的JPEG格式卫星图像（简化版 - 无质量分类）
"""

import os
import mmap
import struct
from typing import Dict, List, Tuple, Optional
import argparse
import time
from collections import defaultdict


def find_jpeg_images(file_path: str, target_size: Tuple[int, int] = (256, 256)) -> List[Dict]:
    """查找所有JPEG卫星图像"""
    print(f"JPEG卫星图像搜索: {os.path.basename(file_path)}")
    print(f"目标尺寸: {target_size[0]}x{target_size[1]}")
    
    start_time = time.time()
    jpeg_images = []
    target_width, target_height = target_size
    file_size = os.path.getsize(file_path)
    
    with open(file_path, 'rb') as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            
            print("搜索JPEG签名...")
            pos = 0
            found_count = 0
            
            while pos < file_size:
                # 查找JPEG签名
                pos = mm.find(b'\xFF\xD8\xFF', pos)
                if pos == -1:
                    break
                
                found_count += 1
                
                if found_count % 500 == 0:
                    print(f"  已检查 {found_count} 个JPEG签名...")
                
                # 验证JPEG并获取尺寸
                jpeg_info = validate_and_extract_jpeg_info(mm, pos, target_size)
                
                if jpeg_info:
                    jpeg_info['sequence_number'] = len(jpeg_images) + 1
                    jpeg_images.append(jpeg_info)
                    
                    if len(jpeg_images) % 100 == 0:
                        print(f"    已找到 {len(jpeg_images)} 个有效JPEG")
                
                pos += 3  # 跳过当前签名继续搜索
    
    elapsed_time = time.time() - start_time
    print(f"\n搜索完成，耗时: {elapsed_time:.2f} 秒")
    print(f"检查JPEG签名: {found_count} 个")
    print(f"有效JPEG图像: {len(jpeg_images)} 个")
    
    return jpeg_images


def validate_and_extract_jpeg_info(data: bytes, pos: int, target_size: Tuple[int, int]) -> Optional[Dict]:
    """验证JPEG并提取信息"""
    if pos + 20 > len(data):
        return None
    
    # 基本JPEG签名检查
    if data[pos:pos+3] != b'\xFF\xD8\xFF':
        return None
    
    # 查找SOF标记来获取尺寸
    search_end = min(pos + 2048, len(data))  # 在前2KB内搜索SOF
    width = height = None
    
    for i in range(pos + 3, search_end - 10):
        if data[i] == 0xFF and data[i+1] in [0xC0, 0xC1, 0xC2, 0xC3]:  # SOF markers
            try:
                length = struct.unpack('>H', data[i+2:i+4])[0]
                if i + 4 + length <= len(data) and length >= 8:
                    height = struct.unpack('>H', data[i+5:i+7])[0]
                    width = struct.unpack('>H', data[i+7:i+9])[0]
                    break
            except:
                continue
    
    # 验证尺寸是否符合要求
    target_width, target_height = target_size
    if width is None or height is None:
        return None
    
    # 放宽尺寸要求 - 接受256x256或相近尺寸
    if not (240 <= width <= 280 and 240 <= height <= 280):
        return None
    
    # 查找JPEG结束标记来确定文件大小
    jpeg_size = find_jpeg_end(data, pos)
    if jpeg_size is None:
        # 如果找不到结束标记，估算大小
        jpeg_size = min(500000, len(data) - pos)  # 最大500KB
    
    return {
        'offset': pos,
        'width': width,
        'height': height,
        'size': jpeg_size
    }


def find_jpeg_end(data: bytes, start_pos: int) -> Optional[int]:
    """查找JPEG结束标记"""
    search_end = min(start_pos + 1024*1024, len(data))  # 最多搜索1MB
    
    for i in range(start_pos + 10, search_end - 1):
        if data[i] == 0xFF and data[i+1] == 0xD9:
            return i + 2 - start_pos
    
    return None


def extract_all_jpegs(file_path: str, jpeg_images: List[Dict], output_dir: str = "extracted_jpegs") -> None:
    """提取所有JPEG图像（简化版）"""
    if not jpeg_images:
        print("没有找到JPEG图像")
        return
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"\n开始提取 {len(jpeg_images)} 个JPEG图像到: {output_dir}")
    
    extracted_count = 0
    failed_count = 0
    total_size = 0
    
    with open(file_path, 'rb') as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            
            for i, jpeg_info in enumerate(jpeg_images):
                try:
                    offset = jpeg_info['offset']
                    size = jpeg_info['size']
                    width = jpeg_info['width']
                    height = jpeg_info['height']
                    seq_num = jpeg_info['sequence_number']
                    
                    # 限制最大提取大小
                    max_size = min(size, 2 * 1024 * 1024)  # 最大2MB
                    
                    if offset + max_size <= len(mm):
                        jpeg_data = mm[offset:offset+max_size]
                        
                        # 验证是否以JPEG签名开始
                        if jpeg_data[:3] == b'\xFF\xD8\xFF':
                            # 生成文件名（简化版，不包含质量信息）
                            filename = f"satellite_{seq_num:04d}_{width}x{height}_{hex(offset)}.jpg"
                            filepath = os.path.join(output_dir, filename)
                            
                            with open(filepath, 'wb') as out_f:
                                out_f.write(jpeg_data)
                            
                            extracted_count += 1
                            total_size += len(jpeg_data)
                            
                            if extracted_count % 100 == 0:
                                print(f"  已提取: {extracted_count}/{len(jpeg_images)} ({extracted_count/len(jpeg_images)*100:.1f}%)")
                        else:
                            failed_count += 1
                    else:
                        failed_count += 1
                
                except Exception as e:
                    print(f"  提取第 {i+1} 个JPEG失败: {e}")
                    failed_count += 1
    
    print(f"\n提取完成!")
    print(f"成功提取: {extracted_count} 个")
    print(f"提取失败: {failed_count} 个")
    print(f"总大小: {total_size / (1024*1024):.1f} MB")


def analyze_jpeg_statistics(jpeg_images: List[Dict]) -> None:
    """分析JPEG统计信息"""
    if not jpeg_images:
        return
    
    print(f"\n📊 JPEG图像统计分析:")
    print("-" * 50)
    
    # 尺寸统计
    size_stats = defaultdict(int)
    file_sizes = []
    
    for jpeg in jpeg_images:
        dimension = f"{jpeg['width']}x{jpeg['height']}"
        size_stats[dimension] += 1
        file_sizes.append(jpeg['size'])
    
    print(f"图像尺寸分布:")
    for dimension, count in sorted(size_stats.items(), key=lambda x: x[1], reverse=True):
        percentage = count / len(jpeg_images) * 100
        print(f"  {dimension:<12}: {count:>4} 个 ({percentage:>5.1f}%)")
    
    if file_sizes:
        file_sizes.sort()
        avg_size = sum(file_sizes) / len(file_sizes)
        median_size = file_sizes[len(file_sizes)//2]
        
        print(f"\n文件大小统计:")
        print(f"  最小: {min(file_sizes):,} bytes")
        print(f"  最大: {max(file_sizes):,} bytes")
        print(f"  平均: {avg_size:,.0f} bytes")
        print(f"  中位数: {median_size:,} bytes")


def main():
    parser = argparse.ArgumentParser(description='MSFS2024 JPEG卫星图像提取器（简化版）')
    parser.add_argument('file', help='要分析的 CCC 文件')
    parser.add_argument('--output-dir', default='extracted_jpegs', help='输出目录')
    parser.add_argument('--target-size', nargs=2, type=int, default=[256, 256], 
                       help='目标图像尺寸 (默认: 256 256)')
    parser.add_argument('--analyze-only', action='store_true', help='仅分析不提取')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(f"错误: 文件不存在 - {args.file}")
        return
    
    target_size = tuple(args.target_size)
    
    # 查找所有JPEG图像
    jpeg_images = find_jpeg_images(args.file, target_size)
    
    if jpeg_images:
        # 分析统计信息
        analyze_jpeg_statistics(jpeg_images)
        
        # 提取图像
        if not args.analyze_only:
            extract_all_jpegs(args.file, jpeg_images, args.output_dir)
            
            print(f"\n🎉 完成! 所有JPEG卫星图像已提取到: {args.output_dir}")
    else:
        print("未找到任何JPEG图像")


if __name__ == "__main__":
    main()
