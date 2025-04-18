import fitz  # PyMuPDF
import io
import re
from datetime import datetime , timedelta
import easyocr
from PIL import Image
from dateutil.parser import parse


def detect_pdf_type(file_bytes: bytes) -> str:
    try:
        doc = fitz.open("pdf", file_bytes)
        for page in doc:
            text = page.get_text()
            if text.strip():
                return "text"
            # fallback check
            images = page.get_images(full=True)
            if images:
                return "image"
        return "empty"
    except Exception:
        return "unreadable"


reader = easyocr.Reader(['en', 'nl'])

def validate_id_card(file_bytes: bytes, firstName: str, lastName: str) -> dict:
    try:
        # Improved text extraction with PDF type detection
        def detect_pdf_type(file_bytes: bytes) -> str:
            with fitz.open("pdf", file_bytes) as doc:
                return "text" if any(page.get_text().strip() for page in doc) else "image"

        pdf_type = detect_pdf_type(file_bytes)
        text = ""
        
        with fitz.open("pdf", file_bytes) as doc:
            for page in doc:
                if pdf_type == "text":
                    text += page.get_text()
                else:
                    pix = page.get_pixmap()
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    results = reader.readtext(img_bytes.getvalue(), detail=0)
                    text += " ".join(results)

        normalized_text = text.lower().replace('\n', ' ').replace('  ', ' ')
        clean_text = re.sub(r'[^a-z0-9./-]', ' ', normalized_text)  # Keep date separators

        # Enhanced name matching
        first_name = re.escape(firstName.lower())
        last_name = re.escape(lastName.lower())
        name_pattern = rf"\b{first_name}\b.*?\b{last_name}\b|\b{last_name}\b.*?\b{first_name}\b"
        name_match = bool(re.search(name_pattern, clean_text, re.IGNORECASE))

        # Robust date extraction patterns
        date_patterns = [
            # Handle OCR errors in "valid until" with flexible matching
            (r"(?:geldig|valid|valable|verloopt|expires?)[^\d]{1,20}(\d{2}[./-]\d{2}[./-]\d{4})", "%d.%m.%Y"),
            # General date patterns
            (r"\b(\d{2}[./-]\d{2}[./-]\d{4})\b", "%d.%m.%Y"),
            (r"\b(\d{4}[./-]\d{2}[./-]\d{2})\b", "%Y-%m-%d"),
            (r"\b(\d{2}\s\d{2}\s\d{4})\b", "%d %m %Y"),
        ]

        current_date = datetime.now()
        exp_dates = []

        for pattern, fmt in date_patterns:
            for match in re.finditer(pattern, clean_text, re.IGNORECASE):
                date_str = match.group(1)
                try:
                    # Normalize date separators
                    date_str = re.sub(r'[/-]', '.', date_str)
                    parsed_date = datetime.strptime(date_str, fmt)
                    if parsed_date > current_date:
                        exp_dates.append(parsed_date)
                except ValueError:
                    continue

        # Find latest valid date
        expiry_valid = False
        expiry_date = "Not found"
        if exp_dates:
            latest_date = max(exp_dates)
            expiry_date = latest_date.strftime("%Y-%m-%d")
            expiry_valid = latest_date > current_date

        return {
            "name_match": name_match,
            "expiry_valid": expiry_valid,
            "expiry_date": expiry_date,
            # "extracted_text": text
        }

    except Exception as e:
        return {"error": str(e)}  
    


