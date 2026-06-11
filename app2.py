# app.py
# Unified Smart Agro App (Disease + Crop Recommendation + Indoor Plant Species + Chatbot)
# ✅ Professional structure, clean imports, safe config, and indoor plant guide integration

import os
import cv2
import numpy as np
import pandas as pd
import joblib
import datetime
import traceback

from tensorflow.keras.models import load_model
from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename

import langdetect
from groq import Groq


# =========================================================
# CONFIG
# =========================================================
app = Flask(__name__)

app.config["UPLOAD_FOLDER"] = "static/uploads/"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB
app.config["SECRET_KEY"] = "smart-agro-secret"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# =========================================================
# IMPORT GUIDES (put these files in guides/ folder)
# =========================================================
# guides/disease_guides.py -> TREATMENT_GUIDE, DEFAULT_TREATMENT
# guides/crop_guides.py -> CROP_GUIDE
# guides/indoor_plant_guides.py -> INDOOR_PLANT_GUIDE

from guides.disease_guides import TREATMENT_GUIDE, DEFAULT_TREATMENT
from guides.crop_guides import CROP_GUIDE
import guides.indoor_plant_guides as indoor_guides
INDOOR_PLANT_GUIDE = indoor_guides.INDOOR_PLANT_GUIDE


# =========================================================
# GROQ CHATBOT CLIENT (IMPORTANT: use env var, not hardcoded key)
# =========================================================
# Set in terminal:
# Windows PowerShell:
#   setx GROQ_API_KEY "your_key_here"
# then reopen terminal
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


# =========================================================
# MODELS
# =========================================================
disease_model = None
indoor_model = None

# Disease class names (your PlantVillage classes)
CLASS_NAMES = [
    "Apple___Apple_scab", "Apple___Black_rot", "Apple___Cedar_apple_rust", "Apple___healthy",
    "Blueberry___healthy", "Cherry_(including_sour)___Powdery_mildew", "Cherry_(including_sour)___healthy",
    "Corn_(maize)___Cercospora_leaf_spot_Gray_leaf_spot", "Corn_(maize)___Common_rust_",
    "Corn_(maize)___Northern_Leaf_Blight", "Corn_(maize)___healthy", "Grape___Black_rot",
    "Grape___Esca_(Black_Measles)", "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)", "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)", "Peach___Bacterial_spot", "Peach___healthy",
    "Pepper,_bell___Bacterial_spot", "Pepper,_bell___healthy", "Potato___Early_blight",
    "Potato___Late_blight", "Potato___healthy", "Raspberry___healthy", "Soybean___healthy",
    "Squash___Powdery_mildew", "Strawberry___Leaf_scorch", "Strawberry___healthy",
    "Tomato___Bacterial_spot", "Tomato___Early_blight", "Tomato___Late_blight", "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot", "Tomato___Spider_mites_Two-spotted_spider_mite", "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "Tomato___Tomato_mosaic_virus", "Tomato___healthy"
]

