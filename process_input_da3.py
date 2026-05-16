#!/usr/bin/env python3
"""
Process images from Input_DA3 folder and save results to Output_DA3
Uses Depth Anything V2 model for underwater depth estimation
"""

import sys
import importlib
import types
import os
from pathlib import Path
import json

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

# Setup paths
INPUT_DIR = Path("./Input_DA3")
OUTPUT_DIR = Path("./Output_DA3")
OUTPUT_DIR.mkdir(exist_ok=True)

print("=" * 80)
print("🌊 PROCESSING IMAGES FROM Input_DA3 → Output_DA3")
print("=" * 80)

# Load Model
print("\n📦 Loading Depth Anything model...")
model_checkpoint = "depth-anything/Depth-Anything-V2-Small-hf"
base_model = AutoModelForDepthEstimation.from_pretrained(model_checkpoint)
processor = AutoImageProcessor.from_pretrained(model_checkpoint)
base_model.eval()
print("✅ Model loaded successfully!")

# Get all image files
image_extensions = {'.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG'}
image_files = sorted([f for f in INPUT_DIR.iterdir() if f.suffix in image_extensions])

print(f"\n📊 Found {len(image_files)} images in Input_DA3/")
for img_file in image_files:
    print(f"   • {img_file.name}")

# Process each image
results = []

print("\n" + "=" * 80)
print("🔄 PROCESSING IMAGES")
print("=" * 80)

for idx, image_path in enumerate(image_files, 1):
    print(f"\n🖼️  [{idx}/{len(image_files)}] {image_path.name}")
    
    try:
        # Load image
        image = Image.open(image_path).convert('RGB')
        print(f"   ✓ Loaded image size: {image.size}")
        
        # Process through model
        inputs = processor(images=image, return_tensors="pt")
        
        with torch.no_grad():
            outputs = base_model(**inputs)
            depth_map = outputs.predicted_depth.squeeze().cpu().numpy()
        
        print(f"   ✓ Depth map generated: {depth_map.shape}")
        
        # Calculate statistics
        depth_min = depth_map.min()
        depth_max = depth_map.max()
        depth_mean = depth_map.mean()
        depth_std = depth_map.std()
        depth_median = np.median(depth_map)
        
        print(f"   ✓ Depth range: [{depth_min:.4f}, {depth_max:.4f}]")
        print(f"   ✓ Mean depth: {depth_mean:.4f} ± {depth_std:.4f}")
        
        # Normalize for visualization
        depth_normalized = (depth_map - depth_min) / (depth_max - depth_min + 1e-8)
        
        # Create output filename
        output_name = image_path.stem
        
        # Save visualizations with multiple colormaps
        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        fig.suptitle(f'Depth Analysis - {image_path.name}', fontsize=16, fontweight='bold')
        
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
        
        # Statistics panel
        stats_text = f"""
DEPTH STATISTICS

Range Analysis:
  Min: {depth_min:.6f}
  Max: {depth_max:.6f}
  Range: {depth_max - depth_min:.6f}

Distribution:
  Mean: {depth_mean:.6f}
  Median: {depth_median:.6f}
  Std Dev: {depth_std:.6f}

Image: {image.size}
Depth Map: {depth_map.shape}
"""
        
        axes[1, 2].text(0.05, 0.95, stats_text, fontsize=9, family='monospace',
                       verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        axes[1, 2].axis('off')
        
        # Save visualization
        output_viz = OUTPUT_DIR / f"{output_name}_depth_analysis.png"
        plt.tight_layout()
        plt.savefig(output_viz, dpi=100, bbox_inches='tight')
        plt.close()
        print(f"   ✓ Saved visualization: {output_viz.name}")
        
        # Save depth map as raw numpy data (for further processing)
        output_npy = OUTPUT_DIR / f"{output_name}_depthmap.npy"
        np.save(output_npy, depth_map)
        print(f"   ✓ Saved depth map data: {output_npy.name}")
        
        # Save colorized depth map
        colored_depth = (plt.cm.get_cmap('plasma')(depth_normalized)[:, :, :3] * 255).astype(np.uint8)
        output_colored = OUTPUT_DIR / f"{output_name}_colored_depth.png"
        Image.fromarray(colored_depth).save(output_colored)
        print(f"   ✓ Saved colored depth: {output_colored.name}")
        
        # Store result
        results.append({
            'input': image_path.name,
            'visualization': output_viz.name,
            'depthmap': output_npy.name,
            'colored_depth': output_colored.name,
            'stats': {
                'min': float(depth_min),
                'max': float(depth_max),
                'mean': float(depth_mean),
                'std': float(depth_std),
                'median': float(depth_median),
                'image_size': list(image.size),
                'depth_shape': list(depth_map.shape)
            }
        })
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()

# Generate summary report
print("\n" + "=" * 80)
print("📋 GENERATING REPORT")
print("=" * 80)

report_path = OUTPUT_DIR / "processing_report.json"
with open(report_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\n✅ Report saved: {report_path.name}")

# Create markdown summary
summary_md = OUTPUT_DIR / "RESULTS_SUMMARY.md"
with open(summary_md, 'w') as f:
    f.write("# 🌊 Depth Estimation Results\n\n")
    f.write(f"**Processing Date:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"**Model:** Depth Anything V2-Small\n")
    f.write(f"**Total Images Processed:** {len(results)}\n\n")
    
    f.write("## Results\n\n")
    for i, result in enumerate(results, 1):
        f.write(f"### {i}. {result['input']}\n\n")
        f.write(f"**Files Generated:**\n")
        f.write(f"- Visualization: `{result['visualization']}`\n")
        f.write(f"- Colored Depth: `{result['colored_depth']}`\n")
        f.write(f"- Raw Depth Data: `{result['depthmap']}`\n\n")
        
        stats = result['stats']
        f.write("**Statistics:**\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Min Depth | {stats['min']:.6f} |\n")
        f.write(f"| Max Depth | {stats['max']:.6f} |\n")
        f.write(f"| Mean Depth | {stats['mean']:.6f} |\n")
        f.write(f"| Median Depth | {stats['median']:.6f} |\n")
        f.write(f"| Std Dev | {stats['std']:.6f} |\n")
        f.write(f"| Image Size | {stats['image_size']} |\n")
        f.write(f"| Depth Map Size | {stats['depth_shape']} |\n\n")

print(f"✅ Summary saved: {summary_md.name}")

# Display final summary
print("\n" + "=" * 80)
print("📊 PROCESSING COMPLETE")
print("=" * 80)

print(f"\n✅ Successfully processed {len(results)} images!")
print(f"📁 Results saved in: {OUTPUT_DIR}")
print(f"\n📁 Output files generated:")
for result in results:
    print(f"   • {result['input']}")
    print(f"     ├─ {result['visualization']} (6-panel analysis)")
    print(f"     ├─ {result['colored_depth']} (colored depth map)")
    print(f"     └─ {result['depthmap']} (raw depth data)")

print(f"\n📄 Reports generated:")
print(f"   • processing_report.json (structured data)")
print(f"   • RESULTS_SUMMARY.md (markdown report)")

print(f"\n🎉 All results ready in Output_DA3/")

importlib.util.find_spec = original_find_spec
