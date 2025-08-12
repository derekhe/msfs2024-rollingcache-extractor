#!/usr/bin/env python3
"""
MSFS2024 RollingCache 卫星图像专项分析器
专门搜索4000+个256x256图像，放宽验证条件
"""

import os
import mmap
import struct
from typing import Dict, List, Tuple, Optional
import argparse
import time
from collections import defaultdict


def find_all_potential_images(file_path: str, target_size: Tuple[int, int] = (256, 256)) -> Dict:
    """查找所有可能的256x256图像，包括各种格式和变体"""
    print(f"卫星图像专项搜索: {os.path.basename(file_path)}")
    print(f"目标尺寸: {target_size[0]}x{target_size[1]}")
    start_time = time.time()
    
    results = {
        'file_path': file_path,
        'potential_images': [],
        'format_analysis': defaultdict(list),
        'size_analysis': defaultdict(list),
        'total_found': 0
    }
    
    target_width, target_height = target_size
    file_size = os.path.getsize(file_path)
    
    # 扩展的图像格式签名和验证
    image_patterns = [
        # PNG 变体 - 放宽验证
        {
            'name': 'PNG_STANDARD',
            'signature': b'\x89PNG\r\n\x1a\n',
            'validator': lambda data, pos: validate_png_relaxed(data, pos, target_size)
        },
        # PNG chunk开始模式 (可能PNG头部被修改)
        {
            'name': 'PNG_IHDR',
            'signature': b'IHDR',
            'validator': lambda data, pos: validate_ihdr_chunk(data, pos, target_size)
        },
        # JPEG 变体
        {
            'name': 'JPEG_STANDARD',
            'signature': b'\xFF\xD8\xFF',
            'validator': lambda data, pos: validate_jpeg_relaxed(data, pos, target_size)
        },
        # DDS
        {
            'name': 'DDS',
            'signature': b'DDS ',
            'validator': lambda data, pos: validate_dds_relaxed(data, pos, target_size)
        },
        # 原始图像数据模式 - 查找256x256的维度标识
        {
            'name': 'RAW_DIMENSION',
            'signature': struct.pack('<II', target_width, target_height),  # 小端序的256, 256
            'validator': lambda data, pos: validate_raw_dimensions(data, pos, target_size)
        },
        {
            'name': 'RAW_DIMENSION_BE',
            'signature': struct.pack('>II', target_width, target_height),  # 大端序的256, 256
            'validator': lambda data, pos: validate_raw_dimensions(data, pos, target_size)
        },
        # 可能的纹理格式
        {
            'name': 'TEX_HEADER',
            'signature': b'TEX\x00',
            'validator': lambda data, pos: validate_texture_header(data, pos, target_size)
        },
        # BC压缩格式
        {
            'name': 'BC_COMPRESSED',
            'signature': b'BC',
            'validator': lambda data, pos: validate_bc_texture(data, pos, target_size)
        }
    ]
    
    with open(file_path, 'rb') as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            
            for pattern in image_patterns:
                print(f"\n搜索 {pattern['name']} 格式...")
                signature = pattern['signature']
                validator = pattern['validator']
                
                pos = 0
                format_count = 0
                
                while pos < file_size and format_count < 2000:  # 每种格式最多找2000个
                    pos = mm.find(signature, pos)
                    if pos == -1:
                        break
                    
                    # 验证是否为有效图像
                    validation_result = validator(mm, pos)
                    
                    if validation_result:
                        image_info = {
                            'format': pattern['name'],
                            'offset': pos,
                            'signature_pos': pos,
                            **validation_result
                        }
                        
                        results['potential_images'].append(image_info)
                        results['format_analysis'][pattern['name']].append(image_info)
                        
                        # 按尺寸分类
                        if 'width' in validation_result and 'height' in validation_result:
                            size_key = f"{validation_result['width']}x{validation_result['height']}"
                            results['size_analysis'][size_key].append(image_info)
                        
                        format_count += 1
                        
                        if format_count % 100 == 0:
                            print(f"  找到 {format_count} 个 {pattern['name']}")
                    
                    pos += len(signature)
                
                print(f"  {pattern['name']}: 总计 {format_count} 个")
    
    results['total_found'] = len(results['potential_images'])
    results['analysis_time'] = time.time() - start_time
    
    print(f"\n搜索完成，耗时: {results['analysis_time']:.2f} 秒")
    print(f"总计找到潜在图像: {results['total_found']} 个")
    
    return results