# Indoor plant labels (47) — MUST match the training order exactly
INDOOR_LABELS = {
    "0": "African Violet (Saintpaulia ionantha)",
    "1": "Aloe Vera",
    "2": "Anthurium (Anthurium andraeanum)",
    "3": "Areca Palm (Dypsis lutescens)",
    "4": "Asparagus Fern (Asparagus setaceus)",
    "5": "Begonia (Begonia spp.)",
    "6": "Bird of Paradise (Strelitzia reginae)",
    "7": "Birds Nest Fern (Asplenium nidus)",
    "8": "Boston Fern (Nephrolepis exaltata)",
    "9": "Calathea",
    "10": "Cast Iron Plant (Aspidistra elatior)",
    "11": "Chinese Money Plant (Pilea peperomioides)",
    "12": "Chinese evergreen (Aglaonema)",
    "13": "Christmas Cactus (Schlumbergera bridgesii)",
    "14": "Chrysanthemum",
    "15": "Ctenanthe",
    "16": "Daffodils (Narcissus spp.)",
    "17": "Dracaena",
    "18": "Dumb Cane (Dieffenbachia spp.)",
    "19": "Elephant Ear (Alocasia spp.)",
    "20": "English Ivy (Hedera helix)",
    "21": "Hyacinth (Hyacinthus orientalis)",
    "22": "Iron Cross begonia (Begonia masoniana)",
    "23": "Jade plant (Crassula ovata)",
    "24": "Kalanchoe",
    "25": "Lilium (Hemerocallis)",
    "26": "Lily of the valley (Convallaria majalis)",
    "27": "Money Tree (Pachira aquatica)",
    "28": "Monstera Deliciosa (Monstera deliciosa)",
    "29": "Orchid",
    "30": "Parlor Palm (Chamaedorea elegans)",
    "31": "Peace lily",
    "32": "Poinsettia (Euphorbia pulcherrima)",
    "33": "Polka Dot Plant (Hypoestes phyllostachya)",
    "34": "Ponytail Palm (Beaucarnea recurvata)",
    "35": "Pothos (Ivy arum)",
    "36": "Prayer Plant (Maranta leuconeura)",
    "37": "Rattlesnake Plant (Calathea lancifolia)",
    "38": "Rubber Plant (Ficus elastica)",
    "39": "Sago Palm (Cycas revoluta)",
    "40": "Schefflera",
    "41": "Snake plant (Sanseviera)",
    "42": "Tradescantia",
    "43": "Tulip",
    "44": "Venus Flytrap",
    "45": "Yucca",
    "46": "ZZ Plant (Zamioculcas zamiifolia)"
}


# =========================================================
# LOAD MODELS
# =========================================================
def load_disease_model():
    global disease_model
    try:
        model_path = "my_keras_model.h5"
        if not os.path.exists(model_path):
            print(f"❌ Disease model not found: {model_path}")
            return False
        disease_model = load_model(model_path)
        print("✅ Disease model loaded!")
        return True
    except Exception as e:
        print("❌ Disease model load error:", e)
        print(traceback.format_exc())
        return False


def load_indoor_model():
    """
    Put your indoor plant model here:
      models/indoor_plant_model.h5   (example)
    """
    global indoor_model
    try:
        model_path = os.path.join("models", "indoor_plant_model.h5")
        if not os.path.exists(model_path):
            print(f"⚠️ Indoor model not found: {model_path}")
            return False
        indoor_model = load_model(model_path)
        print("✅ Indoor plant model loaded!")
        return True
    except Exception as e:
        print("❌ Indoor model load error:", e)
        print(traceback.format_exc())
        return False


# =========================================================
# HELPERS
# =========================================================
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def preprocess_keras_image(image_path: str, size=(224, 224)) -> np.ndarray:
    """
    For Keras models trained on images 224x224 normalized 0..1
    """
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Could not read image file")
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = cv2.resize(image, size)
    image = image.astype("float32") / 255.0
    image = np.expand_dims(image, axis=0)
    return image


# =========================================================
# DISEASE PREDICTION
# =========================================================
def predict_disease(image_path: str):
    try:
        if disease_model is None:
            return None, "Disease model not loaded"

        x = preprocess_keras_image(image_path, (224, 224))
        preds = disease_model.predict(x, verbose=0)[0]

        idx = int(np.argmax(preds))
        confidence = float(preds[idx])
        predicted_class = CLASS_NAMES[idx]

        treatment_info = TREATMENT_GUIDE.get(predicted_class, DEFAULT_TREATMENT)

        top_3_idx = np.argsort(preds)[-3:][::-1]
        top_3 = [
            {
                "disease": CLASS_NAMES[i],
                "confidence": float(preds[i]),
                "treatment_url": f"/treatment/{CLASS_NAMES[i].replace('___', '_')}"
            }
            for i in top_3_idx
        ]

        result = {
            "predicted_disease": predicted_class,
            "common_name": treatment_info.get("name", predicted_class),
            "confidence": confidence,
            "severity": treatment_info.get("severity", "unknown"),
            "treatment_guide": treatment_info,
            "treatment_url": f"/treatment/{predicted_class.replace('___', '_')}",
            "top_predictions": top_3
        }
        return result, None

    except Exception as e:
        return None, str(e)


