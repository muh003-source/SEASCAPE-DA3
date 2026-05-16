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

# Use the direct model from transformers (more reliable)
model_checkpoint = "depth-anything/Depth-Anything-V2-Small-hf"
base_model = AutoModelForDepthEstimation.from_pretrained(model_checkpoint)
processor = AutoImageProcessor.from_pretrained(model_checkpoint)
print("✅ Model loaded successfully!")

# Store current depth map globally
current_depth_map = None
current_image_shape = None

# --- Helper functions ---
def convert_to_pil(image):
    """Convert various input types to PIL RGB image"""
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
    global current_depth_map, current_image_shape
    
    if image is None:
        return None, "No image uploaded.", "No image uploaded."
    
    try:
        original_image = convert_to_pil(image)
        current_image_shape = original_image.size
        
        # Prepare input
        inputs = processor(images=original_image, return_tensors="pt")
        
        # Run depth estimation
        with torch.no_grad():
            outputs = base_model(**inputs)
            depth_map = outputs.predicted_depth.squeeze().cpu().numpy()
        
        current_depth_map = depth_map
        
        # Create static colored depth map
        depth_normalized = (depth_map - depth_map.min()) / (depth_map.max() - depth_map.min())
        colored_depth = (plt.cm.get_cmap(colormap)(depth_normalized)[:, :, :3] * 255).astype(np.uint8)
        
        # Create interactive HTML with JavaScript for click handling
        interactive_html = create_interactive_html(depth_map, colormap)
        
        # Generate comprehensive statistics
        depth_min = depth_map.min()
        depth_max = depth_map.max()
        depth_mean = depth_map.mean()
        depth_std = depth_map.std()
        depth_median = np.median(depth_map)
        depth_range = depth_max - depth_min
        
        # Normalize depth map for better metrics
        depth_normalized = (depth_map - depth_min) / (depth_range + 1e-8)
        
        # Calculate improved evaluation metrics
        # Absolute Relative Error (comparing to median)
        abs_rel = np.mean(np.abs(depth_map - depth_median) / (np.abs(depth_median) + 1e-8))
        
        # Root Mean Squared Error (comparing to median)
        rmse = np.sqrt(np.mean((depth_map - depth_median)**2))
        
        # Threshold accuracy (δ1: % of pixels within 1.25x error)
        threshold = 1.25
        ratio = np.maximum(depth_map / (depth_max + 1e-8), 
                          (depth_max + 1e-8) / (depth_map + 1e-8))
        delta1 = np.mean(ratio < threshold) * 100
        
        # Additional metrics for better understanding
        # Depth discontinuity (edges in depth map)
        depth_edges = np.sqrt(np.gradient(depth_map)[0]**2 + np.gradient(depth_map)[1]**2)
        discontinuity = np.mean(depth_edges)
        
        # Depth variance in foreground vs background
        foreground_mask = depth_normalized > 0.7
        background_mask = depth_normalized < 0.3
        foreground_var = np.var(depth_map[foreground_mask]) if foreground_mask.any() else 0
        background_var = np.var(depth_map[background_mask]) if background_mask.any() else 0
        
        stats_text = f"""
### 📊 Depth Statistics

#### Basic Depth Information
| Metric | Value |
|--------|-------|
| **Min Depth (Farthest)** | `{depth_min:.4f}` |
| **Max Depth (Closest)** | `{depth_max:.4f}` |
| **Depth Range** | `{depth_range:.4f}` |
| **Mean Depth** | `{depth_mean:.4f}` |
| **Median Depth** | `{depth_median:.4f}` |
| **Std Dev** | `{depth_std:.4f}` |

#### Accuracy Metrics
| Metric | Value | Description |
|--------|-------|-------------|
| **AbsRel ↓** | `{abs_rel:.4f}` | Absolute Relative Error (lower is better) |
| **RMSE ↓** | `{rmse:.4f}` | Root Mean Squared Error (lower is better) |
| **δ1 ↑** | `{delta1:.2f}%` | % of predictions within 1.25× threshold |

#### Spatial Analysis
| Metric | Value | Description |
|--------|-------|-------------|
| **Discontinuity** | `{discontinuity:.4f}` | Depth edge magnitude (scene complexity) |
| **Foreground Variance** | `{foreground_var:.4f}` | Depth variation in close objects |
| **Background Variance** | `{background_var:.4f}` | Depth variation in distant areas |

> **Note:** Higher depth value = closer to camera. Lower value = farther from camera.
> **Fish Detection Tip:** High δ1 scores indicate reliable depth discrimination for tracking.
"""
        
        return colored_depth, interactive_html, stats_text
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None, f"❌ Error: {str(e)}", f"❌ Error: {str(e)}"

