#!/usr/bin/env python3
import sys
import importlib
import types

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

print("Python version:", sys.version)

# Import model
import torch
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

sys.path.append('.')

print("Importing DepthAnythingPEFT...")
from DepthAnythingPEFT.Model import DepthAnythingPEFT

print("Creating model instance...")
model_checkpoint = "depth-anything/Depth-Anything-V2-Small-hf"
peft_model = DepthAnythingPEFT(model_checkpoint=model_checkpoint)
print(f"✅ Model loaded successfully!")

# Access the actual depth estimation model
base_model = peft_model.model
print(f"Base model type: {type(base_model)}")

# Check what the base model can do
print(f"\nBase model methods:")
methods = [m for m in dir(base_model) if not m.startswith('_') and callable(getattr(base_model, m))]
for method in methods[:15]:
    print(f"  - {method}")

# Try to use the base model for depth estimation
print("\n--- Testing depth estimation with base model ---")

# Create a test image
test_array = np.zeros((384, 384, 3), dtype=np.uint8)
test_array[:, :, 0] = 50   # Red (attenuated underwater)
test_array[:, :, 1] = 100  # Green
test_array[:, :, 2] = 200  # Blue (penetrates best)
test_image = Image.fromarray(test_array)

print(f"Test image size: {test_image.size}")

# Method 1: Try using the base model's forward method
with torch.no_grad():
    try:
        # Convert image to tensor
        from transformers import AutoImageProcessor
        processor = AutoImageProcessor.from_pretrained(model_checkpoint)
        inputs = processor(images=test_image, return_tensors="pt")
        
        print(f"Input shape: {inputs['pixel_values'].shape}")
        
        # Forward pass
        outputs = base_model(**inputs)
        print(f"✅ Depth estimation successful!")
        print(f"Output type: {type(outputs)}")
        
        if hasattr(outputs, 'predicted_depth'):
            depth = outputs.predicted_depth
            print(f"Depth map shape: {depth.shape}")
            
            # Visualize the depth map
            depth_np = depth.squeeze().cpu().numpy()
            print(f"Depth range: {depth_np.min():.3f} - {depth_np.max():.3f}")
            
            # Plot
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
            ax1.imshow(test_array)
            ax1.set_title('Input Image')
            ax1.axis('off')
            
            im = ax2.imshow(depth_np, cmap='plasma')
            ax2.set_title('Depth Map')
            ax2.axis('off')
            plt.colorbar(im, ax=ax2)
            plt.show()
            
        elif isinstance(outputs, dict):
            print(f"Output keys: {outputs.keys()}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

print("\n🎉 Done!")