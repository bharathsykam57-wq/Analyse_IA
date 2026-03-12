"""Multilingual support module for Analyse_IA using statistical language detection.

Provides language detection and translation services for a bilingual (French/English) system.
Designed for French enterprises requiring RGPD/CNIL compliance with support for
bilingual user inputs.

Core Functions:
- detect_language(): Statistical language detection using langdetect library (trained on real text)
- translate_to_french(): English-to-French translation via Ollama mistral-nemo API
- get_analysis_summary(): Bilingual analysis report generation (markdown formatted)
- get_error_message(): Localized error messages for user display

Architecture:
- Language detection: Uses langdetect for high-accuracy classification (handles mixed-language text)
- Translation: Ollama mistral-nemo LLM running on localhost:11434 (temperature=0.1 for consistency)
- Default language: French (fallback for detection failures and ambiguous text)
- Supported languages: French ('fr') and English ('en') only

Error Handling & Reliability:
- All external service calls (Ollama) include timeout (15s) and exception handling
- Graceful degradation: Returns original text if translation service unavailable
- Language detection failures default to French (\"French first\" policy)
- No external calls ever crash the system—all exceptions caught and logged

Dependencies:
- langdetect: Statistical language detection library
- requests: HTTP client for Ollama API communication
- logging: Standard library for operation tracking
"""
import logging
import requests
from langdetect import detect, LangDetectException

logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """Detect language of input text using statistical language detection.

    Uses the langdetect library (trained on real-world text corpora) to accurately identify
    whether input text is French or English. This approach is more robust than keyword matching,
    handling mixed-language content, technical terminology, and domain-specific vocabulary.

    Detection Flow:
    1. Validate input: empty/whitespace returns 'fr' immediately (no processing needed)
    2. Apply langdetect's statistical model: identifies language from character/word patterns
    3. Map result: 'en' → 'en', all other detected languages → 'fr' (French first policy)
    4. Catch LangDetectException: ambiguous or too-short text defaults to French
    5. Log detection: recorded for debugging, monitoring, and audit trails

    Default Behavior—\"French First\" Policy:
    - Empty/None input: Returns 'fr' (French) without processing
    - Ambiguous detection: Returns 'fr' (French) when langdetect cannot decide
    - Detection exception: Returns 'fr' (French) + warning log
    - Unknown languages: Treated as 'fr' (French) - ensures graceful degradation
    This policy supports Analyse_IA's target audience (French enterprises) and ensures
    the system always has a reasonable default for bilingual environments.

    Performance: ~10-50ms depending on text length (langdetect is highly optimized)

    Args:
        text (str): User input text to classify. Can be French or English.
                   Empty/None input returns 'fr' without processing.
                   Handles non-ASCII characters and special symbols.

    Returns:
        str: Language code - 'en' for English, 'fr' for French (default)
             Always returns a valid code (never None or unknown values)

    Logs:
        - INFO: Successful detection with cleaned language code and raw langdetect result
        - WARNING: LangDetectException caught (ambiguous/failed), defaulting to French

    Example:
        >>> detect_language("Analysez ce fichier CSV de ventes")
        'fr'
        >>> detect_language("Analyze this sales dataset")
        'en'
        >>> detect_language("")
        'fr'  # Empty text defaults to French
        >>> detect_language("   ")
        'fr'  # Whitespace defaults to French
    """
    # Handle empty/None input: default to French (\"French first\" policy)
    # Prevents langdetect from processing empty strings
    if not text or not text.strip():
        return 'fr'

    try:
        # Apply langdetect statistical model to identify language
        # Returns ISO 639-1 language code (e.g., 'en', 'fr', 'es', 'de', etc.)
        detected = detect(text)
        
        # Map to supported languages: keep 'en' as-is, default all others to 'fr'
        # This ensures unknown/unsupported languages gracefully fall back to French
        language = 'en' if detected == 'en' else 'fr'
        
        # Log detection result for debugging and monitoring
        # Include both our code ('en'/'fr') and langdetect's original code for troubleshooting
        logger.info(f"Language detected: {language} (langdetect={detected})")
        return language

    except LangDetectException as e:
        # Catch ambiguous detection (text too short, mixed languages, or random characters)
        # Gracefully default to French per system policy
        logger.warning(f"Language detection failed, defaulting to French: {e}")
        return 'fr'


