from flask import Flask, render_template, request, jsonify
from roboflow import Roboflow
import os
import json
from werkzeug.utils import secure_filename
from pathlib import Path
import requests
from PIL import Image
from io import BytesIO
import mimetypes

# =========================
# CONFIG
# =========================
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}

# Roboflow config
API_KEY = "YOUR_API_KEY" #Change with your api key
WORKSPACE = "YOUR_WORKSPACE_NAME" #Change with your workspace name

# All project models configuration
MODELS_CONFIG = [
    {
        'name': 'plant-leaf-detection',
        'project_id': 'plant-leaf-detection-yb5mn-lohga',
        'version': 1,
        'type': 'leaf_detection'
    },
    {
        'name': 'plantdoc',
        'project_id': 'plantdoc-kgjr7',
        'version': 1,
        'type': 'disease_detection'
    },
    {
        'name': 'leaf-detection-02',
        'project_id': 'leaf_detection_02-fo6hg',
        'version': 1,
        'type': 'leaf_detection'
    },
    {
        'name': 'leaf-detection',
        'project_id': 'leaf-rhr7e-kq9f5',
        'version': 1,
        'type': 'leaf_detection'
    }
]

# Load all Roboflow models
models = {}
try:
    rf = Roboflow(api_key=API_KEY)
    for model_config in MODELS_CONFIG:
        try:
            project = rf.workspace(WORKSPACE).project(model_config['project_id'])
            model = project.version(model_config['version']).model
            models[model_config['name']] = {
                'model': model,
                'config': model_config
            }
            print(f"✓ Loaded model: {model_config['name']}")
        except Exception as e:
            print(f"✗ Warning: Could not load model {model_config['name']}: {e}")
except Exception as e:
    print(f"✗ Warning: Could not initialize Roboflow: {e}")

# =========================
# HELPER FUNCTIONS
# =========================
def extract_leaf_type(class_name):
    """Extract leaf type from class name"""
    leaf_type = class_name.split('___')[0].replace('_', ' ')
    return leaf_type.strip()

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_image(file_path):
    """Validate that file is actually an image"""
    try:
        with Image.open(file_path) as img:
            img.verify()
        return True
    except Exception as e:
        return False

def process_prediction(result, model_name):
    """Process raw prediction result from a single model"""
    if result.get('predictions') and result['predictions']:
        predictions = result['predictions']
        top_prediction = predictions[0]
        class_name = top_prediction.get('class', 'Unknown')
        confidence = top_prediction.get('confidence', 0)
        
        return {
            'model_name': model_name,
            'success': True,
            'plant_name': extract_leaf_type(class_name),
            'condition': class_name.split('___')[1] if '___' in class_name else 'Unknown',
            'full_class': class_name,
            'confidence': round(float(confidence), 4),
            'all_predictions': predictions
        }
    else:
        return {
            'model_name': model_name,
            'success': False,
            'error': 'No predictions found'
        }

def run_all_predictions(filepath):
    """Run predictions on all loaded models"""
    all_results = {
        'image_path': filepath,
        'total_models': len(models),
        'models_loaded': len(models),
        'predictions': [],
        'success': False
    }
    
    if not models:
        all_results['error'] = 'No models loaded'
        return all_results
    
    for model_name, model_data in models.items():
        try:
            model = model_data['model']
            config = model_data['config']
            
            # Run prediction
            result = model.predict(filepath, confidence=40, overlap=30).json()
            prediction = process_prediction(result, model_name)
            prediction['model_type'] = config['type']
            all_results['predictions'].append(prediction)
        except Exception as e:
            all_results['predictions'].append({
                'model_name': model_name,
                'success': False,
                'error': str(e)
            })
    
    # Mark as success if at least one model made a prediction
    all_results['success'] = any(p.get('success', False) for p in all_results['predictions'])
    return all_results

def cleanup_old_files():
    """Clean up old files from the uploads folder"""
    import time
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        now = time.time()
        # Delete files older than 1 hour
        for filename in os.listdir(upload_folder):
            filepath = os.path.join(upload_folder, filename)
            if os.path.isfile(filepath):
                if os.stat(filepath).st_mtime < now - 3600:
                    try:
                        os.remove(filepath)
                    except Exception as e:
                        print(f"Could not delete {filepath}: {e}")
    except Exception as e:
        print(f"Cleanup error: {e}")

# =========================
# ROUTES
# =========================
@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/api/predict', methods=['POST'])
def predict():
    """Handle file upload and prediction from all models"""
    if not models:
        return jsonify({'error': 'No models loaded'}), 500
    
    filepath = None
    try:
        # Cleanup old files first
        cleanup_old_files()
        
        # Check if file in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Allowed: png, jpg, jpeg, gif, webp, bmp'}), 400
        
        # Save file with unique name to avoid conflicts
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"upload_{os.urandom(16).hex()}.{file_ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # Validate image
        if not validate_image(filepath):
            os.remove(filepath)
            return jsonify({'error': 'File is not a valid image'}), 400
        
        # Run predictions from all models
        predictions = run_all_predictions(filepath)
        
        return jsonify(predictions)
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500
    finally:
        # Clean up file after processing
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Warning: Could not clean up file {filepath}: {e}")

@app.route('/api/predict-url', methods=['POST'])
def predict_url():
    """Handle URL image prediction from all models"""
    if not models:
        return jsonify({'error': 'No models loaded'}), 500
    
    filepath = None
    try:
        # Cleanup old files first
        cleanup_old_files()
        
        data = request.get_json()
        image_url = data.get('url', '').strip()
        
        if not image_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        # Download image from URL
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        
        # Validate content type
        content_type = response.headers.get('content-type', '')
        if 'image' not in content_type:
            return jsonify({'error': 'URL does not point to an image'}), 400
        
        # Save temporary file with unique name
        img = Image.open(BytesIO(response.content))
        temp_filename = f"temp_{os.urandom(16).hex()}.png"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
        img.save(filepath)
        img.close()  # Close image explicitly
        
        # Run predictions from all models
        predictions = run_all_predictions(filepath)
        
        return jsonify(predictions)
    
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to download image: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500
    finally:
        # Clean up file after processing
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Warning: Could not clean up file {filepath}: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

