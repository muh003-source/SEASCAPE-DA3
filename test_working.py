#!/usr/bin/env python3
import sys
import importlib
import types

# Mock soundfile (same as before)
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

# Import the model
import os
sys.path.append('.')

print("Importing DepthAnythingPEFT...")

try:
    from DepthAnythingPEFT.Model import DepthAnythingPEFT
    print("✅ Model imported successfully!")
    
    # Create model instance WITH checkpoint parameter
    print("Creating model instance...")
    # Use the Depth Anything base model
    model_checkpoint = "depth-anything/Depth-Anything-V2-Small-hf"  # or Base, Large
    model = DepthAnythingPEFT(model_checkpoint=model_checkpoint)
    print(f"✅ Model created successfully with checkpoint: {model_checkpoint}")
    
    # Print model info
    print(f"Model type: {type(model)}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Restore original find_spec
importlib.util.find_spec = original_find_spec