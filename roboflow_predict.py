from roboflow import Roboflow
import json
import re

# =========================
# CONFIG
# =========================
API_KEY = "X5C8pMt0QHFOyfjWN9sW"
WORKSPACE = "mpblitz"
PROJECT = "plantdoc-kgjr7"
VERSION = 1   # change if needed

# =========================
# LOAD MODEL
# =========================
rf = Roboflow(api_key=API_KEY)
project = rf.workspace(WORKSPACE).project(PROJECT)
model = project.version(VERSION).model

# =========================
# HELPER FUNCTIONS
# =========================
def extract_leaf_type(class_name):
    """Extract leaf type from class name"""
    # Remove common suffixes and extract the plant name
    leaf_type = class_name.split('___')[0].replace('_', ' ')
    return leaf_type.strip()

# =========================
# PREDICT
# =========================
image_path = input("Enter image path: ").strip()

result = model.predict(image_path, confidence=40, overlap=30).json()

# Extract leaf type from predictions
if result.get('predictions'):
    predictions = result['predictions']
    if predictions:
        class_name = predictions[0].get('class', 'Unknown')
        leaf_type = extract_leaf_type(class_name)
        confidence = predictions[0].get('confidence', 0)
        
        print("\n===== Leaf Type Detection =====")
        print(f"Leaf Type: {leaf_type}")
        print(f"Confidence: {confidence:.2%}")
        print(f"Full Class: {class_name}")
else:
    print("\n===== Prediction Result =====")
    print(json.dumps(result, indent=4))
