#!/usr/bin/env python3
import sys
import os
import types
import importlib
import torch
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import base64
from io import BytesIO

# Add the subfolder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Underwater_Depth_Estimation'))

# --- Mock soundfile to avoid errors ---
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

# --- Import Gradio ---
import gradio as gr
from transformers import AutoImageProcessor, AutoModelForDepthEstimation

# --- Load Model ---
print("Loading Depth Anything model...")
model_checkpoint = "depth-anything/Depth-Anything-V2-Small-hf"
base_model = AutoModelForDepthEstimation.from_pretrained(model_checkpoint)
processor = AutoImageProcessor.from_pretrained(model_checkpoint)
print("✅ Model loaded successfully!")

# Store current depth map
current_depth_map = None

# --- Helper functions ---
def convert_to_pil(image):
    if image is None:
        return None
    
    if isinstance(image, Image.Image):
        return image.convert('RGB')
    
    if isinstance(image, np.ndarray):
        if len(image.shape) == 3 and image.shape[-1] == 4:
            image = Image.fromarray(image).convert('RGB')
        else:
            image = Image.fromarray(image)
        return image.convert('RGB')
    
    if hasattr(image, 'name'):
        image_path = image.name
    elif isinstance(image, str):
        image_path = image
    else:
        return None
    
    try:
        image = Image.open(image_path)
        return image.convert('RGB')
    except Exception as e:
        raise ValueError(f"Error opening image: {e}")

# --- Prediction Function ---
def predict_depth(image, colormap="plasma"):
    global current_depth_map
    
    if image is None:
        return None, "No image uploaded.", ""
    
    try:
        original_image = convert_to_pil(image)
        
        inputs = processor(images=original_image, return_tensors="pt")
        
        with torch.no_grad():
            outputs = base_model(**inputs)
            depth_map = outputs.predicted_depth.squeeze().cpu().numpy()
        
        current_depth_map = depth_map
        
        # Create static colored depth map
        depth_normalized = (depth_map - depth_map.min()) / (depth_map.max() - depth_map.min())
        colored_depth = (plt.cm.get_cmap(colormap)(depth_normalized)[:, :, :3] * 255).astype(np.uint8)
        
        # Generate statistics
        abs_rel = np.mean(np.abs(depth_map - np.median(depth_map)) / (depth_map + 1e-8))
        rmse = np.sqrt(np.mean((depth_map - np.median(depth_map))**2))
        threshold = 1.25
        ratio = np.maximum(depth_map / (depth_map.max() + 1e-8), 
                          (depth_map.max() + 1e-8) / (depth_map + 1e-8))
        delta1 = np.mean(ratio < threshold)
        
        stats_text = f"""
### 📊 Depth Statistics

| Metric | Value |
|--------|-------|
| **Min (Farthest)** | `{depth_map.min():.4f}` |
| **Max (Closest)** | `{depth_map.max():.4f}` |
| **Mean** | `{depth_map.mean():.4f}` |
| **Std Dev** | `{depth_map.std():.4f}` |

**Reference Metrics:**
- **AbsRel ↓** : `{abs_rel:.4f}`
- **RMSE ↓** : `{rmse:.4f}` 
- **δ1 ↑** : `{delta1:.4f}`

> **Note:** Higher number = closer to camera.
"""
        
        return colored_depth, stats_text
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None, f"❌ Error: {str(e)}"

# --- Function to get depth at coordinates from click ---
def get_depth_at_coordinates(x, y):
    global current_depth_map
    
    if current_depth_map is None:
        return "No depth map loaded. Please estimate depth first."
    
    if x is None or y is None:
        return "Click on the depth map to see values."
    
    try:
        x = int(x)
        y = int(y)
        if 0 <= x < current_depth_map.shape[1] and 0 <= y < current_depth_map.shape[0]:
            value = current_depth_map[y, x]
            normalized = (value - current_depth_map.min()) / (current_depth_map.max() - current_depth_map.min())
            return f"""
### 📍 Depth at Click Location

| Property | Value |
|----------|-------|
| **Position** | ({x}, {y}) |
| **Relative Depth** | `{value:.4f}` |
| **Normalized (0-1)** | `{normalized:.3f}` |
| **Interpretation** | {'🟡 Closer to camera' if normalized > 0.5 else '🟣 Farther from camera'} |
"""
        return f"Position ({x}, {y}) is out of bounds."
    except Exception as e:
        return f"Error: {str(e)}"

# --- Create Web Interface ---
with gr.Blocks(title="Underwater Depth Estimator") as demo:
    gr.Markdown("""
    # 🌊 Underwater Depth Estimator
    
    **Upload an underwater image to estimate its depth map.**
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            input_image = gr.Image(label="📸 Upload Image", type="filepath")
            
            colormap_choice = gr.Dropdown(
                choices=["plasma", "viridis", "inferno", "magma", "cividis", "turbo"],
                value="plasma",
                label="🎨 Color Map"
            )
            
            submit_btn = gr.Button("🔮 Estimate Depth", variant="primary")
            clear_btn = gr.Button("🗑️ Clear")
            
        with gr.Column(scale=1):
            output_static = gr.Image(label="🗺️ Depth Map")
    
    with gr.Row():
        with gr.Column(scale=1):
            # Click coordinate inputs (manual entry or click via JS)
            click_x = gr.Number(label="Click X Position", value=None, precision=0)
            click_y = gr.Number(label="Click Y Position", value=None, precision=0)
            get_depth_btn = gr.Button("📍 Get Depth at Position")
            depth_value = gr.Markdown("**Enter X,Y coordinates and click 'Get Depth'**")
            
        with gr.Column(scale=1):
            stats_output = gr.Markdown(label="📈 Statistics")
    
    # Wire up predictions
    submit_btn.click(
        fn=predict_depth,
        inputs=[input_image, colormap_choice],
        outputs=[output_static, stats_output]
    )
    
    # Get depth when button is clicked
    get_depth_btn.click(
        fn=get_depth_at_coordinates,
        inputs=[click_x, click_y],
        outputs=[depth_value]
    )
    
    clear_btn.click(
        fn=lambda: (None, None, None, None, "", "Enter X,Y coordinates and click 'Get Depth'"),
        outputs=[input_image, output_static, click_x, click_y, stats_output, depth_value]
    )
    
    gr.Markdown("""
    ---
    ### 📝 Instructions:
    1. **Upload** an underwater image
    2. **Click** "Estimate Depth"
    3. **To get depth at a specific point:** Enter X and Y coordinates, then click "Get Depth at Position"
    
    > **Tip:** X = horizontal position (0 = left edge), Y = vertical position (0 = top edge)
    """)

# --- Launch ---
if __name__ == "__main__":
    demo.launch(share=False, server_port=7860)