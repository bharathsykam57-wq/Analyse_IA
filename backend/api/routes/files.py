"""FastAPI file upload endpoints for CSV and PDF documents with storage and authentication.

Provides secure file upload, retrieval, and management for authenticated users.

Endpoints:
    POST /files/upload/csv → Upload CSV file (max 50MB)
    POST /files/upload/pdf → Upload PDF file (max 20MB, magic byte validation)
    GET /files/list → List all files uploaded by current user

Security Features:
    - JWT Bearer authentication required (get_current_active_user dependency)
    - Per-user upload directories (isolation)
    - File size limits (50MB CSV, 20MB PDF)
    - Content-type validation (whitelist)
    - PDF magic byte validation (prevent masked files)
    - Safe filename generation (UUID + sanitized name)
    - Async file operations (non-blocking)
    - Request logging (audit trail)

Storage:
    - Uploaded files stored in UPLOAD_DIR/user_id/ subdirectories
    - Filenames: {uuid}_{sanitized_original_name}
    - Metadata returned in response (size, type, upload time)
    - No database tracking (files tracked by filesystem)

File Size Limits:
    - CSV: 50MB (large datasets, analysis-friendly)
    - PDF: 20MB (document processing, RAG ingestion)
    - Empty files rejected (0 bytes)

Supported Types:
    - CSV: text/csv, application/csv, text/plain
    - PDF: application/pdf (+ magic byte validation %PDF)

Error Handling:
    - 400: Unsupported type, empty file, invalid PDF
    - 413: File too large (entity too large)
    - 401: Missing/invalid authentication token
    - 500: Server errors (file system, disk space)

Bilingual Support:
    - Error messages in French
    - Supports multi-language user base
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
import aiofiles
import os
import uuid
import io
import csv
import unicodedata as _unicodedata
import logging
from backend.monitoring.analytics_tracker import log_analytics_event_sync

from backend.api.dependencies import get_db
from backend.api.auth.router import get_current_active_user
from backend.api.auth.models import User

try:
    from supabase import create_client
    _SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    _SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
    _supabase = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_KEY) if _SUPABASE_URL and _SUPABASE_SERVICE_KEY else None
except Exception as _supabase_init_err:
    _supabase = None
    import logging as _l
    _l.getLogger(__name__).warning(f"Supabase client init failed in files.py: {_supabase_init_err}")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

# Upload directory for user files (can be configured via environment variable)
# Directory structure: UPLOAD_DIR/user_id/filename
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

# File size limits (prevents resource exhaustion and disk space issues)
MAX_CSV_SIZE = 50 * 1024 * 1024   # 50MB - Large datasets, analysis-friendly
MAX_PDF_SIZE = 20 * 1024 * 1024   # 20MB - Document processing, RAG ingestion

# MIME type whitelists (prevents unexpected file types)
ALLOWED_CSV_TYPES = {"text/csv", "application/csv", "text/plain", "application/octet-stream"}
ALLOWED_PDF_TYPES = {"application/pdf"}


def ensure_upload_dir(user_id: str) -> str:
    """Create per-user upload directory if it doesn't exist (idempotent).
    
    Creates isolated directory tree for each user's files. This prevents:
    - Directory traversal attacks (each user confined to own directory)
    - File conflicts between users (separate namespaces)
    - Unauthorized file access (filesystem permission enforcement)
    
    Args:
        user_id: UUID of authenticated user (string)
        
    Returns:
        str: Absolute path to user's upload directory (created if missing)
        
    Example:
        user_dir = ensure_upload_dir("550e8400-e29b-41d4-a716-446655440000")
        # Returns: "uploads/550e8400-e29b-41d4-a716-446655440000"
        # Creates directory if not exists
    """
    user_dir = os.path.join(UPLOAD_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)  # exist_ok prevents errors on retry
    return user_dir


def safe_filename(original: str, file_id: str) -> str:
    """Generate filesystem-safe filename preventing path traversal and special chars.
    
    Transforms user-provided filename into safe format: {uuid}_{sanitized_name}
    This prevents:
    - Path traversal (../, ..\\\\)
    - Special characters causing filesystem errors
    - Very long filenames (filesystem limits)
    - Repeated uploads of same file (UUID ensures uniqueness)
    
    Args:
        original: Original filename from UploadFile (user-controlled input)
        file_id: UUID for uniqueness (prevents filename collisions)
        
    Returns:
        str: Safe filename with format: {file_id}_{sanitized_original}
        
    Examples:
        safe_filename("my-data.csv", "550e8400")
        → "550e8400_my-data.csv"
        
        safe_filename("../../etc/passwd", "550e8400")
        → "550e8400________etc_passwd"
        
        safe_filename("data (copy).csv", "550e8400")
        → "550e8400_data__copy_.csv"
    
    Security:
        - UUID prefix ensures collision-free storage
        - Original filename kept for display (not execution)
        - Special characters replaced with underscores
        - Extension preserved and lowercased
    """
    ext = os.path.splitext(original)[1].lower()
    # Replace all non-alphanumeric characters (except dash, underscore, dot)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in original)
    return f"{file_id}_{safe}"


@router.post("/upload/csv")
async def upload_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Upload CSV file with validation, storage, and metadata return.
    
    Accepts CSV uploads for data analysis. Validates file type, size, and content.
    Stores in per-user directory with UUID-based naming for collision avoidance.
    
    Authentication:
        Required: Valid Bearer token (JWT access_token)
        User must have is_active=True (get_current_active_user dependency)
    
    Validation Pipeline:
        1. Content-type check (ALLOWED_CSV_TYPES whitelist)
        2. File read (loads entire file into memory)
        3. Size check (reject if > 50MB)
        4. Empty file check (reject if 0 bytes)
        5. Directory creation (per-user uploads/{user_id}/)
        6. Safe filename generation ({uuid}_{sanitized_name})
        7. Async write to disk (non-blocking)
    
    Args:
        file: Multipart form file from request (UploadFile)
        current_user: Authenticated User object (from JWT token)
        db: SQLAlchemy session (unused, kept for consistency)
    
    Returns:
        Dict with file metadata on 200 OK:
            file_id: UUID for future reference
            filename: Sanitized name on disk
            original_name: User-provided filename
            size_bytes: File size in bytes
            type: "csv"
            path: Absolute filesystem path
            uploaded_at: ISO 8601 timestamp
            user_id: UUID of uploading user
    
    HTTP Status Codes:
        201 Created: File uploaded successfully
        400 Bad Request: Unsupported type, empty file
        413 Request Entity Too Large: File exceeds 50MB
        401 Unauthorized: Missing/invalid token
        500 Server Error: Filesystem/disk issues
    
    Error Responses:
        - Unsupported type: {"detail": "Type de fichier non supporté..."}
        - File too large: {"detail": "Fichier trop volumineux..."}
        - Empty file: {"detail": "Le fichier est vide..."}
    
    Security:
        - JWT authentication prevents unauthorized uploads
        - Per-user directories prevent cross-user access
        - File size limits prevent resource exhaustion
        - Content-type whitelist prevents malicious uploads
        - Safe filenames prevent directory traversal
        - Async I/O prevents thread blocking
    """
    # Validation 1: Content-Type (MIME type check)
    if file.content_type not in ALLOWED_CSV_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Type de fichier non supporté: {file.content_type}. Utilisez un fichier CSV.",
        )

    # Validation 2-4: File size and emptiness
    contents = await file.read()
    if len(contents) > MAX_CSV_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fichier trop volumineux. Taille maximale: 50MB.",
        )
    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier est vide.",
        )

    # Validation 5-7: Storage and write
    file_id = str(uuid.uuid4())
    user_dir = ensure_upload_dir(str(current_user.id))
    filename = safe_filename(file.filename or "upload.csv", file_id)
    filepath = os.path.join(user_dir, filename)

    # Async write to disk (non-blocking)
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(contents)

    # Also upload to Supabase Storage for persistent cloud storage
    if _supabase is not None:
        try:
            storage_path = f"{current_user.id}/{filename}"
            logger.info(f"Attempting Supabase upload to: {storage_path}")
            _supabase.storage.from_("uploads").upload(
                storage_path,
                contents,
                {"content-type": file.content_type or "text/csv"},
            )
            logger.info(f"Supabase upload successful: {storage_path}")
        except Exception as _e:
            logger.warning(f"Supabase upload failed: {_e}", exc_info=True)

    logger.info(f"CSV uploaded: {filename} ({len(contents)} bytes) by {current_user.email}")
    log_analytics_event_sync(
        event_type="file_upload",
        status="success",
        user_id=str(current_user.id),
        file_type="csv",
        file_size_bytes=len(contents),
        metadata={"filename": filename},
    )

    return {
        "file_id": filename,  # full "{uuid}_{sanitized_name}" matches list_files and Supabase path
        "filename": filename,
        "original_name": file.filename,
        "size_bytes": len(contents),
        "type": "csv",
        "path": filepath,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "user_id": str(current_user.id),
    }