# =========================================================
# INDOOR PLANT SPECIES PREDICTION
# =========================================================
def predict_indoor_plant(image_path: str):
    try:
        if indoor_model is None:
            return None, "Indoor plant model not loaded"

        x = preprocess_keras_image(image_path, (224, 224))
        preds = indoor_model.predict(x, verbose=0)[0]

        idx = int(np.argmax(preds))
        confidence = float(preds[idx])

        label = INDOOR_LABELS[str(idx)]
        guide = INDOOR_PLANT_GUIDE.get(label)

        result = {
            "predicted_plant": label,
            "confidence": confidence,
            "guide": guide  # can be None if label not in guide dict (but should match)
        }
        return result, None

    except Exception as e:
        return None, str(e)


# =========================================================
# CROP RECOMMENDATION MODEL
# =========================================================
crop_model = joblib.load("crop_recommender_xgb.pkl")
scaler = joblib.load("scaler.pkl")
label_encoder = joblib.load("label_encoder.pkl")


# =========================================================
# ROUTES (UI)
# =========================================================
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/menu")
def menu_page():
    return render_template("menu.html")


@app.route("/chatbot")
def chatbot_page():
    return render_template("chatbot.html")


# Indoor plant guide pages
@app.route("/indoor-plants")
def indoor_plants_page():
    # list all guides
    return render_template("indoor_plants.html", plants=INDOOR_PLANT_GUIDE)


@app.route("/indoor-plants/<plant_name>")
def indoor_plant_detail(plant_name):
    guide = INDOOR_PLANT_GUIDE.get(plant_name)
    if not guide:
        return render_template("error.html", error="Plant guide not found")
    return render_template("indoor_plant_detail.html", plant_name=plant_name, guide=guide)


# =========================================================
# CHATBOT API
# =========================================================
def detect_language(text):
    try:
        return langdetect.detect(text)
    except Exception:
        return "en"


def chat_with_gpt(message: str):
    if client is None:
        return "Chatbot is not configured. Please set GROQ_API_KEY in environment variables."

    user_lang = detect_language(message)

    if user_lang == "ar":
        system_prompt = (
            "أنت مساعد ذكاء اصطناعي متخصص فقط في الزراعة. "
            "إذا سأل المستخدم عن أي شيء غير زراعي، أجب: "
            "'أنا متخصص فقط في المواضيع الزراعية.'"
        )
    else:
        system_prompt = (
            "You are an AI assistant specialized ONLY in agriculture. "
            "If the user asks anything unrelated to agriculture, respond: "
            "'I am specialized only in agricultural topics.'"
        )

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    )
    return completion.choices[0].message.content


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    user_msg = data.get("message", "")
    reply = chat_with_gpt(user_msg)
    return jsonify({"reply": reply})


# =========================================================
# DISEASE DETECTION (UI + API)
# =========================================================
@app.route("/disease-detection", methods=["GET", "POST"])
def disease_detection():
    if request.method == "GET":
        return render_template("disease-detection.html")

    try:
        if "file" not in request.files:
            return render_template("disease-detection.html", error="No file uploaded")

        file = request.files["file"]
        if file.filename == "":
            return render_template("disease-detection.html", error="No file selected")
        if not allowed_file(file.filename):
            return render_template("disease-detection.html", error="Invalid file type")

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        result, error = predict_disease(filepath)
        if error:
            return render_template("disease-detection.html", error=error)

        input_data = {
            "Image File": filename,
            "Predicted Disease": result["predicted_disease"],
            "Common Name": result["common_name"],
            "Confidence": f"{result['confidence']*100:.2f}%"
        }

        return render_template("result.html", crop=result["predicted_disease"], input_data=input_data)

    except Exception as e:
        return render_template("disease-detection.html", error=str(e))