def validate_png_relaxed(data: bytes, pos: int, target_size: Tuple[int, int]) -> Optional[Dict]:
    """放宽的PNG验证"""
    if pos + 33 > len(data):
        return None
    
    # 检查PNG签名
    if data[pos:pos+8] != b'\x89PNG\r\n\x1a\n':
        return None
    
    # 查找IHDR
    ihdr_pos = pos + 8
    for i in range(3):  # 允许一些偏移
        check_pos = ihdr_pos + i * 4
        if check_pos + 21 <= len(data):
            if data[check_pos+4:check_pos+8] == b'IHDR':
                try:
                    ihdr_data = data[check_pos+8:check_pos+21]
                    width, height, bit_depth, color_type = struct.unpack('>IIBBB', ihdr_data[:9])
                    
                    # 放宽尺寸要求 - 接受256x256或相近尺寸
                    if (240 <= width <= 280 and 240 <= height <= 280 and
                        bit_depth in [1, 2, 4, 8, 16] and
                        color_type in [0, 2, 3, 4, 6]):
                        
                        return {
                            'width': width,
                            'height': height,
                            'bit_depth': bit_depth,
                            'color_type': color_type,
                            'estimated_size': estimate_png_size(width, height, bit_depth, color_type)
                        }
                except:
                    continue
    
    return None


def validate_ihdr_chunk(data: bytes, pos: int, target_size: Tuple[int, int]) -> Optional[Dict]:
    """验证IHDR chunk（可能PNG头部被剥离）"""
    if pos + 13 > len(data):
        return None
    
    # 检查前面是否有长度字段
    for offset in [-8, -4, 0]:
        check_pos = pos + offset
        if check_pos >= 0 and check_pos + 21 <= len(data):
            try:
                if data[check_pos+4:check_pos+8] == b'IHDR':
                    ihdr_data = data[check_pos+8:check_pos+21]
                    width, height, bit_depth, color_type = struct.unpack('>IIBBB', ihdr_data[:9])
                    
                    if (200 <= width <= 300 and 200 <= height <= 300):
                        return {
                            'width': width,
                            'height': height,
                            'bit_depth': bit_depth,
                            'color_type': color_type,
                            'estimated_size': estimate_png_size(width, height, bit_depth, color_type)
                        }
            except:
                continue
    
    return None


def validate_jpeg_relaxed(data: bytes, pos: int, target_size: Tuple[int, int]) -> Optional[Dict]:
    """放宽的JPEG验证"""
    if pos + 20 > len(data):
        return None
    
    # 基本JPEG签名检查
    if data[pos:pos+3] != b'\xFF\xD8\xFF':
        return None
    
    # 查找SOF标记来获取尺寸
    search_end = min(pos + 1024, len(data))
    for i in range(pos + 3, search_end - 10):
        if data[i] == 0xFF and data[i+1] in [0xC0, 0xC1, 0xC2]:  # SOF markers
            try:
                length = struct.unpack('>H', data[i+2:i+4])[0]
                if i + 4 + length <= len(data):
                    height = struct.unpack('>H', data[i+5:i+7])[0]
                    width = struct.unpack('>H', data[i+7:i+9])[0]
                    
                    if 200 <= width <= 300 and 200 <= height <= 300:
                        return {
                            'width': width,
                            'height': height,
                            'estimated_size': width * height * 3  # 估算RGB大小
                        }
            except:
                continue
    
    return None


