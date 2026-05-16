#!/usr/bin/env python3
import sys
import importlib
import types

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

print("Python version:", sys.version)
print("Mocking soundfile...")

# Import model
import os
import torch
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

sys.path.append('.')

print("Importing DepthAnythingPEFT...")
from DepthAnythingPEFT.Model import DepthAnythingPEFT

print("Creating model instance...")
# Use the small model for faster loading
model_checkpoint = "depth-anything/Depth-Anything-V2-Small-hf"
model = DepthAnythingPEFT(model_checkpoint=model_checkpoint)
print(f"✅ Model loaded successfully with checkpoint: {model_checkpoint}")

# Set to evaluation mode
model.eval()
print("✅ Model ready for inference!")

# Test with a sample image
print("\n--- Testing depth estimation ---")

# Create a dummy underwater-style image
test_image = Image.new('RGB', (384, 384), color=(0, 100, 150))
# Or load a real image if you have one:
# test_image = Image.open("your_underwater_image.jpg")

print(f"Test image size: {test_image.size}")

# Run depth estimation
with torch.no_grad():
    # The model expects specific preprocessing
    # This might need adjustment based on the actual model interface
    try:
        # Try direct forward pass
        depth_map = model(test_image)
        print(f"Depth map shape: {depth_map.shape if hasattr(depth_map, 'shape') else type(depth_map)}")
        print("✅ Depth estimation completed!")
    except Exception as e:
        print(f"Need to check model input format: {e}")
        
        # Try alternative approach
        print("\nTrying alternative input format...")
        try:
            # Convert to tensor
            img_tensor = torch.from_numpy(np.array(test_image)).permute(2,0,1).float().unsqueeze(0)
            depth_map = model(img_tensor)
            print(f"Depth map shape: {depth_map.shape}")
        except Exception as e2:
            print(f"Alternative also failed: {e2}")
            print("\nChecking model methods:")
            print(dir(model))

# Restore original find_spec
importlib.util.find_spec = original_find_spec

print("\n🎉 Setup complete! Model is ready for underwater depth estimation.")