def translate_to_french(text: str) -> str:
    """Translate English text to French using Ollama's mistral-nemo LLM.

    Ensures consistent French representation for English queries before RAG pipeline processing.
    By translating English questions to French, the system retrieves equivalent documents
    from the vector database regardless of original query language.

    Translation Pipeline:
    1. Validate text (non-empty, strip whitespace)
    2. Send POST request to Ollama API at localhost:11434/api/chat
    3. Configure mistral-nemo with 15-second timeout and low temperature (0.1)
    4. Set model to output ONLY translation (no explanations or alternatives)
    5. Extract and return translated content on HTTP 200 success
    6. On any failure (network, timeout, API error), return original English text unchanged

    Error Handling Strategy:
    - Network errors (connection refused, connection timeout): Log warning, return original
    - Invalid response (non-200 status, missing content): Log warning, return original text
    - Invalid JSON parsing: Caught by broad exception handler, returns original text
    - System remains operational and functional even if Ollama service is unavailable
    - Never raises exceptions—always returns displayable text

    Temperature Configuration:
    - 0.1 (very low randomness): Ensures deterministic, consistent translations
    - Focus on likely token sequences: Favors accuracy over creative/paraphrased output
    - Suitable for technical/compliance domain translations: RGPD, CSV columns, dataset names

    Prerequisites:
    - Ollama running locally on port 11434: ollama serve
    - mistral-nemo model pulled: ollama pull mistral-nemo
    - Network connectivity: API calls to localhost (should be instant)

    Performance: 2-10 seconds typical (dominated by Ollama LLM inference)
    Timeout: 15 seconds (prevents indefinite blocking of agent)

    Args:
        text (str): English text to translate
                   Example: \"Analyze anomalies in sales data\"
                   Can be empty string (returns empty string after processing)

    Returns:
        str: French translation if successful
             Original English text if translation service unavailable
             Ensures system always returns usable text (never None or error state)

    Logs:
        - INFO: Successful translation with 50-char excerpt of source and target
        - WARNING: Translation failure (network, timeout, API error) with full exception details

    Example:
        >>> translate_to_french(\"What anomalies did you find?\")
        \"Quelles anomalies as-tu trouvées ?\"
        >>> translate_to_french(\"Analyze this\")  # If Ollama down
        \"Analyze this\"  # Returns original on failure
    """
    try:
        # POST to Ollama API running on localhost:11434
        # Endpoint: /api/chat - chat completion interface compatible with OpenAI format
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                # Model: mistral-nemo (7.3B parameters, multilingual, fast)
                "model": "mistral-nemo",
                # Message format: standard OpenAI chat API structure (role + content)
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Translate this to French. "
                            f"Return ONLY the translation, nothing else:\n{text}"
                        )
                    }
                ],
                # stream=False: Wait for complete response (not streaming chunks)
                "stream": False,
                # Generation options: temperature=0.1 for deterministic output
                "options": {"temperature": 0.1}
            },
            timeout=15  # 15-second timeout (prevent indefinite blocking of agent)
        )

        # Verify HTTP success (200 OK status)
        if response.status_code == 200:
            # Extract translated text from Ollama response format
            # Response structure: {\"message\": {\"content\": \"translated text\"}}
            translated = response.json()["message"]["content"].strip()
            # Log with 50-char excerpt for debugging without cluttering logs
            logger.info(f"Query translated: '{text[:50]}' → '{translated[:50]}'")
            return translated

    except Exception as e:
        # Catch all exceptions: network errors, timeouts, JSON parse errors, etc.
        # System gracefully degrades by returning original English text
        logger.warning(f"Translation failed, using original: {e}")

    # Fallback: return original text if translation failed or service unavailable
    return text