def validate_dds_relaxed(data: bytes, pos: int, target_size: Tuple[int, int]) -> Optional[Dict]:
    """DDS格式验证"""
    if pos + 128 > len(data):
        return None
    
    if data[pos:pos+4] != b'DDS ':
        return None
    
    try:
        # DDS header
        header_size = struct.unpack('<I', data[pos+4:pos+8])[0]
        if header_size == 124:
            height = struct.unpack('<I', data[pos+12:pos+16])[0]
            width = struct.unpack('<I', data[pos+16:pos+20])[0]
            
            if 200 <= width <= 300 and 200 <= height <= 300:
                return {
                    'width': width,
                    'height': height,
                    'estimated_size': width * height * 4  # 估算RGBA大小
                }
    except:
        pass
    
    return None


def validate_raw_dimensions(data: bytes, pos: int, target_size: Tuple[int, int]) -> Optional[Dict]:
    """验证原始维度数据"""
    if pos + 8 > len(data):
        return None
    
    try:
        # 检查是否真的是维度数据
        width, height = struct.unpack('<II', data[pos:pos+8])
        
        # 更宽松的尺寸验证
        if 200 <= width <= 400 and 200 <= height <= 400:
            # 检查后续是否有合理的图像数据
            expected_size = width * height
            if pos + 8 + expected_size <= len(data):
                # 简单的数据熵检查
                sample_data = data[pos+8:pos+8+min(1024, expected_size)]
                if len(set(sample_data)) > 10:  # 数据有一定变化
                    return {
                        'width': width,
                        'height': height,
                        'estimated_size': expected_size,
                        'format_hint': 'raw_grayscale' if expected_size == width * height else 'raw_rgba'
                    }
    except:
        pass
    
    return None


def validate_texture_header(data: bytes, pos: int, target_size: Tuple[int, int]) -> Optional[Dict]:
    """验证自定义纹理头部"""
    if pos + 32 > len(data):
        return None
    
    # 简单的纹理头部启发式检查
    try:
        # 检查后续几个DWORD是否包含合理的维度
        for offset in range(4, 32, 4):
            if pos + offset + 8 <= len(data):
                width, height = struct.unpack('<II', data[pos+offset:pos+offset+8])
                if 200 <= width <= 400 and 200 <= height <= 400:
                    return {
                        'width': width,
                        'height': height,
                        'estimated_size': width * height * 4,
                        'format_hint': 'custom_texture'
                    }
    except:
        pass
    
    return None


def validate_bc_texture(data: bytes, pos: int, target_size: Tuple[int, int]) -> Optional[Dict]:
    """验证BC压缩纹理"""
    if pos + 16 > len(data):
        return None
    
    # BC纹理的基本启发式检查
    if data[pos:pos+2] == b'BC':
        # BC1, BC3, BC5, BC7 等
        bc_type = data[pos+2]
        if bc_type in [ord('1'), ord('3'), ord('5'), ord('7')]:
            # 假设是256x256的BC纹理
            width, height = target_size
            return {
                'width': width,
                'height': height,
                'estimated_size': (width * height) // (2 if bc_type == ord('1') else 1),
                'format_hint': f'BC{chr(bc_type)}'
            }
    
    return None