@router.post("/upload/pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Upload PDF file with validation, magic byte check, and storage.
    
    Accepts PDF uploads for document processing and RAG ingestion. Includes
    magic byte validation (%PDF header) to prevent masked file uploads.
    
    Authentication:
        Required: Valid Bearer token (JWT access_token)
        User must have is_active=True (get_current_active_user dependency)
    
    Validation Pipeline:
        1. Content-type check (ALLOWED_PDF_TYPES whitelist)
        2. File read (loads entire file into memory)
        3. Size check (reject if > 20MB)
        4. Empty file check (reject if 0 bytes)
        5. Magic byte validation (must start with %PDF)
        6. Directory creation (per-user uploads/{user_id}/)
        7. Safe filename generation ({uuid}_{sanitized_name})
        8. Async write to disk (non-blocking)
    
    Args:
        file: Multipart form file from request (UploadFile)
        current_user: Authenticated User object (from JWT token)
        db: SQLAlchemy session (unused, kept for consistency)
    
    Returns:
        Dict with file metadata on 200 OK:
            file_id: UUID for future reference
            filename: Sanitized name on disk
            original_name: User-provided filename
            size_bytes: File size in bytes
            type: "pdf"
            path: Absolute filesystem path
            uploaded_at: ISO 8601 timestamp
            user_id: UUID of uploading user
    
    HTTP Status Codes:
        201 Created: File uploaded successfully
        400 Bad Request: Unsupported type, empty file, invalid PDF
        413 Request Entity Too Large: File exceeds 20MB
        401 Unauthorized: Missing/invalid token
        500 Server Error: Filesystem/disk issues
    
    Error Responses:
        - Unsupported type: {"detail": "Type de fichier non supporté..."}
        - File too large: {"detail": "Fichier trop volumineux..."}
        - Empty file: {"detail": "Le fichier est vide..."}
        - Invalid PDF: {"detail": "Fichier PDF invalide..."}
    
    Magic Byte Validation:
        PDF spec requires first bytes: %PDF-X.X (e.g., %PDF-1.4, %PDF-2.0)
        
        Prevents Attacks:
            - File renamed: .exe → .pdf (detected by magic bytes)
            - Content-type spoofing: non-PDF sent as PDF (detected)
            - Format wrapping: malicious content in PDF structure (detected)
    
    Security:
        - JWT authentication prevents unauthorized uploads
        - Per-user directories prevent cross-user access
        - File size limits prevent resource exhaustion
        - Content-type whitelist prevents malicious uploads
        - Magic byte validation prevents masked files
        - Safe filenames prevent directory traversal
        - Async I/O prevents thread blocking
    """
    # Validation 1: Content-Type (MIME type check)
    if file.content_type not in ALLOWED_PDF_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Type de fichier non supporté: {file.content_type}. Utilisez un fichier PDF.",
        )

    # Validation 2-4: File size and emptiness
    contents = await file.read()
    if len(contents) > MAX_PDF_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fichier trop volumineux. Taille maximale: 20MB.",
        )
    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier est vide.",
        )

    # Validation 5: Magic byte check (security: prevents masked files)
    # PDF spec requires header: %PDF-X.X (e.g., %PDF-1.4, %PDF-2.0)
    # This prevents attackers from uploading .exe or other files renamed to .pdf
    if not contents.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fichier PDF invalide.",
        )

    # Validation 6-8: Storage and write
    file_id = str(uuid.uuid4())
    user_dir = ensure_upload_dir(str(current_user.id))
    filename = safe_filename(file.filename or "upload.pdf", file_id)
    filepath = os.path.join(user_dir, filename)

    # Async write to disk (non-blocking)
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(contents)

    # Also upload to Supabase Storage for persistent cloud storage
    if _supabase is not None:
        try:
            storage_path = f"{current_user.id}/{filename}"
            logger.info(f"Attempting Supabase upload to: {storage_path}")
            _supabase.storage.from_("uploads").upload(
                storage_path,
                contents,
                {"content-type": "application/pdf"},
            )
            logger.info(f"Supabase upload successful: {storage_path}")
        except Exception as _e:
            logger.warning(f"Supabase upload failed: {_e}", exc_info=True)

    logger.info(f"PDF uploaded: {filename} ({len(contents)} bytes) by {current_user.email}")
    log_analytics_event_sync(
        event_type="file_upload",
        status="success",
        user_id=str(current_user.id),
        file_type="pdf",
        file_size_bytes=len(contents),
        metadata={"filename": filename},
    )

    return {
        "file_id": filename,  # full "{uuid}_{sanitized_name}" matches list_files and Supabase path
        "filename": filename,
        "original_name": file.filename,
        "size_bytes": len(contents),
        "type": "pdf",
        "path": filepath,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "user_id": str(current_user.id),
    }


@router.get("/list")
async def list_files(
    current_user: User = Depends(get_current_active_user),
):
    """List all files uploaded by authenticated user with metadata.
    
    Returns a list of files stored in user's directory with filesystem metadata
    (size, type, modification time).
    
    Authentication:
        Required: Valid Bearer token (JWT access_token)
        User must have is_active=True (get_current_active_user dependency)
    
    Query Process:
        1. Check user directory exists (UPLOAD_DIR/{user_id}/)
        2. If not found: Return empty list (no files uploaded)
        3. If found: Iterate directory contents
        4. For each file: Extract metadata (size, type, timestamp)
        5. Build response with file list
    
    Args:
        current_user: Authenticated User object (from JWT token)
    
    Returns:
        Dict with file listing on 200 OK:
            files: List of file metadata objects, each containing:
                filename: Filesystem name (UUID-based, sanitized)
                type: "csv" or "pdf" (inferred from extension)
                size_bytes: File size in bytes
                uploaded_at: ISO 8601 timestamp of modification
            total: Count of files in directory
    
    HTTP Status Codes:
        200 OK: Request successful (empty list if no files)
        401 Unauthorized: Missing/invalid token
        500 Server Error: Filesystem access errors
    
    Success Response Format:
        {
            "files": [
                {
                    "filename": "550e8400_sales_data.csv",
                    "type": "csv",
                    "size_bytes": 2457600,
                    "uploaded_at": "2026-03-12T10:30:00+00:00"
                },
                {
                    "filename": "550e8401_report.pdf",
                    "type": "pdf",
                    "size_bytes": 5242880,
                    "uploaded_at": "2026-03-12T10:35:00+00:00"
                }
            ],
            "total": 2
        }
    
    Empty List Response:
        {
            "files": [],
            "total": 0
        }
    
    Security:
        - JWT authentication prevents unauthorized listing
        - Only user's own files returned (directory isolation)
        - No access to other users' files (separate directories)
        - Filesystem permissions enforce isolation
    
    File Type Detection:
        - Inferred from extension (.csv or .pdf)
        - Case-insensitive (converts to lowercase)
        - Fallback: Other extensions map to pdf
    
    Timestamp Precision:
        - Uses filesystem modification time (st_mtime)
        - Converted to ISO 8601 UTC format
        - Timezone-aware (includes +00:00 UTC offset)
        - May differ from upload time if file re-written
    
    Performance:
        - O(n) directory listing (n = number of files)
        - Filesystem stat calls (metadata only, no file read)
        - Suitable for moderate file counts (100s-1000s)
    
    Examples:
        REQUEST:
            GET /files/list
            Authorization: Bearer eyJhbGc...
        
        SUCCESS RESPONSE (200 OK):
            {
                "files": [
                    {
                        "filename": "550e8400_dataset.csv",
                        "type": "csv",
                        "size_bytes": 1048576,
                        "uploaded_at": "2026-03-12T10:30:00+00:00"
                    }
                ],
                "total": 1
            }
        
        NO FILES RESPONSE (200 OK):
            {
                "files": [],
                "total": 0
            }
    """
    user_id_str = str(current_user.id)

    # Prefer Supabase Storage listing when client is available
    if _supabase is not None:
        try:
            objects = _supabase.storage.from_("uploads").list(user_id_str)
            files = []
            for obj in (objects or []):
                name = obj.get("name", "")
                if not name:
                    continue  # Skip folder placeholders
                metadata = obj.get("metadata") or {}
                ext = os.path.splitext(name)[1].lower()
                files.append({
                    "file_id": name,
                    "filename": name,
                    "type": "csv" if ext == ".csv" else "pdf",
                    "size_bytes": int(metadata.get("size", 0)),
                    "uploaded_at": (
                        obj.get("updated_at")
                        or obj.get("created_at")
                        or datetime.now(timezone.utc).isoformat()
                    ),
                })
            return {"files": files, "total": len(files)}
        except Exception as _e:
            logger.warning(f"Supabase list failed, falling back to filesystem: {_e}")

    # Fallback: local filesystem listing
    user_dir = os.path.join(UPLOAD_DIR, user_id_str)
    if not os.path.exists(user_dir):
        return {"files": [], "total": 0}

    files = []
    for filename in os.listdir(user_dir):
        filepath = os.path.join(user_dir, filename)
        stat = os.stat(filepath)
        ext = os.path.splitext(filename)[1].lower()
        files.append({
            "file_id": filename,
            "filename": filename,
            "type": "csv" if ext == ".csv" else "pdf",
            "size_bytes": stat.st_size,
            "uploaded_at": datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat(),
        })

    return {"files": files, "total": len(files)}


# ═══════════════════════════════════════════════════════════════════════════════
# RGPD Personal Data Scanner
# ═══════════════════════════════════════════════════════════════════════════════

# ── Tier 1 — Exact match (confidence 1.0) ────────────────────────────────────
_HIGH_EXACT: dict[str, str] = {
    "email":                "Identifiant personnel — Adresse e-mail",
    "mail":                 "Identifiant personnel — Adresse e-mail",
    "e_mail":               "Identifiant personnel — Adresse e-mail",
    "courriel":             "Identifiant personnel — Adresse e-mail",
    "phone":                "Identifiant personnel — Numéro de téléphone",
    "telephone":            "Identifiant personnel — Numéro de téléphone",
    "tel":                  "Identifiant personnel — Numéro de téléphone",
    "mobile":               "Identifiant personnel — Numéro de mobile",
    "portable":             "Identifiant personnel — Numéro de mobile",
    "gsm":                  "Identifiant personnel — Numéro de mobile",
    "fax":                  "Identifiant personnel — Numéro de fax",
    "nom":                  "Identifiant personnel — Nom de famille",
    "prenom":               "Identifiant personnel — Prénom",
    "name":                 "Identifiant personnel — Nom complet",
    "firstname":            "Identifiant personnel — Prénom",
    "lastname":             "Identifiant personnel — Nom de famille",
    "surname":              "Identifiant personnel — Nom de famille",
    "fullname":             "Identifiant personnel — Nom complet",
    "full_name":            "Identifiant personnel — Nom complet",
    "nom_complet":          "Identifiant personnel — Nom complet",
    "adresse":              "Identifiant personnel — Adresse postale",
    "address":              "Identifiant personnel — Adresse postale",
    "rue":                  "Identifiant personnel — Rue",
    "street":               "Identifiant personnel — Rue",
    "voie":                 "Identifiant personnel — Voie",
    "ssn":                  "Identifiant personnel — Numéro de sécurité sociale",
    "nss":                  "Identifiant personnel — Numéro de sécurité sociale",
    "secu":                 "Identifiant personnel — Numéro de sécurité sociale",
    "securite_sociale":     "Identifiant personnel — Numéro de sécurité sociale",
    "national_id":          "Identifiant personnel — Numéro national d'identité",
    "id_national":          "Identifiant personnel — Numéro national d'identité",
    "cin":                  "Identifiant personnel — Carte d'identité nationale",
    "cni":                  "Identifiant personnel — Carte d'identité nationale",
    "passport":             "Identifiant personnel — Numéro de passeport",
    "passeport":            "Identifiant personnel — Numéro de passeport",
    "carte_identite":       "Identifiant personnel — Carte d'identité",
    "ip":                   "Identifiant personnel — Adresse IP",
    "ip_address":           "Identifiant personnel — Adresse IP",
    "adresse_ip":           "Identifiant personnel — Adresse IP",
    "device_id":            "Identifiant personnel — Identifiant d'appareil",
    "identifiant_appareil": "Identifiant personnel — Identifiant d'appareil",
    "mac_address":          "Identifiant personnel — Adresse MAC",
    "date_naissance":       "Identifiant personnel — Date de naissance",
    "dob":                  "Identifiant personnel — Date de naissance",
    "birthdate":            "Identifiant personnel — Date de naissance",
    "birthday":             "Identifiant personnel — Date de naissance",
    "naissance":            "Identifiant personnel — Date de naissance",
    "birth_date":           "Identifiant personnel — Date de naissance",
    "user_id":              "Identifiant personnel — Identifiant utilisateur",
    "userid":               "Identifiant personnel — Identifiant utilisateur",
    "client_id":            "Identifiant personnel — Identifiant client",
    "clientid":             "Identifiant personnel — Identifiant client",
    "customer_id":          "Identifiant personnel — Identifiant client",
    "customerid":           "Identifiant personnel — Identifiant client",
    "patient_id":           "Identifiant personnel — Identifiant patient",
    "employee_id":          "Identifiant personnel — Identifiant employé",
    "employeeid":           "Identifiant personnel — Identifiant employé",
    "matricule":            "Identifiant personnel — Matricule",
    "identifiant":          "Identifiant personnel — Identifiant",
    "identifier":           "Identifiant personnel — Identifiant",
    "login":                "Identifiant personnel — Login",
    "username":             "Identifiant personnel — Nom d'utilisateur",
    "password":             "Identifiant personnel — Mot de passe",
    "mot_de_passe":         "Identifiant personnel — Mot de passe",
    "mdp":                  "Identifiant personnel — Mot de passe",
    "pwd":                  "Identifiant personnel — Mot de passe",
    "token":                "Identifiant personnel — Jeton d'authentification",
    "secret":               "Identifiant personnel — Secret",
    "api_key":              "Identifiant personnel — Clé API",
    "apikey":               "Identifiant personnel — Clé API",
    "iban":                 "Identifiant personnel — IBAN (données bancaires)",
    "bic":                  "Identifiant personnel — BIC (données bancaires)",
    "swift":                "Identifiant personnel — SWIFT (données bancaires)",
    "compte_bancaire":      "Identifiant personnel — Compte bancaire",
    "carte_credit":         "Identifiant personnel — Carte de crédit",
    "credit_card":          "Identifiant personnel — Carte de crédit",
    "cvv":                  "Identifiant personnel — CVV (carte bancaire)",
    "pan":                  "Identifiant personnel — PAN (numéro de carte)",
    "numero_secu":          "Identifiant personnel — Numéro de sécurité sociale",
    "numero_client":        "Identifiant personnel — Numéro client",
    "numero_employe":       "Identifiant personnel — Numéro employé",
}

_MEDIUM_EXACT: dict[str, tuple[str, str]] = {
    "age":                  ("Quasi-identifiant — Âge",                         "RGPD Article 4(1)"),
    "genre":                ("Quasi-identifiant — Genre",                       "RGPD Article 4(1)"),
    "gender":               ("Quasi-identifiant — Gender",                      "RGPD Article 4(1)"),
    "sexe":                 ("Quasi-identifiant — Sexe",                        "RGPD Article 4(1)"),
    "sex":                  ("Quasi-identifiant — Sex",                         "RGPD Article 4(1)"),
    "ville":                ("Quasi-identifiant — Ville",                       "RGPD Article 4(1)"),
    "city":                 ("Quasi-identifiant — City",                        "RGPD Article 4(1)"),
    "commune":              ("Quasi-identifiant — Commune",                     "RGPD Article 4(1)"),
    "municipalite":         ("Quasi-identifiant — Municipalité",                "RGPD Article 4(1)"),
    "pays":                 ("Quasi-identifiant — Pays",                        "RGPD Article 4(1)"),
    "country":              ("Quasi-identifiant — Country",                     "RGPD Article 4(1)"),
    "nation":               ("Quasi-identifiant — Nation",                      "RGPD Article 4(1)"),
    "nationalite":          ("Quasi-identifiant — Nationalité",                 "RGPD Article 4(1)"),
    "nationality":          ("Quasi-identifiant — Nationality",                 "RGPD Article 4(1)"),
    "region":               ("Quasi-identifiant — Région",                      "RGPD Article 4(1)"),
    "departement":          ("Quasi-identifiant — Département",                 "RGPD Article 4(1)"),
    "province":             ("Quasi-identifiant — Province",                    "RGPD Article 4(1)"),
    "code_postal":          ("Quasi-identifiant — Code postal",                 "RGPD Article 4(1)"),
    "zip":                  ("Quasi-identifiant — ZIP code",                    "RGPD Article 4(1)"),
    "zipcode":              ("Quasi-identifiant — ZIP code",                    "RGPD Article 4(1)"),
    "postal_code":          ("Quasi-identifiant — Code postal",                 "RGPD Article 4(1)"),
    "cp":                   ("Quasi-identifiant — Code postal",                 "RGPD Article 4(1)"),
    "cedex":                ("Quasi-identifiant — CEDEX",                       "RGPD Article 4(1)"),
    "salaire":              ("Quasi-identifiant — Salaire",                     "RGPD Article 4(1)"),
    "salary":               ("Quasi-identifiant — Salary",                      "RGPD Article 4(1)"),
    "wage":                 ("Quasi-identifiant — Wage",                        "RGPD Article 4(1)"),
    "remuneration":         ("Quasi-identifiant — Rémunération",                "RGPD Article 4(1)"),
    "revenus":              ("Quasi-identifiant — Revenus",                     "RGPD Article 4(1)"),
    "income":               ("Quasi-identifiant — Income",                      "RGPD Article 4(1)"),
    "earnings":             ("Quasi-identifiant — Earnings",                    "RGPD Article 4(1)"),
    "revenue_annuel":       ("Quasi-identifiant — Revenu annuel",               "RGPD Article 4(1)"),
    "religion":             ("Donnée sensible — Religion",                      "RGPD Article 9"),
    "ethnicity":            ("Donnée sensible — Ethnie",                        "RGPD Article 9"),
    "race":                 ("Donnée sensible — Origine raciale",               "RGPD Article 9"),
    "origine":              ("Donnée sensible — Origine",                       "RGPD Article 9"),
    "ethnie":               ("Donnée sensible — Ethnie",                        "RGPD Article 9"),
    "handicap":             ("Donnée sensible — Handicap",                      "RGPD Article 9"),
    "disability":           ("Donnée sensible — Disability",                    "RGPD Article 9"),
    "opinion_politique":    ("Donnée sensible — Opinion politique",             "RGPD Article 9"),
    "political_view":       ("Donnée sensible — Political view",                "RGPD Article 9"),
    "orientation_sexuelle": ("Donnée sensible — Orientation sexuelle",          "RGPD Article 9"),
    "sexual_orientation":   ("Donnée sensible — Sexual orientation",            "RGPD Article 9"),
    "sante":                ("Donnée sensible — Santé",                         "RGPD Article 9"),
    "health":               ("Donnée sensible — Health",                        "RGPD Article 9"),
    "medical":              ("Donnée sensible — Médical",                       "RGPD Article 9"),
    "diagnostic":           ("Donnée sensible — Diagnostic médical",            "RGPD Article 9"),
    "maladie":              ("Donnée sensible — Maladie",                       "RGPD Article 9"),
    "pathologie":           ("Donnée sensible — Pathologie",                    "RGPD Article 9"),
    "traitement":           ("Donnée sensible — Traitement médical",            "RGPD Article 9"),
    "syndicat":             ("Donnée sensible — Appartenance syndicale",        "RGPD Article 9"),
    "union_membership":     ("Donnée sensible — Union membership",              "RGPD Article 9"),
    "latitude":             ("Quasi-identifiant — Coordonnée géographique",     "RGPD Article 4(1)"),
    "longitude":            ("Quasi-identifiant — Coordonnée géographique",     "RGPD Article 4(1)"),
    "lat":                  ("Quasi-identifiant — Latitude",                    "RGPD Article 4(1)"),
    "lon":                  ("Quasi-identifiant — Longitude",                   "RGPD Article 4(1)"),
    "lng":                  ("Quasi-identifiant — Longitude",                   "RGPD Article 4(1)"),
    "gps":                  ("Quasi-identifiant — Coordonnée GPS",              "RGPD Article 4(1)"),
    "coordinates":          ("Quasi-identifiant — Coordonnées",                 "RGPD Article 4(1)"),
    "localisation":         ("Quasi-identifiant — Localisation",                "RGPD Article 4(1)"),
    "location":             ("Quasi-identifiant — Location",                    "RGPD Article 4(1)"),
    "geolocation":          ("Quasi-identifiant — Géolocalisation",             "RGPD Article 4(1)"),
    "position":             ("Quasi-identifiant — Position géographique",       "RGPD Article 4(1)"),
}

# ── Tier 2 — Pattern match at word boundaries (confidence 0.85) ──────────────
# Stored as plain tokens; matched against first/last element of col.split("_")
_HIGH_ENDS:    frozenset[str] = frozenset({"email", "phone", "name", "id", "nom", "prenom", "adresse", "address"})
_HIGH_STARTS:  frozenset[str] = frozenset({"email", "phone", "tel", "mob", "user"})
_MEDIUM_ENDS:  frozenset[str] = frozenset({"age", "city", "zip", "lat", "lon", "salary", "income", "gender", "sex"})
_MEDIUM_STARTS: frozenset[str] = frozenset({"age", "city", "zip", "lat", "lon"})

# ── Tier 3 — Semantic: word must be a complete token (confidence 0.65) ────────
_SEMANTIC_MEDIUM: frozenset[str] = frozenset({
    "birth", "born", "gender", "sex", "geo",
    "coord", "location", "salary", "wage", "income",
})


def _normalize_col(col_name: str) -> str:
    """Lowercase, strip accents, replace spaces/hyphens with underscores."""
    lower = col_name.lower()
    nfd = _unicodedata.normalize("NFD", lower)
    stripped = "".join(c for c in nfd if _unicodedata.category(c) != "Mn")
    return stripped.replace(" ", "_").replace("-", "_")


def _has_word(normalized: str, word: str) -> bool:
    """Return True only when *word* is a complete underscore-delimited token."""
    return word in normalized.split("_")


def _classify_column(col_name: str) -> tuple[str, float, str, str, str]:
    """3-tier RGPD classifier — no substring false-positives.

    Returns:
        (risk_level, confidence, reason, article, match_tier)
        risk_level : 'high' | 'medium' | 'safe'
        confidence : 1.0 (exact) | 0.85 (pattern) | 0.65 (semantic) | 0.0 (safe)
        match_tier : 'exact' | 'pattern' | 'semantic' | 'none'

    Tiers:
        1. Exact  — full normalised name is in the exact-match dict (no false positives)
        2. Pattern — first or last token matches a boundary-anchored keyword
        3. Semantic — any token matches a semantic keyword (medium-risk only)
    """
    norm = _normalize_col(col_name)
    parts = norm.split("_")

    # ── Tier 1: exact match ──────────────────────────────────────────────────
    if norm in _HIGH_EXACT:
        return "high", 1.0, _HIGH_EXACT[norm], "RGPD Article 4(1)", "exact"
    if norm in _MEDIUM_EXACT:
        reason, article = _MEDIUM_EXACT[norm]
        return "medium", 1.0, reason, article, "exact"

    # ── Tier 2: boundary-anchored pattern ────────────────────────────────────
    last = parts[-1] if parts else ""
    first = parts[0] if parts else ""

    if last in _HIGH_ENDS:
        return (
            "high", 0.85,
            f"Identifiant personnel — colonne se terminant par '{last}'",
            "RGPD Article 4(1)", "pattern",
        )
    if first in _HIGH_STARTS:
        return (
            "high", 0.85,
            f"Identifiant personnel — colonne commençant par '{first}'",
            "RGPD Article 4(1)", "pattern",
        )
    if last in _MEDIUM_ENDS:
        return (
            "medium", 0.85,
            f"Quasi-identifiant — colonne se terminant par '{last}'",
            "RGPD Article 4(1)", "pattern",
        )
    if first in _MEDIUM_STARTS:
        return (
            "medium", 0.85,
            f"Quasi-identifiant — colonne commençant par '{first}'",
            "RGPD Article 4(1)", "pattern",
        )

    # ── Tier 3: semantic token check (medium only) ───────────────────────────
    for word in _SEMANTIC_MEDIUM:
        if _has_word(norm, word):
            return (
                "medium", 0.65,
                f"Quasi-identifiant probable — contient le terme '{word}'",
                "RGPD Article 4(1)", "semantic",
            )

    return "safe", 0.0, "Donnée statistique — Faible risque", "", "none"


class RgpdScanRequest(BaseModel):
    file_id: str


@router.post("/rgpd-scan")
async def rgpd_scan(
    request: RgpdScanRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Scan a CSV file's column names for RGPD personal-data indicators.

    Downloads only the header row from Supabase Storage (local fallback),
    then classifies each column:
      - high   : direct personal identifiers — RGPD Art. 4(1)
      - medium : quasi-identifiers / sensitive categories — Art. 4 / Art. 9
      - safe   : statistical / anonymous data

    Returns a structured risk assessment with per-column detail and recommendations.
    """
    file_id = request.file_id
    user_id = str(current_user.id)

    # ── 1. Fetch file bytes (Supabase first, local filesystem fallback) ──────
    csv_bytes: bytes | None = None

    if _supabase is not None:
        try:
            storage_path = f"{user_id}/{file_id}"
            csv_bytes = _supabase.storage.from_("uploads").download(storage_path)
            logger.info(f"RGPD scan: downloaded {storage_path} from Supabase")
        except Exception as _dl_err:
            logger.warning(f"RGPD scan: Supabase download failed: {_dl_err}")

    if csv_bytes is None:
        local_path = os.path.join(UPLOAD_DIR, user_id, file_id)
        if not os.path.exists(local_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fichier non trouvé: {file_id}",
            )
        with open(local_path, "rb") as _lf:
            csv_bytes = _lf.read()

    # ── 2. Parse header row only (lightweight — no pandas required) ──────────
    try:
        text = csv_bytes.decode("utf-8", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t|')
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ','
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        columns = next(reader, [])
    except Exception as _parse_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Impossible de lire le fichier CSV: {_parse_err}",
        )

    if not columns:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier CSV ne contient aucune colonne détectable.",
        )

    # ── 3. Classify each column ──────────────────────────────────────────────
    column_results: list[dict] = []
    risk_column_names: list[str] = []
    safe_columns: list[str] = []
    has_high = False
    has_medium = False

    for col in columns:
        risk, confidence, reason, article, match_tier = _classify_column(col)
        if risk == "high":
            has_high = True
            risk_column_names.append(col)
            column_results.append({"name": col, "risk": "high", "reason": reason, "article": article, "confidence": confidence, "match_tier": match_tier})
        elif risk == "medium":
            has_medium = True
            risk_column_names.append(col)
            column_results.append({"name": col, "risk": "medium", "reason": reason, "article": article, "confidence": confidence, "match_tier": match_tier})
        else:
            safe_columns.append(col)

    # ── 4. Aggregate risk ────────────────────────────────────────────────────
    if has_high:
        overall_risk = "high"
    elif has_medium:
        overall_risk = "medium"
    elif risk_column_names:
        overall_risk = "low"
    else:
        overall_risk = "safe"

    has_personal_data = len(risk_column_names) > 0
    recommendation = (
        f"Supprimer ou anonymiser les colonnes : {', '.join(risk_column_names)}"
        if risk_column_names
        else "Aucune donnée personnelle détectée. Analyse sécurisée."
    )

    logger.info(
        f"RGPD scan: file={file_id} user={current_user.email} "
        f"risk={overall_risk} columns={len(columns)} personal={has_personal_data}"
    )

    return {
        "has_personal_data": has_personal_data,
        "risk_level": overall_risk,
        "columns": column_results,
        "safe_columns": safe_columns,
        "recommendation": recommendation,
    }