def get_analysis_summary(
    filename: str,
    rows: int,
    cols: int,
    insights: list,
    anomaly_count: int,
    best_model: str = None,
    r2: float = None,
    language: str = 'fr'
) -> str:
    """Generate bilingual analysis report summarizing Phase 1 pipeline results.

    Formats complete analysis outputs (EDA statistics, AutoML model info, anomaly detection)
    into a user-friendly markdown report. Dynamically generates French or English narratives
    based on detected language preference.

    Report Structure (consistent across both languages):
    1. Header: Dataset identification with dimensions (rows × columns)
    2. Insights: Top 3 findings from EDA engine (statistical patterns, correlations, outliers)
    3. Model: Best-performing AutoML model name and R² coefficient (if provided)
    4. Anomalies: Count of detected anomalies with positive/negative interpretation

    Markdown Formatting:
    - Section headers: Bold text (**Header Name:**) for visual hierarchy
    - Insights list: Bullet points (- item) for readability
    - Metrics: Formatted numbers (R² as percentage: 87.34%)
    - Spacing: Clean line breaks (\n\n) between sections for visual separation

    Language Terminology:
    - French: \"lignes\" (rows), \"colonnes\" (columns), \"modèle\" (model), \"anomalies\"
    - English: \"rows\", \"columns\", \"model\", \"anomalies\"
    - Both: R² coefficient, dataset filename, insight text (as provided)

    Args:
        filename (str): CSV filename analyzed (e.g., 'sales_data.csv')
                       Displayed as-is in report header without path
        rows (int): Number of rows in dataset (≥0)
        cols (int): Number of columns in dataset (≥0)
        insights (list[str]): List of human-readable insight strings from EDA engine
                             Example: ['High correlation (0.89) between price and area',
                                      'Right-skewed distribution in annual revenue']
                             Behavior: Only first 3 insights displayed (excess ignored)
                             Empty list: Insights section omitted from report
        anomaly_count (int): Number of detected anomalies (≥0)
                            0 = \"No anomalies detected\" message (positive language)
                            >0 = \"N suspicious rows found\" message (alerts user)
        best_model (str, optional): Name of best AutoML model
                                   Example: 'XGBRegressor', 'RandomForestClassifier',
                                           'Ridge', 'GradientBoostingRegressor'
                                   Default: None (model performance section omitted)
                                   Note: Only displayed if both best_model AND r2 provided
        r2 (float, optional): R² score for best model (typically 0.0-1.0, can be negative)
                             Formatted as percentage with 2 decimal places (e.g., 0.87 → \"87.00%\")
                             Default: None (model performance section omitted if missing)
                             Note: Only displayed if both best_model AND r2 provided
        language (str, optional): User's language preference for report
                                 'en' = English report
                                 'fr' = French report (default)
                                 Default: 'fr' (French - Analyse_IA default)

    Returns:
        str: Formatted markdown report in specified language
             Contains headers, insights, and anomaly information
             Optimized for display in chat interfaces and markdown renderers
             Never returns None (always returns valid string)

    Example:
        >>> report = get_analysis_summary(
        ...     filename='sales.csv',
        ...     rows=10000,
        ...     cols=12,
        ...     insights=['Median price €250k', 'Outliers in 3%', 'Strong location correlation'],
        ...     anomaly_count=45,
        ...     best_model='XGBRegressor',
        ...     r2=0.8734,
        ...     language='fr'
        ... )
        >>> print(report)
        # Output (French):
        # J'ai analysé le fichier **sales.csv** contenant 10000 lignes et 12 colonnes.
        #
        # **Insights statistiques :**
        # - Median price €250k
        # - Outliers in 3%
        # - Strong location correlation
        #
        # **Meilleur modèle :** XGBRegressor (R² = 87.34%)
        #
        # **Anomalies détectées :** 45 lignes suspectes trouvées.
    """

    # Generate report in English if language='en', otherwise French (default)
    if language == 'en':
        # English report header: dataset file name, dimensions
        summary = f"I analysed **{filename}** containing {rows} rows and {cols} columns.\n\n"

        # Add insights section: display first 3 findings from EDA engine
        if insights:
            summary += "**Statistical insights:**\n"
            for insight in insights[:3]:
                # Each insight as bullet point
                summary += f"- {insight}\n"
            summary += "\n"  # Blank line for visual spacing

        # Add model performance: best model name + R² coefficient
        # Only included if best_model AND r2 are both provided
        if best_model and r2:
            # Format R² as percentage with 2 decimal places (e.g., 87.34%)
            summary += f"**Best model:** {best_model} (R² = {r2:.2%})\n\n"

        # Add anomalies section: count + interpretation
        if anomaly_count > 0:
            # Plural message when anomalies found
            summary += f"**Anomalies detected:** {anomaly_count} suspicious rows found.\n"
        else:
            # Positive message when no anomalies detected
            summary += "**Anomalies:** No anomalies detected.\n"

    else:
        # French report header: dataset file name, dimensions (French terminology)
        summary = f"J'ai analysé le fichier **{filename}** contenant {rows} lignes et {cols} colonnes.\n\n"

        # Add insights section: display first 3 findings from EDA engine
        if insights:
            summary += "**Insights statistiques :**\n"
            for insight in insights[:3]:
                # Each insight as bullet point
                summary += f"- {insight}\n"
            summary += "\n"  # Blank line for visual spacing

        # Add model performance: best model name + R² coefficient
        # Only included if best_model AND r2 are both provided
        if best_model and r2:
            # Format R² as percentage with 2 decimal places (e.g., 87.34%)
            summary += f"**Meilleur modèle :** {best_model} (R² = {r2:.2%})\n\n"

        # Add anomalies section: count + interpretation
        if anomaly_count > 0:
            # Plural message when anomalies found (French: lignes suspectes)
            summary += f"**Anomalies détectées :** {anomaly_count} lignes suspectes trouvées.\n"
        else:
            # Positive message when no anomalies detected (French)
            summary += "**Anomalies :** Aucune anomalie détectée.\n"

    # Return completed markdown report
    return summary