def validate_kbo_register_extract(
    file_bytes: bytes,
    companyName: str,
    companyNumber: str,
    ownerFirstName: str,
    ownerLastName: str
) -> dict:
    try:
        pdf_type = detect_pdf_type(file_bytes)
        text = ""
        # print("User Company number is ", companyNumber)
        
        with fitz.open("pdf", file_bytes) as doc:
            for page in doc:
                if pdf_type == "text":
                    text += page.get_text()
                else:
                    pix = page.get_pixmap()
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    results = reader.readtext(img_bytes.getvalue(), detail=0)
                    text += " ".join(results)

        normalized_text = text.lower().replace('\n', ' ')
        # Remove all non-digit characters for number comparison
        plain_text = re.sub(r'\D', '', normalized_text)  # Corrected line

        # Company Name Match
        company_name_match = companyName.lower() in normalized_text

        # Company Number Match: Check if stripped number exists in the cleaned text
        stripped_company_number = re.sub(r'\D', '', companyNumber)
        company_number_match = stripped_company_number in plain_text  # Corrected check

        # Owner/Manager Name Match
        owner_full_name = f"{ownerFirstName} {ownerLastName}".lower()
        first_name_found = ownerFirstName.lower() in normalized_text
        last_name_found = ownerLastName.lower() in normalized_text
        full_name_found = owner_full_name in normalized_text
        manager_name_match = full_name_found or (first_name_found and last_name_found)

        return {
            "company_name_match": company_name_match,
            "company_number_match": company_number_match,
            "manager_name_match": manager_name_match,
            # "extracted_text": text
        }

    except Exception as e:
        return {"error": str(e)}

def validate_official_gazette_publication(
    file_bytes: bytes,
    companyName: str,
    companyNumber: str
) -> dict:
    try:
        def detect_pdf_type(file_bytes: bytes) -> str:
            """Returns 'text' if PDF contains text layers, 'image' otherwise"""
            with fitz.open("pdf", file_bytes) as doc:
                for page in doc:
                    if page.get_text().strip():
                        return "text"
                return "image"

        pdf_type = detect_pdf_type(file_bytes)
        extracted_text = ""
        
        # Extract text from PDF
        with fitz.open("pdf", file_bytes) as doc:
            for page in doc:
                if pdf_type == "text":
                    extracted_text += page.get_text()
                else:
                    # OCR processing for image-based PDFs
                    pix = page.get_pixmap()
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    ocr_results = reader.readtext(img_bytes.getvalue(), detail=0)
                    extracted_text += " ".join(ocr_results)

        # Normalization and cleaning
        normalized_text = extracted_text.lower().replace('\n', ' ')
        digits_only_text = re.sub(r'\D', '', normalized_text)  # Remove all non-digits
        
        # Company name check (case-insensitive substring match)
        company_name_match = companyName.lower() in normalized_text
        
        # Company number check (exact digit sequence match)
        cleaned_company_number = re.sub(r'\D', '', companyNumber)
        company_number_match = cleaned_company_number in digits_only_text

        return {
            "company_name_match": company_name_match,
            "company_number_match": company_number_match,
            # "extracted_text": extracted_text
        }

    except Exception as e:
        return {"error": str(e)}


