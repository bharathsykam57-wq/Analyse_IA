import os
import logging
from backend.utils.language import detect_language, translate_to_french, get_analysis_summary

# Setup basic logging to see the "Language detected" info logs
logging.basicConfig(level=logging.INFO)

def run_test():
    print("--- 🌍 Starting Language Module Test ---")

    # 1. Test Detection
    fr_text = "Est-ce que tu peux analyser ce fichier de ventes ?"
    en_text = "Can you analyze this sales file?"
    
    print(f"Detecting FR: {detect_language(fr_text)}") # Should be 'fr'
    print(f"Detecting EN: {detect_language(en_text)}") # Should be 'en'

    # 2. Test Translation (Requires Ollama/Mistral-Nemo)
    # If this returns the original text, your OLLAMA_URL is likely wrong in Railway
    print("\n--- 🤖 Testing Translation (Ollama) ---")
    sample_q = "What are the main trends in this data?"
    translated = translate_to_french(sample_q)
    print(f"Original: {sample_q}")
    print(f"Translated: {translated}")

    # 3. Test Summary Generation
    print("\n--- 📊 Testing Summary Generation ---")
    report = get_analysis_summary(
        filename="production_data.csv",
        rows=1500,
        cols=10,
        insights=["High growth in Q3", "User retention up 20%"],
        anomaly_count=5,
        best_model="XGBoost",
        r2=0.9245,
        language='en'
    )
    print(report)

if __name__ == "__main__":
    run_test()