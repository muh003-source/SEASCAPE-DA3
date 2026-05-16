#!/usr/bin/env python3
"""
Download underwater images from GitHub datasets and process them through Depth Anything
"""

import sys
import importlib
import types
import os
import urllib.request
import json
from pathlib import Path

# Mock soundfile (required for transformers)
class MockSoundfileModule(types.ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self.__spec__ = importlib.machinery.ModuleSpec(name, None)
        self.__spec__.loader = None
        self.__spec__.origin = 'mock'
        self.__spec__.submodule_search_locations = []
        self.__version__ = '0.12.1'
        self.SoundFile = None
        
    def read(self, *args, **kwargs):
        return None
    
    def write(self, *args, **kwargs):
        return None

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

# Create output directory
OUTPUT_DIR = Path("./github_depth_results")
OUTPUT_DIR.mkdir(exist_ok=True)
INPUT_DIR = OUTPUT_DIR / "input_images"
INPUT_DIR.mkdir(exist_ok=True)

print("=" * 80)
print("🌊 UNDERWATER DEPTH ESTIMATION - GitHub Image Processor")
print("=" * 80)

# --- Load Model ---
print("\n📦 Loading Depth Anything model...")
model_checkpoint = "depth-anything/Depth-Anything-V2-Small-hf"
base_model = AutoModelForDepthEstimation.from_pretrained(model_checkpoint)
processor = AutoImageProcessor.from_pretrained(model_checkpoint)
base_model.eval()
print("✅ Model loaded successfully!")

# --- GitHub Image Sources ---
GITHUB_IMAGE_URLS = [
    # USOD10K dataset sample images from GitHub
    "https://raw.githubusercontent.com/LinHong-HIT/USOD10K/main/Images/underwater_img_000001.jpg",
    
    # Sample underwater images from various sources
    "https://raw.githubusercontent.com/tompollard/phd_thesis_artifacts/master/results/underwater_0.jpg",
    
    # Fallback: Create test underwater-like images if GitHub images aren't available
    None  # Will generate synthetic ones
]

def download_image(url, save_path):
    """Download image from GitHub URL"""
    try:
        print(f"  ↓ Downloading from: {url}")
        urllib.request.urlretrieve(url, save_path)
        print(f"  ✅ Saved to: {save_path}")
        return True
    except Exception as e:
        print(f"  ❌ Failed to download: {e}")
        return False

def create_synthetic_underwater_image(idx, size=(384, 512)):
    """Create synthetic underwater-like image for testing"""
    print(f"  🎨 Creating synthetic underwater image {idx}...")
    
    # Create a more realistic underwater scene
    img = Image.new('RGB', size, color=(20, 40, 80))  # Dark blue water
    pixels = img.load()
    
    # Add some texture variation
    np.random.seed(idx)
    for i in range(size[0]):
        for j in range(size[1]):
            # Add depth-based coloring (bluish to more transparent)
            depth_factor = j / size[1]
            r = int(20 + depth_factor * 60)
            g = int(40 + depth_factor * 80)
            b = int(80 + depth_factor * 100 - np.random.randint(0, 30))
            
            # Add some noise
            if np.random.random() > 0.95:
                r += np.random.randint(-20, 20)
                g += np.random.randint(-20, 20)
                b += np.random.randint(-20, 20)
            
            pixels[i, j] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
    
    return img

def estimate_depth(image, idx):
    """Estimate depth from image"""
    print(f"\n  🔮 Processing image {idx}...")
    
    try:
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        print(f"     Image size: {image.size}")
        
        # Process
        inputs = processor(images=image, return_tensors="pt")
        
        with torch.no_grad():
            outputs = base_model(**inputs)
            depth_map = outputs.predicted_depth.squeeze().cpu().numpy()
        
        print(f"     ✅ Depth map shape: {depth_map.shape}")
        
        # Calculate statistics
        depth_min = depth_map.min()
        depth_max = depth_map.max()
        depth_mean = depth_map.mean()
        depth_std = depth_map.std()
        
        print(f"     📊 Depth range: [{depth_min:.4f}, {depth_max:.4f}]")
        print(f"     📊 Mean depth: {depth_mean:.4f} ± {depth_std:.4f}")
        
        return depth_map, (depth_min, depth_max, depth_mean, depth_std)
    
    except Exception as e:
        print(f"     ❌ Error: {e}")
        return None, None

def save_depth_map(depth_map, image, idx, stats):
    """Save depth map visualization"""
    depth_min, depth_max, depth_mean, depth_std = stats
    
    # Normalize for visualization
    depth_normalized = (depth_map - depth_min) / (depth_max - depth_min + 1e-8)
    
    # Create figure with multiple subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    
    # Original image
    axes[0, 0].imshow(image)
    axes[0, 0].set_title('Original Image')
    axes[0, 0].axis('off')
    
    # Depth map with plasma colormap
    im1 = axes[0, 1].imshow(depth_normalized, cmap='plasma')
    axes[0, 1].set_title('Depth Map (Plasma)')
    axes[0, 1].axis('off')
    plt.colorbar(im1, ax=axes[0, 1])
    
    # Depth map with viridis colormap
    im2 = axes[1, 0].imshow(depth_normalized, cmap='viridis')
    axes[1, 0].set_title('Depth Map (Viridis)')
    axes[1, 0].axis('off')
    plt.colorbar(im2, ax=axes[1, 0])
    
    # Statistics text
    stats_text = f"""Depth Statistics
Min: {depth_min:.4f}
Max: {depth_max:.4f}
Mean: {depth_mean:.4f}
Std Dev: {depth_std:.4f}
Range: {depth_max - depth_min:.4f}"""
    
    axes[1, 1].text(0.1, 0.5, stats_text, fontsize=12, family='monospace',
                   verticalalignment='center', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    axes[1, 1].axis('off')
    
    output_path = OUTPUT_DIR / f"depth_result_{idx}.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"     💾 Saved visualization to: {output_path}")
    return output_path

# --- Download Images ---
print("\n" + "=" * 80)
print("📥 DOWNLOADING IMAGES FROM GITHUB")
print("=" * 80)

image_paths = []

# Try to download from GitHub
for idx, url in enumerate(GITHUB_IMAGE_URLS):
    if url:
        save_path = INPUT_DIR / f"github_image_{idx}.jpg"
        if download_image(url, save_path):
            image_paths.append(save_path)

# Generate synthetic images if needed
if len(image_paths) < 3:
    print("\n📝 Generating synthetic underwater images for demonstration...")
    for idx in range(3):
        img = create_synthetic_underwater_image(idx)
        save_path = INPUT_DIR / f"synthetic_underwater_{idx}.jpg"
        img.save(save_path)
        image_paths.append(save_path)
        print(f"  ✅ Saved synthetic image to: {save_path}")

# --- Process Images ---
print("\n" + "=" * 80)
print("🔄 PROCESSING IMAGES THROUGH DEPTH ANYTHING")
print("=" * 80)

results = []

for idx, image_path in enumerate(image_paths):
    print(f"\n🖼️  Image {idx + 1}/{len(image_paths)}")
    print(f"   File: {image_path.name}")
    
    try:
        # Load image
        image = Image.open(image_path).convert('RGB')
        
        # Estimate depth
        depth_map, stats = estimate_depth(image, idx)
        
        if depth_map is not None:
            # Save visualization
            output_path = save_depth_map(depth_map, image, idx, stats)
            results.append({
                'input': str(image_path),
                'output': str(output_path),
                'stats': {
                    'min': float(stats[0]),
                    'max': float(stats[1]),
                    'mean': float(stats[2]),
                    'std': float(stats[3])
                }
            })
        else:
            print(f"   ⚠️  Depth estimation failed for image {idx}")
    
    except Exception as e:
        print(f"   ❌ Error processing image: {e}")
        import traceback
        traceback.print_exc()

# --- Generate Report ---
print("\n" + "=" * 80)
print("📋 GENERATING REPORT")
print("=" * 80)

report_path = OUTPUT_DIR / "processing_report.json"
with open(report_path, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n✅ Report saved to: {report_path}")
print(f"✅ Total images processed: {len(results)}")
print(f"✅ Results saved in: {OUTPUT_DIR}")

# --- Summary ---
print("\n" + "=" * 80)
print("📊 PROCESSING SUMMARY")
print("=" * 80)

for idx, result in enumerate(results):
    print(f"\nImage {idx + 1}:")
    print(f"  Input:  {Path(result['input']).name}")
    print(f"  Output: {Path(result['output']).name}")
    stats = result['stats']
    print(f"  Depth Range: [{stats['min']:.4f}, {stats['max']:.4f}]")
    print(f"  Mean Depth:  {stats['mean']:.4f} ± {stats['std']:.4f}")

print(f"\n🎉 All results saved in: {OUTPUT_DIR}")
print("=" * 80)

# Restore original find_spec
importlib.util.find_spec = original_find_spec