def validate_morality_certificate(
    file_bytes: bytes,
    firstName: str,
    lastName: str
) -> dict:
    try:
        # PDF type detection
        def detect_pdf_type(file_bytes: bytes) -> str:
            with fitz.open("pdf", file_bytes) as doc:
                return "text" if any(page.get_text().strip() for page in doc) else "image"

        # Text extraction
        pdf_type = detect_pdf_type(file_bytes)
        extracted_text = ""
        
        with fitz.open("pdf", file_bytes) as doc:
            for page in doc:
                if pdf_type == "text":
                    extracted_text += page.get_text()
                else:
                    pix = page.get_pixmap()
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    ocr_results = reader.readtext(img_bytes.getvalue(), detail=0)
                    extracted_text += " ".join(ocr_results)

        # Normalization
        normalized_text = extracted_text.lower().replace('\n', ' ')
        clean_text = re.sub(r'[^\w\s/]', '', normalized_text)  # Keep slashes for dates

        # Name validation
        first_name = firstName.lower().strip()
        last_name = lastName.lower().strip()
        full_name = f"{first_name} {last_name}"
        name_valid = (
            full_name in normalized_text or 
            (first_name in clean_text and last_name in clean_text)
        )

        # Date validation
        date_valid = False
        certificate_date = None
        today = datetime.now().date()
        
        # Improved date pattern matching
        date_pattern = r'(?:datum\s*:?\s*)(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})'
        match = re.search(date_pattern, normalized_text, re.IGNORECASE)
        
        if not match:
            # Fallback to find first date after "Datum"
            date_section = normalized_text.split('datum', 1)[-1]
            match = re.search(r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b', date_section)

        if match:
            try:
                date_str = match.group(1)
                # Handle different date separators
                date_str = re.sub(r'[/\-\.]', '/', date_str)
                certificate_date = parse(date_str, dayfirst=True).date()
                
                # Validate date range
                if certificate_date > today:
                    date_valid = False
                else:
                    date_valid = (today - certificate_date) <= timedelta(days=30)
                    
            except Exception as date_error:
                print(f"Date parsing error: {date_error}")
                date_valid = False

        return {
            "name_valid": name_valid,
            "date_valid": date_valid,
            "certificate_date": certificate_date.isoformat() if certificate_date else None,
            # "is_current": date_valid and name_valid,
            # "extracted_text": extracted_text
        }

    except Exception as e:
        return {"error": str(e)}
    

def validate_commercial_lease(
    file_bytes: bytes,
    building_owner_name: str,
    restaurant_address: str
) -> dict:
    try:
        # PDF type detection
        def detect_pdf_type(file_bytes: bytes) -> str:
            """Detect if PDF contains text layers"""
            with fitz.open("pdf", file_bytes) as doc:
                return "text" if any(page.get_text().strip() for page in doc) else "image"

        # Extract text from PDF
        pdf_type = detect_pdf_type(file_bytes)
        extracted_text = ""
        
        with fitz.open("pdf", file_bytes) as doc:
            for page in doc:
                if pdf_type == "text":
                    extracted_text += page.get_text()
                else:
                    pix = page.get_pixmap()
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    ocr_results = reader.readtext(img_bytes.getvalue(), detail=0)
                    extracted_text += " ".join(ocr_results)

        # Normalization function
        def normalize(text: str) -> str:
            text = text.lower()
            text = re.sub(r'[^a-z0-9]', '', text)  # Remove all non-alphanumeric
            return text.strip()

        # Extract seller details
        seller_match = re.search(
            r'Seller:\s*Name:\s*(.*?)\s*Address:\s*(.*?)\s*VAT',
            extracted_text, 
            re.IGNORECASE | re.DOTALL
        )
        pdf_owner_name = seller_match.group(1).strip() if seller_match else ""

        # Improved address extraction
        address_match = re.search(
            r'located at\s+(.*?)\s*(?=\bthe Buyer\b|$)',
            extracted_text,
            re.IGNORECASE | re.DOTALL
        )
        
        if address_match:
            pdf_restaurant_address = address_match.group(1).strip()
            # Clean address formatting
            pdf_restaurant_address = ' '.join(pdf_restaurant_address.replace('\n', ' ').split())
        else:
            pdf_restaurant_address = ""

        # Normalize values for comparison
        norm_form_owner = normalize(building_owner_name)
        norm_pdf_owner = normalize(pdf_owner_name)
        norm_form_address = normalize(restaurant_address)
        norm_pdf_address = normalize(pdf_restaurant_address)

        # Validation checks
        owner_match = norm_form_owner == norm_pdf_owner
        address_match = norm_form_address == norm_pdf_address

        return {
            "building_owner_match": owner_match,
            "restaurant_address_match": address_match,
            "extracted_owner": pdf_owner_name,
            "extracted_address": pdf_restaurant_address,
            # "extracted_text": extracted_text
        }

    except Exception as e:
        return {"error": str(e)}

def validate_liability_insurance(file_bytes: bytes, company_name: str) -> dict:
    try:
        def detect_pdf_type(file_bytes: bytes) -> str:
            with fitz.open("pdf", file_bytes) as doc:
                return "text" if any(page.get_text().strip() for page in doc) else "image"

        pdf_type = detect_pdf_type(file_bytes)
        extracted_text = ""

        with fitz.open("pdf", file_bytes) as doc:
            for page in doc:
                if pdf_type == "text":
                    extracted_text += page.get_text()
                else:
                    pix = page.get_pixmap()
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    ocr_results = reader.readtext(img_bytes.getvalue(), detail=0)
                    extracted_text += " ".join(ocr_results)

        # Normalize text
        processed_text = extracted_text.replace('\n', ' ')
        processed_text = ' '.join(processed_text.split())
        normalized_text = processed_text.lower()

        company_name_match = company_name.lower() in normalized_text

        month_map = {
            'januari': '01', 'january': '01',
            'februari': '02', 'february': '02',
            'maart': '03', 'march': '03',
            'april': '04',
            'mei': '05', 'may': '05',
            'juni': '06', 'june': '06',
            'juli': '07', 'july': '07',
            'augustus': '08', 'august': '08',
            'september': '09',
            'oktober': '10', 'october': '10',
            'november': '11',
            'december': '12'
        }

        def parse_date(date_str: str) -> str:
            date_str = re.sub(r'[/.-]', ' ', date_str)
            parts = re.split(r'\s+', date_str.strip())
            if len(parts) == 3:
                day, month, year = parts
                if month.lower() in month_map:
                    month = month_map[month.lower()]
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            return None

        # Enhanced regex to tolerate newlines and extra words
        date_range_pattern = r"van\s+(\d{1,2}\s+\w+\s+\d{4})\s+tot\s+(\d{1,2}\s+\w+\s+\d{4})"
        matches = re.findall(date_range_pattern, extracted_text, flags=re.IGNORECASE)

        end_dates = []
        for _, end_date_str in matches:
            try:
                parsed = parse_date(end_date_str)
                if parsed:
                    end_dates.append(datetime.strptime(parsed, "%Y-%m-%d").date())
            except Exception:
                continue

        current_date = datetime.now().date()
        expired = True
        latest_end_date = None

        if end_dates:
            latest_end_date = max(end_dates)
            expiry_valid = latest_end_date > current_date

        return {
            "company_name_match": company_name_match,
            "expiry_valid": expiry_valid,
            "end_date": latest_end_date.isoformat() if latest_end_date else None,
            "current_date": current_date.isoformat(),
            # "extracted_text": extracted_text
        }

    except Exception as e:
        return {"error": str(e)} 

def validate_electric_certificate(file_bytes: bytes, expected_address: str) -> dict:
    try:
        def detect_pdf_type(file_bytes):
            with fitz.open("pdf", file_bytes) as doc:
                return "text" if any(page.get_text().strip() for page in doc) else "image"

        pdf_type = detect_pdf_type(file_bytes)
        extracted_text = ""

        with fitz.open("pdf", file_bytes) as doc:
            for page in doc:
                if pdf_type == "text":
                    extracted_text += page.get_text()
                else:
                    pix = page.get_pixmap()
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    ocr_results = reader.readtext(img_bytes.getvalue(), detail=0)
                    extracted_text += " ".join(ocr_results)

        # Check for conformity statement
        conformity_match = re.search(r'DE INSTALLATIE IS CONFORM', extracted_text, re.IGNORECASE) is not None

        # Normalize function
        def normalize_address(address):
            cleaned = re.sub(r'[^a-zA-Z0-9\s,]', '', address.lower())
            cleaned = re.sub(r'\s+', ' ', cleaned).replace(',', ' ').strip()
            return re.sub(r'\s{2,}', ' ', cleaned)

        # Extract all address lines
        address_lines = re.findall(r'Adres:\s*(.*)', extracted_text, re.IGNORECASE)

        extracted_address = ""
        address_match = False
        norm_expected = normalize_address(expected_address)

        for line in address_lines:
            norm_line = normalize_address(line)
            if norm_line and norm_line in norm_expected or norm_expected in norm_line:
                extracted_address = line.strip()
                address_match = True
                break  # Stop on first match

        return {
                "conformity_statement_found": conformity_match,
                "address_match": address_match,
                "extracted_address": extracted_address,
                "expected_address": expected_address,
                # "extracted_text": extracted_text[:3000]  # Optional: limit for debugging
            
        }

    except Exception as e:
        return {"error": str(e)}