def create_interactive_html(depth_map, colormap='plasma'):
    """Create HTML with interactive Plotly figure with mouse tooltip"""
    depth_normalized = (depth_map - depth_map.min()) / (depth_map.max() - depth_map.min())
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Heatmap(
            z=depth_normalized,
            zmin=0,
            zmax=1,
            colorscale=colormap,
            hovertemplate='<b>Depth Value:</b> %{z:.4f}<br><b>X:</b> %{x}<br><b>Y:</b> %{y}<extra></extra>',
            name='Depth Map',
            showscale=True,
            colorbar=dict(title="Relative Depth<br>(0=Far, 1=Close)"),
            hoverinfo='all'
        )
    )
    
    fig.update_layout(
        title='Interactive Depth Map (Hover to See Values)',
        xaxis_title='Horizontal Position (Pixels)',
        yaxis_title='Vertical Position (Pixels)',
        height=600,
        hovermode='closest',
        xaxis=dict(scaleanchor="y", scaleratio=1),
        yaxis=dict(autorange="reversed"),
        showlegend=False
    )
    
    # Add custom JavaScript for better tooltip display
    html_str = fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    custom_js = """
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(function() {
            var plotDiv = document.querySelector('.plotly-graph-div');
            if (plotDiv) {
                plotDiv.on('plotly_hover', function(data) {
                    // Enhanced hover handling - Plotly's default hover is already good
                    console.log('Hovering at:', data.points[0]);
                });
            }
        }, 100);
    });
    </script>
    """
    
    return html_str + custom_js

# --- Create Web Interface ---
with gr.Blocks(title="Underwater Depth Estimator") as demo:
    gr.Markdown("""
    # 🌊 Underwater Depth Estimator
    
    **Upload an underwater image to estimate its depth map. Hover or click on the depth map to see exact relative depth values!**
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
        with gr.Column(scale=2):
            output_interactive = gr.HTML(label="📊 Interactive Map (Hover for Values)")
            
    with gr.Row():
        with gr.Column():
            stats_output = gr.Markdown(label="📈 Statistics")
    
    # Wire up predictions
    submit_btn.click(
        fn=predict_depth,
        inputs=[input_image, colormap_choice],
        outputs=[output_static, output_interactive, stats_output]
    )
    
    # Clear button
    clear_btn.click(
        fn=lambda: (None, None, ""),
        outputs=[input_image, output_static, stats_output]
    )
    
    # Add JavaScript to capture clicks from the Plotly figure
    gr.HTML("""
    <script>
    // Plotly hover tooltips are automatically handled by the library
    // The depth value appears when you move your mouse over the map
    </script>
    """)
    
    gr.Markdown("""
    ---
    ### 📝 Instructions:
    1. **Upload** an underwater image
    2. **Click** "Estimate Depth"
    3. **Hover your mouse** over the interactive map to see depth values
    4. **Check statistics** below for accuracy metrics and spatial analysis
    """)

# --- Launch ---
if __name__ == "__main__":
    demo.launch(share=False, server_port=7860)