def estimate_png_size(width: int, height: int, bit_depth: int, color_type: int) -> int:
    """估算PNG文件大小"""
    # 基本像素数据大小
    if color_type == 0:  # Grayscale
        raw_size = width * height * (bit_depth // 8 or 1)
    elif color_type == 2:  # RGB
        raw_size = width * height * 3 * (bit_depth // 8 or 1)
    elif color_type == 3:  # Palette
        raw_size = width * height * (bit_depth // 8 or 1)
    elif color_type == 4:  # Grayscale + Alpha
        raw_size = width * height * 2 * (bit_depth // 8 or 1)
    elif color_type == 6:  # RGB + Alpha
        raw_size = width * height * 4 * (bit_depth // 8 or 1)
    else:
        raw_size = width * height * 4
    
    # 考虑PNG压缩（通常能压缩到50-70%）
    return int(raw_size * 0.6) + 1000  # 加上头部开销


def analyze_results(results: Dict) -> None:
    """分析搜索结果"""
    print("\n" + "="*80)
    print("卫星图像分析结果")
    print("="*80)
    
    total = results['total_found']
    print(f"总计找到图像: {total}")
    
    if total == 0:
        return
    
    # 按格式统计
    print(f"\n📊 格式分布:")
    for format_name, images in results['format_analysis'].items():
        count = len(images)
        percentage = count / total * 100
        print(f"  {format_name:<20}: {count:>6} 个 ({percentage:>5.1f}%)")
    
    # 按尺寸统计
    print(f"\n📏 尺寸分布:")
    for size_name, images in results['size_analysis'].items():
        count = len(images)
        percentage = count / total * 100
        print(f"  {size_name:<12}: {count:>6} 个 ({percentage:>5.1f}%)")
    
    # 显示一些样本
    print(f"\n🔍 前20个图像样本:")
    for i, img in enumerate(results['potential_images'][:20]):
        width = img.get('width', '?')
        height = img.get('height', '?')
        size = img.get('estimated_size', '?')
        print(f"  {i+1:2d}. {img['format']:<20} {width}x{height} @ 0x{img['offset']:08X} (~{size} bytes)")


def extract_samples(file_path: str, results: Dict, output_dir: str = "satellite_samples") -> None:
    """提取样本图像"""
    if not results['potential_images']:
        return
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"\n提取样本到: {output_dir}")
    
    # 选择不同格式的样本
    samples_per_format = 3
    extracted_count = 0
    
    with open(file_path, 'rb') as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            
            for format_name, images in results['format_analysis'].items():
                format_count = 0
                
                for img in images:
                    if format_count >= samples_per_format:
                        break
                    
                    try:
                        offset = img['offset']
                        est_size = img.get('estimated_size', 50000)
                        
                        # 限制提取大小
                        max_extract_size = min(est_size * 2, 1024 * 1024)  # 最大1MB
                        
                        if offset + max_extract_size <= len(mm):
                            data = mm[offset:offset+max_extract_size]
                            
                            # 确定文件扩展名
                            if 'PNG' in format_name:
                                ext = '.png'
                            elif 'JPEG' in format_name:
                                ext = '.jpg'
                            elif 'DDS' in format_name:
                                ext = '.dds'
                            else:
                                ext = '.bin'
                            
                            width = img.get('width', 'unk')
                            height = img.get('height', 'unk')
                            filename = f"{format_name}_{format_count+1}_{width}x{height}_{hex(offset)}{ext}"
                            filepath = os.path.join(output_dir, filename)
                            
                            with open(filepath, 'wb') as out_f:
                                out_f.write(data)
                            
                            print(f"  ✓ {filename} ({len(data)} bytes)")
                            format_count += 1
                            extracted_count += 1
                    
                    except Exception as e:
                        print(f"  ✗ 提取失败: {e}")
    
    print(f"总计提取: {extracted_count} 个样本")


def main():
    parser = argparse.ArgumentParser(description='MSFS2024 卫星图像专项分析器')
    parser.add_argument('files', nargs='+', help='要分析的 CCC 文件')
    parser.add_argument('--extract', action='store_true', help='提取样本图像')
    parser.add_argument('--target-size', nargs=2, type=int, default=[256, 256], 
                       help='目标图像尺寸 (默认: 256 256)')
    parser.add_argument('--output-dir', default='satellite_samples', help='样本输出目录')
    
    args = parser.parse_args()
    
    target_size = tuple(args.target_size)
    
    for file_path in args.files:
        if not os.path.exists(file_path):
            print(f"错误: 文件不存在 - {file_path}")
            continue
        
        results = find_all_potential_images(file_path, target_size)
        analyze_results(results)
        
        if args.extract:
            extract_samples(file_path, results, args.output_dir)
        
        print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