@app.route("/api/disease-predict", methods=["POST"])
def api_disease_predict():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type"}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        result, error = predict_disease(filepath)
        if error:
            return jsonify({"error": error}), 500

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/treatment/<disease_name>")
def treatment_guide(disease_name):
    formatted_name = disease_name.replace("_", "___").replace("-", "___")
    treatment = TREATMENT_GUIDE.get(formatted_name, DEFAULT_TREATMENT)
    return render_template(
        "treatment_guide.html",
        disease_name=formatted_name,
        treatment=treatment,
        current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


# =========================================================
# INDOOR PLANT IDENTIFICATION (UI + API)
# =========================================================
@app.route("/indoor-plant-detection", methods=["GET", "POST"])
def indoor_plant_detection():
    if request.method == "GET":
        return render_template("indoor-plant-detection.html")

    try:
        if "file" not in request.files:
            return render_template("indoor-plant-detection.html", error="No file uploaded")

        file = request.files["file"]
        if file.filename == "":
            return render_template("indoor-plant-detection.html", error="No file selected")
        if not allowed_file(file.filename):
            return render_template("indoor-plant-detection.html", error="Invalid file type")

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        result, error = predict_indoor_plant(filepath)
        if error:
            return render_template("indoor-plant-detection.html", error=error)

        # Show guide directly after prediction
        return render_template(
            "indoor_plant_result.html",
            image_file=filename,
            predicted_plant=result["predicted_plant"],
            confidence=f"{result['confidence']*100:.2f}%",
            guide=result["guide"]
        )

    except Exception as e:
        return render_template("indoor-plant-detection.html", error=str(e))


@app.route("/api/indoor-plant-predict", methods=["POST"])
def api_indoor_plant_predict():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type"}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        result, error = predict_indoor_plant(filepath)
        if error:
            return jsonify({"error": error}), 500

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================================================
# CROP RECOMMENDATION (UI + API)
# =========================================================
@app.route("/crop-recommendation")
def crop_recommend_page():
    return render_template("crop-recommendation.html")


@app.route("/all-guides")
def all_guides():
    return render_template("all_guides.html", crops=CROP_GUIDE.keys())


@app.route("/crop-predict", methods=["POST"])
def crop_predict():
    try:
        data = {
            "N": float(request.form["nitrogen"]),
            "P": float(request.form["phosphorus"]),
            "K": float(request.form["potassium"]),
            "temperature": float(request.form["temperature"]),
            "humidity": float(request.form["humidity"]),
            "ph": float(request.form["ph"]),
            "rainfall": float(request.form["rainfall"]),
        }

        df_input = pd.DataFrame([data])
        df_scaled = scaler.transform(df_input)

        pred_encoded = crop_model.predict(df_scaled)[0]
        predicted_crop = label_encoder.inverse_transform([pred_encoded])[0]

        return render_template("crop_result.html", crop=predicted_crop, input_data=df_input.iloc[0])

    except Exception as e:
        return render_template("error.html", error=str(e))


@app.route("/api/crop-predict", methods=["POST"])
def api_crop_predict():
    try:
        data = request.get_json(force=True)
        df_input = pd.DataFrame([data])
        df_scaled = scaler.transform(df_input)

        pred_encoded = crop_model.predict(df_scaled)[0]
        predicted_crop = label_encoder.inverse_transform([pred_encoded])[0]

        return jsonify({"recommended_crop": predicted_crop})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/guide/<crop_name>")
def crop_guide(crop_name):
    cname = crop_name.lower()
    if cname in CROP_GUIDE:
        return render_template("guide.html", crop_name=crop_name.title(), guide=CROP_GUIDE[cname])
    return render_template("error.html", error="No guide found for this crop")


# =========================================================
# HEALTH CHECK
# =========================================================
@app.route("/health")
def health_check():
    return jsonify({
        "status": "ok",
        "disease_model_loaded": disease_model is not None,
        "indoor_model_loaded": indoor_model is not None,
        "timestamp": datetime.datetime.now().isoformat(),
    })


# =========================================================
# ERROR HANDLERS
# =========================================================
@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", error="Page not found"), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template("error.html", error="Internal server error"), 500


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    print("🚀 Starting Unified Smart Agro App...")
    print("📁 Current directory:", os.getcwd())

    if load_disease_model():
        print("✅ Disease module ready.")
    else:
        print("⚠️ Disease model not loaded.")

    if load_indoor_model():
        print("✅ Indoor plant module ready.")
    else:
        print("⚠️ Indoor plant model not loaded. (Put file in models/indoor_plant_model.h5)")

    print("🌾 Crop recommendation model loaded.")
    print("🌐 App ready: http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
