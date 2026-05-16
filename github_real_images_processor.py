#!/usr/bin/env python3
"""
Download real underwater images from public sources and process through Depth Anything
Includes multiple GitHub dataset sources
"""

import sys
import importlib
import types
import os
import urllib.request
import json
from pathlib import Path
from urllib.error import URLError, HTTPError

# Mock soundfile
class MockSoundfileModule(types.ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self.__spec__ = importlib.machinery.ModuleSpec(name, None)
        self.__spec__.loader = None
        self.__spec__.origin = 'mock'
        self.__spec__.submodule_search_locations = []
        self.__version__ = '0.12.1'
        self.SoundFile = None

if 'soundfile' in sys.modules:
    del sys.modules['soundfile']

mock_module = MockSoundfileModule('soundfile')
sys.modules['soundfile'] = mock_module

original_find_spec = importlib.util.find_spec

def mock_find_spec(name, *args, **kwargs):
    if name == 'soundfile' or name.startswith('soundfile.'):
        return mock_module.__spec__
    return original_find_spec(name, *args, **kwargs)

importlib.util.find_spec = mock_find_spec

import torch
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from transformers import AutoImageProcessor, AutoModelForDepthEstimation

OUTPUT_DIR = Path("./github_depth_results_enhanced")
OUTPUT_DIR.mkdir(exist_ok=True)
INPUT_DIR = OUTPUT_DIR / "input_images"
INPUT_DIR.mkdir(exist_ok=True)

print("=" * 80)
print("🌊 UNDERWATER DEPTH ESTIMATION - Enhanced GitHub Image Processor")
print("=" * 80)

# Load Model
print("\n📦 Loading Depth Anything model...")
model_checkpoint = "depth-anything/Depth-Anything-V2-Small-hf"
base_model = AutoModelForDepthEstimation.from_pretrained(model_checkpoint)
processor = AutoImageProcessor.from_pretrained(model_checkpoint)
base_model.eval()
print("✅ Model loaded successfully!")

# Real underwater image sources from GitHub
REAL_IMAGE_SOURCES = [
    {
        'name': 'SeaThru Dataset Sample',
        'url': 'https://raw.githubusercontent.com/aksyuk/SeaThru/master/sample_data/test_img.jpg'
    },
    {
        'name': 'Underwater Object Detection Sample',
        'url': 'https://raw.githubusercontent.com/xuwenwu/UDIS/master/sample_images/underwater.jpg'
    },
    {
        'name': 'Generic Underwater Scene',
        'url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Poissons_tropical_FWF_33.jpg/640px-Poissons_tropical_FWF_33.jpg'
    },
]

def download_image_with_retry(url, save_path, max_retries=3):
    """Download with retry logic"""
    for attempt in range(max_retries):
        try:
            print(f"  ↓ Downloading (attempt {attempt + 1}/{max_retries}): {url[:60]}...")
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            urllib.request.urlopen(req).read()
            urllib.request.urlretrieve(url, save_path)
            print(f"  ✅ Downloaded successfully!")
            return True
        except (HTTPError, URLError) as e:
            print(f"  ⚠️  Attempt {attempt + 1} failed: {str(e)[:50]}")
            if attempt == max_retries - 1:
                return False
    return False

def create_realistic_underwater_image(idx, size=(640, 480)):
    """Create more realistic underwater images"""
    print(f"  🎨 Creating realistic underwater image {idx}...")
    
    np.random.seed(idx * 42)
    
    # Create base gradient (water gets darker with depth)
    img_array = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    
    for y in range(size[1]):
        depth_factor = y / size[1]
        r = int(50 + depth_factor * 40)
        g = int(80 + depth_factor * 60)
        b = int(140 + depth_factor * 80)
        img_array[y, :] = [r, g, b]
    
    # Add some coral/rock formations
    for i in range(5):
        cx = np.random.randint(100, size[0] - 100)
        cy = np.random.randint(100, size[1] - 100)
        radius = np.random.randint(30, 80)
        
        y, x = np.ogrid[:size[1], :size[0]]
        mask = (x - cx)**2 + (y - cy)**2 <= radius**2
        img_array[mask] = np.clip(img_array[mask].astype(int) + np.random.randint(-30, 60, 3), 0, 255).astype(np.uint8)
    
    # Add particles/suspended matter
    for _ in range(200):
        px = np.random.randint(0, size[0])
        py = np.random.randint(0, size[1])
        size_particle = np.random.randint(1, 4)
        img_array[max(0, py-size_particle):min(size[1], py+size_particle),
                  max(0, px-size_particle):min(size[0], px+size_particle)] = \
            np.clip(img_array[max(0, py-size_particle):min(size[1], py+size_particle),
                             max(0, px-size_particle):min(size[0], px+size_particle)].astype(int) + 80, 0, 255).astype(np.uint8)
    
    img = Image.fromarray(img_array, mode='RGB')
    return img

def estimate_depth(image, idx):
    """Estimate depth from image"""
    print(f"  🔮 Processing image {idx}...")
    
    try:
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        print(f"     Image size: {image.size}")
        
        inputs = processor(images=image, return_tensors="pt")
        
        with torch.no_grad():
            outputs = base_model(**inputs)
            depth_map = outputs.predicted_depth.squeeze().cpu().numpy()
        
        print(f"     ✅ Depth map shape: {depth_map.shape}")
        
        depth_min = depth_map.min()
        depth_max = depth_map.max()
        depth_mean = depth_map.mean()
        depth_std = depth_map.std()
        
        print(f"     📊 Depth range: [{depth_min:.4f}, {depth_max:.4f}]")
        print(f"     📊 Mean: {depth_mean:.4f} ± {depth_std:.4f}")
        
        return depth_map, (depth_min, depth_max, depth_mean, depth_std)
    
    except Exception as e:
        print(f"     ❌ Error: {e}")
        return None, None

def save_depth_map(depth_map, image, idx, stats, source_name=""):
    """Save depth map with detailed visualization"""
    depth_min, depth_max, depth_mean, depth_std = stats
    
    depth_normalized = (depth_map - depth_min) / (depth_max - depth_min + 1e-8)
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(f'Depth Analysis - {source_name}', fontsize=16, fontweight='bold')
    
    # Original image
    axes[0, 0].imshow(image)
    axes[0, 0].set_title('Original Image')
    axes[0, 0].axis('off')
    
    # Plasma colormap
    im1 = axes[0, 1].imshow(depth_normalized, cmap='plasma')
    axes[0, 1].set_title('Depth Map (Plasma)')
    axes[0, 1].axis('off')
    plt.colorbar(im1, ax=axes[0, 1], label='Relative Depth')
    
    # Viridis colormap
    im2 = axes[0, 2].imshow(depth_normalized, cmap='viridis')
    axes[0, 2].set_title('Depth Map (Viridis)')
    axes[0, 2].axis('off')
    plt.colorbar(im2, ax=axes[0, 2], label='Relative Depth')
    
    # Contour plot
    cs = axes[1, 0].contourf(depth_normalized, levels=15, cmap='jet')
    axes[1, 0].set_title('Depth Contours')
    axes[1, 0].axis('off')
    plt.colorbar(cs, ax=axes[1, 0])
    
    # 3D-like surface plot
    X, Y = np.meshgrid(np.arange(depth_map.shape[1]), np.arange(depth_map.shape[0]))
    im3 = axes[1, 1].pcolormesh(X, Y, depth_normalized, cmap='turbo', shading='auto')
    axes[1, 1].set_title('Depth Surface')
    axes[1, 1].axis('off')
    plt.colorbar(im3, ax=axes[1, 1])
    
    # Statistics
    stats_text = f"""
DEPTH STATISTICS

Range Analysis:
  Min Depth: {depth_min:.6f}
  Max Depth: {depth_max:.6f}
  Range: {depth_max - depth_min:.6f}

Distribution:
  Mean: {depth_mean:.6f}
  Median: {np.median(depth_map):.6f}
  Std Dev: {depth_std:.6f}

Quantiles:
  25th: {np.percentile(depth_map, 25):.6f}
  50th: {np.percentile(depth_map, 50):.6f}
  75th: {np.percentile(depth_map, 75):.6f}

Image Size: {depth_map.shape}
"""
    
    axes[1, 2].text(0.05, 0.95, stats_text, fontsize=9, family='monospace',
                   verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    axes[1, 2].axis('off')
    
    output_path = OUTPUT_DIR / f"depth_analysis_{idx:02d}.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"     💾 Saved to: {output_path.name}")
    return output_path

# Download and process images
print("\n" + "=" * 80)
print("📥 DOWNLOADING REAL UNDERWATER IMAGES")
print("=" * 80)

image_paths = []
idx = 0

# Try real sources
for source in REAL_IMAGE_SOURCES:
    print(f"\n🔗 {source['name']}")
    save_path = INPUT_DIR / f"real_underwater_{idx}.jpg"
    
    if download_image_with_retry(source['url'], save_path):
        image_paths.append((save_path, source['name']))
        idx += 1
    else:
        print(f"  ⚠️  Could not download {source['name']}")

# Generate synthetic ones for variety
print(f"\n📝 Generating synthetic underwater images for comparison...")
for i in range(3):
    img = create_realistic_underwater_image(i, size=(640, 480))
    save_path = INPUT_DIR / f"synthetic_underwater_{i}.jpg"
    img.save(save_path)
    image_paths.append((save_path, f"Synthetic Underwater Scene {i+1}"))
    print(f"  ✅ Created synthetic image {i+1}")

# Process all images
print("\n" + "=" * 80)
print("🔄 PROCESSING IMAGES THROUGH DEPTH ANYTHING")
print("=" * 80)

results = []

for idx, (image_path, source_name) in enumerate(image_paths):
    print(f"\n🖼️  Image {idx + 1}/{len(image_paths)}")
    print(f"   Source: {source_name}")
    print(f"   File: {image_path.name}")
    
    try:
        image = Image.open(image_path).convert('RGB')
        depth_map, stats = estimate_depth(image, idx)
        
        if depth_map is not None:
            output_path = save_depth_map(depth_map, image, idx, stats, source_name)
            results.append({
                'index': idx,
                'source': source_name,
                'input': str(image_path),
                'output': str(output_path),
                'image_size': list(image.size),
                'depth_shape': list(depth_map.shape),
                'stats': {
                    'min': float(stats[0]),
                    'max': float(stats[1]),
                    'mean': float(stats[2]),
                    'std': float(stats[3]),
                    'median': float(np.median(depth_map))
                }
            })
    
    except Exception as e:
        print(f"   ❌ Error: {e}")

# Generate comprehensive report
print("\n" + "=" * 80)
print("📋 GENERATING COMPREHENSIVE REPORT")
print("=" * 80)

report_path = OUTPUT_DIR / "processing_report.json"
with open(report_path, 'w') as f:
    json.dump(results, f, indent=2)

print(f"✅ Report saved to: {report_path}")

# Create a summary markdown file
summary_md = OUTPUT_DIR / "RESULTS_SUMMARY.md"
with open(summary_md, 'w') as f:
    f.write("# 🌊 Underwater Depth Estimation Results\n\n")
    f.write("## Processing Summary\n\n")
    f.write(f"- **Total Images Processed:** {len(results)}\n")
    f.write(f"- **Processing Date:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"- **Model:** Depth Anything V2 Small\n\n")
    
    f.write("## Results\n\n")
    for result in results:
        f.write(f"### {result['index'] + 1}. {result['source']}\n\n")
        f.write(f"- **Input Image:** `{Path(result['input']).name}`\n")
        f.write(f"- **Output Visualization:** `{Path(result['output']).name}`\n")
        f.write(f"- **Image Size:** {result['image_size']}\n")
        f.write(f"- **Depth Map Size:** {result['depth_shape']}\n\n")
        
        stats = result['stats']
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Min Depth | {stats['min']:.6f} |\n")
        f.write(f"| Max Depth | {stats['max']:.6f} |\n")
        f.write(f"| Mean Depth | {stats['mean']:.6f} |\n")
        f.write(f"| Median Depth | {stats['median']:.6f} |\n")
        f.write(f"| Std Dev | {stats['std']:.6f} |\n\n")

print(f"✅ Summary saved to: {summary_md}")

# Display final summary
print("\n" + "=" * 80)
print("📊 FINAL SUMMARY")
print("=" * 80)

for result in results:
    print(f"\n{result['index'] + 1}. {result['source']}")
    print(f"   File: {Path(result['input']).name}")
    stats = result['stats']
    print(f"   Depth Range: [{stats['min']:.4f}, {stats['max']:.4f}]")
    print(f"   Mean ± Std: {stats['mean']:.4f} ± {stats['std']:.4f}")

print(f"\n📁 All files saved in: {OUTPUT_DIR}")
print(f"📄 Summary: {summary_md.name}")
print("=" * 80)

importlib.util.find_spec = original_find_spec
