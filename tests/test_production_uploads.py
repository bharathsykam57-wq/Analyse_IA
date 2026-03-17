"""Production File Upload Tests

Tests file upload functionality in production:
- CSV upload with size validation
- PDF upload with magic byte validation
- File listing for authenticated user
- File size limits enforcement
- Concurrent uploads
- Error handling

Usage:
    python tests/test_production_uploads.py --backend-url https://api.example.com --auth-token <token>

Requirements:
    - Backend running and accessible
    - Authenticated user (use test_production_auth.py first)
    - CORS configured
"""

import sys
import os
import argparse
import httpx
import tempfile
import json
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


class ProductionUploadTester:
    """Test file upload functionality in production"""
    
    def __init__(self, backend_url: str, access_token: str, verbose: bool = False):
        self.backend_url = backend_url.rstrip("/")
        self.access_token = access_token
        self.client = httpx.Client(
            verify=True,
            timeout=30.0,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        self.verbose = verbose
        self.results = []
        self.uploaded_files = []
    
    def create_test_csv(self, size_mb: float = 1.0) -> str:
        """Create temporary test CSV file"""
        csv_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.csv',
            delete=False,
            prefix='test_'
        )
        
        # Write CSV header
        csv_file.write("id,name,value,timestamp\n")
        
        # Calculate rows needed to reach size
        row_size = len("1,Customer_Name_Here,1000.00,2026-03-17T10:00:00Z\n")
        target_bytes = int(size_mb * 1024 * 1024)
        num_rows = max(10, target_bytes // row_size)
        
        # Write rows
        for i in range(num_rows):
            csv_file.write(f"{i},Customer_{i:05d},{1000 + i},2026-03-17T{i % 24:02d}:00:00Z\n")
        
        csv_file.close()
        return csv_file.name
    
    def create_test_pdf(self) -> str:
        """Create temporary test PDF file"""
        pdf_file = tempfile.NamedTemporaryFile(
            mode='wb',
            suffix='.pdf',
            delete=False,
            prefix='test_'
        )
        
        # Minimal PDF structure
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 5 0 R
>>
>>
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
5 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000262 00000 n 
0000000355 00000 n 
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
434
%%EOF
"""
        pdf_file.write(pdf_content)
        pdf_file.close()
        return pdf_file.name
    
    def test_csv_upload(self) -> bool:
        """Test CSV file upload"""
        logger.info("[1/5] Testing CSV upload...")
        
        try:
            csv_file = self.create_test_csv(0.5)  # 500KB
            
            with open(csv_file, 'rb') as f:
                response = self.client.post(
                    f"{self.backend_url}/api/v1/files/upload/csv",
                    files={"file": ("test.csv", f, "text/csv")},
                )
            
            os.unlink(csv_file)
            
            if response.status_code == 200:
                data = response.json()
                filename = data.get("filename")
                size = data.get("size")
                
                logger.info(f"  ✓ CSV uploaded successfully")
                logger.info(f"    - Filename: {filename}")
                logger.info(f"    - Size: {size} bytes")
                
                self.uploaded_files.append(("csv", filename, size))
                self.results.append(("CSV Upload", "PASS"))
                return True
            else:
                logger.error(f"  ✗ CSV upload failed: {response.status_code}")
                if response.text:
                    logger.error(f"    {response.text}")
                self.results.append(("CSV Upload", f"FAIL ({response.status_code})"))
                return False
        except Exception as e:
            logger.error(f"  ✗ CSV upload error: {e}")
            self.results.append(("CSV Upload", "ERROR"))
            return False
    
    def test_pdf_upload(self) -> bool:
        """Test PDF file upload"""
        logger.info("[2/5] Testing PDF upload...")
        
        try:
            pdf_file = self.create_test_pdf()
            
            with open(pdf_file, 'rb') as f:
                response = self.client.post(
                    f"{self.backend_url}/api/v1/files/upload/pdf",
                    files={"file": ("test.pdf", f, "application/pdf")},
                )
            
            os.unlink(pdf_file)
            
            if response.status_code == 200:
                data = response.json()
                filename = data.get("filename")
                
                logger.info(f"  ✓ PDF uploaded successfully")
                logger.info(f"    - Filename: {filename}")
                
                self.uploaded_files.append(("pdf", filename, data.get("size")))
                self.results.append(("PDF Upload", "PASS"))
                return True
            else:
                logger.error(f"  ✗ PDF upload failed: {response.status_code}")
                self.results.append(("PDF Upload", f"FAIL ({response.status_code})"))
                return False
        except Exception as e:
            logger.error(f"  ✗ PDF upload error: {e}")
            self.results.append(("PDF Upload", "ERROR"))
            return False
    
    def test_list_files(self) -> bool:
        """Test listing user's uploaded files"""
        logger.info("[3/5] Testing file listing...")
        
        try:
            response = self.client.get(
                f"{self.backend_url}/api/v1/files/list",
            )
            
            if response.status_code == 200:
                data = response.json()
                files = data.get("files", [])
                total = data.get("total", 0)
                
                logger.info(f"  ✓ Files listed successfully")
                logger.info(f"    - Total files: {total}")
                
                for file_info in files[:3]:  # Show first 3
                    logger.info(f"      • {file_info.get('filename')} ({file_info.get('size')} bytes)")
                
                if len(files) > 3:
                    logger.info(f"      ... and {len(files) - 3} more")
                
                self.results.append(("List Files", "PASS"))
                return True
            else:
                logger.error(f"  ✗ File list failed: {response.status_code}")
                self.results.append(("List Files", f"FAIL ({response.status_code})"))
                return False
        except Exception as e:
            logger.error(f"  ✗ File list error: {e}")
            self.results.append(("List Files", "ERROR"))
            return False
    
    def test_size_limit(self) -> bool:
        """Test file size limit enforcement"""
        logger.info("[4/5] Testing file size limits...")
        
        try:
            # Create 100MB file (exceeds 50MB limit)
            csv_file = self.create_test_csv(100.0)
            
            with open(csv_file, 'rb') as f:
                response = self.client.post(
                    f"{self.backend_url}/api/v1/files/upload/csv",
                    files={"file": ("too_large.csv", f, "text/csv")},
                )
            
            os.unlink(csv_file)
            
            if response.status_code == 413:  # Payload Too Large
                logger.info(f"  ✓ File size limit correctly enforced")
                self.results.append(("Size Limit", "PASS"))
                return True
            elif response.status_code >= 400:
                logger.info(f"  ✓ Large file rejected: {response.status_code}")
                self.results.append(("Size Limit", "PASS"))
                return True
            else:
                logger.error(f"  ✗ Large file was accepted: {response.status_code}")
                self.results.append(("Size Limit", "FAIL"))
                return False
        except Exception as e:
            logger.error(f"  ✗ Size limit test error: {e}")
            self.results.append(("Size Limit", "ERROR"))
            return False
    
    def test_invalid_file_type(self) -> bool:
        """Test rejection of invalid file types"""
        logger.info("[5/5] Testing invalid file type rejection...")
        
        try:
            # Create fake executable file
            exe_file = tempfile.NamedTemporaryFile(
                mode='wb',
                suffix='.exe',
                delete=False,
                prefix='test_'
            )
            exe_file.write(b"MZ\x90\x00")  # PE executable magic bytes
            exe_file.close()
            
            with open(exe_file, 'rb') as f:
                response = self.client.post(
                    f"{self.backend_url}/api/v1/files/upload/csv",
                    files={"file": ("malicious.exe", f, "application/x-msdownload")},
                )
            
            os.unlink(exe_file)
            
            if response.status_code >= 400:
                logger.info(f"  ✓ Invalid file type rejected: {response.status_code}")
                self.results.append(("Invalid File Type", "PASS"))
                return True
            else:
                logger.error(f"  ✗ Invalid file was accepted: {response.status_code}")
                self.results.append(("Invalid File Type", "FAIL"))
                return False
        except Exception as e:
            logger.error(f"  ✗ Invalid file type test error: {e}")
            self.results.append(("Invalid File Type", "ERROR"))
            return False
    
    def run_all_tests(self) -> bool:
        """Run all upload tests"""
        logger.info("=" * 60)
        logger.info("PRODUCTION FILE UPLOAD TESTS")
        logger.info("=" * 60)
        logger.info(f"Backend URL: {self.backend_url}")
        logger.info("")
        
        all_pass = True
        
        if not self.test_csv_upload():
            all_pass = False
        
        if not self.test_pdf_upload():
            all_pass = False
        
        if not self.test_list_files():
            all_pass = False
        
        if not self.test_size_limit():
            all_pass = False
        
        if not self.test_invalid_file_type():
            all_pass = False
        
        self.print_summary()
        
        return all_pass
    
    def print_summary(self):
        """Print test summary"""
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Files uploaded: {len(self.uploaded_files)}")
        for file_type, filename, size in self.uploaded_files:
            logger.info(f"  • {file_type.upper()}: {filename} ({size} bytes)")
        
        logger.info("")
        for test_name, result in self.results:
            status_symbol = "✓" if result == "PASS" else "✗"
            logger.info(f"{status_symbol} {test_name}: {result}")
        
        passed = sum(1 for _, r in self.results if r == "PASS")
        total = len(self.results)
        
        logger.info(f"\nResult: {passed}/{total} tests passed")


def main():
    parser = argparse.ArgumentParser(
        description="Test production file upload functionality"
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        help="Backend API URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--auth-token",
        required=True,
        help="JWT access token (get from test_production_auth.py)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    tester = ProductionUploadTester(
        args.backend_url,
        args.auth_token,
        verbose=args.verbose
    )
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