def get_error_message(error_type: str, language: str = 'fr') -> str:
    """Retrieve localized error message for user display.

    Centralized error messaging system providing consistent French and English error
    messages for all system components. Maps internal error codes to user-friendly
    explanations suitable for direct display in UI or chat interfaces.

    Error Message Categories:
    1. Input Validation (empty_question): User provided no question to process
    2. Missing Resources (no_dataset, no_documents): Required files not available
    3. Pipeline Failures (analysis_failed, rag_failed): Processing errors during execution

    Supported Error Types:
    - 'empty_question': User submitted empty or whitespace-only query
                        Suggests: Provide a meaningful question to the system
    - 'no_dataset': Required CSV file not provided for analysis phase
                    Suggests: Upload/specify a CSV file to analyze
    - 'no_documents': Required PDF documents not indexed for RAG phase
                      Suggests: Index a PDF document first before searching
    - 'analysis_failed': Data processing error in analysis pipeline
                        Suggests: Check file format and content validity
    - 'rag_failed': Document search or LLM generation error in RAG phase
                    Suggests: Retry search or verify document content

    Fallback Behavior:
    - Unknown error_type: Returns generic 'Erreur' (French) or 'Error' (English)
    - Missing language code: Defaults to French ('fr')
    - None/invalid inputs: Returns safe generic message (never crashes)

    Localization Strategy:
    - French ('fr'): Formal, professional tone suitable for enterprises and compliance
    - English ('en'): Clear, actionable messages for international/technical users

    Args:
        error_type (str): Internal error code identifying the error type
                         Must be key in messages dict (empty_question, no_dataset, etc.)
                         Unknown codes return generic fallback message
        language (str, optional): User's language for error message display
                                 'fr' = French error message
                                 'en' = English error message
                                 Default: 'fr' (French - Analyse_IA standard)

    Returns:
        str: User-friendly error message in specified language
             Never returns None - always returns displayable text
             Suitable for direct display in user interface or chat
             Safe to use even if error_type is unknown

    Example:
        >>> get_error_message('no_dataset', 'en')
        'To analyse data, please provide the path to a CSV file.'
        >>> get_error_message('no_dataset', 'fr')
        'Pour analyser des données, veuillez fournir le chemin vers un fichier CSV.'
        >>> get_error_message('unknown_error', 'en')  # Unknown error type
        'Error'  # Fallback to generic
        >>> get_error_message('analysis_failed', 'fr')
        \"L'analyse a échoué. Veuillez vérifier votre fichier.\"
        >>> get_error_message('rag_failed', 'en')
        'Document search failed.'
    """

    # Bilingual error message catalog
    # Structure: error_type → {language_code → user_friendly_message}
    messages = {
        # Input validation: user provided no question
        'empty_question': {
            'fr': 'Question vide',
            'en': 'Empty question'
        },
        # Analysis phase: CSV file not provided
        # Message: prompt user to provide dataset path
        'no_dataset': {
            'fr': 'Pour analyser des données, veuillez fournir le chemin vers un fichier CSV.',
            'en': 'To analyse data, please provide the path to a CSV file.'
        },
        # RAG phase: PDF documents not indexed
        # Message: prompt user to index a PDF first
        'no_documents': {
            'fr': "Aucun document indexé. Veuillez d'abord indexer un PDF.",
            'en': 'No documents indexed. Please index a PDF first.'
        },
        # Analysis pipeline: data processing failed
        # Message: prompt user to check file format/content validity
        'analysis_failed': {
            'fr': "L'analyse a échoué. Veuillez vérifier votre fichier.",
            'en': 'Analysis failed. Please check your file.'
        },
        # RAG pipeline: document search or LLM generation failed
        # Message: inform user of search/generation failure
        'rag_failed': {
            'fr': 'La recherche documentaire a échoué.',
            'en': 'Document search failed.'
        }
    }

    # Retrieve localized message: first by error_type, then by language
    # Fallback to 'Erreur' (French) if error_type or language not found
    # messages.get(error_type, {}) returns empty dict if error_type unknown
    # Then .get(language, 'Erreur') returns generic error or specific message
    return messages.get(error_type, {}).get(language, 'Erreur')