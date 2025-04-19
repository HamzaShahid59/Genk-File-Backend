from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
import fitz  # remove if you want pure built-in only
import io
from fastapi.middleware.cors import CORSMiddleware

from utils import *

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # allow frontend origin
    allow_credentials=True,
    allow_methods=["*"],  # allow all HTTP methods (POST, GET, etc.)
    allow_headers=["*"],  # allow all headers
)


@app.post("/validate-documents")
async def process_form(
    businessAddress: str = Form(...),
    firstName: str = Form(...),
    lastName: str = Form(...),
    ownerName: str = Form(...),
    companyNumber: str = Form(...),
    companyName: str = Form(...),
    IDCardAttachment: UploadFile = File(...),
    KBORegisterExtract: UploadFile = File(...),
    OfficialGazettePublication: UploadFile = File(...),
    MoralityCertificate: UploadFile = File(...),
    LiabilityInsuranceCopy: UploadFile = File(...),
    CommercialLeaseAgreement: UploadFile = File(...),
    ElectricCertificate: UploadFile = File(...),
):
    # Step 1: Check if each file contains text or images
    files = {}
    for name, file in [
        ("IDCardAttachment", IDCardAttachment),
        ("KBORegisterExtract", KBORegisterExtract),
        ("OfficialGazettePublication", OfficialGazettePublication),
        ("MoralityCertificate", MoralityCertificate),
        ("LiabilityInsuranceCopy", LiabilityInsuranceCopy),
        ("CommercialLeaseAgreement", CommercialLeaseAgreement),
        ("ElectricCertificate", ElectricCertificate),
    ]:
        contents = await file.read()
        files[name] = contents

    # Step 1: Check if each file contains text or images
    file_checks = {
        name: detect_pdf_type(data)
        for name, data in files.items()
    }

    # Step 2: Validate ID card name and expiry

    id_validation = validate_id_card(files["IDCardAttachment"], firstName,lastName)
    
    kbo_register = validate_kbo_register_extract(files["KBORegisterExtract"],
                                                 companyName,companyNumber,
                                                 firstName,lastName)
    
    official_gazette = validate_official_gazette_publication(files["OfficialGazettePublication"],
                                                 companyName,companyNumber)
    
    morality_certificate = validate_morality_certificate(files["MoralityCertificate"],
                                                 firstName,lastName)
    
    commercial_lease = validate_commercial_lease(
                    file_bytes=files["CommercialLeaseAgreement"],
                    building_owner_name=ownerName,
                    restaurant_address=businessAddress
    )

    liability_insurance = validate_liability_insurance(
        file_bytes=files["LiabilityInsuranceCopy"],
        company_name=companyName
    )

    electric_certificate = validate_electric_certificate(
        file_bytes=files["ElectricCertificate"],
        expected_address=businessAddress
    )

    return JSONResponse({
        "pdf_checks": file_checks,
        "id_card_valid": id_validation,
        "kbo_register_valid": kbo_register,
        "official_gazette_valid": official_gazette,
        "morality_certificate_valid": morality_certificate,
        "commercial_lease_valid": commercial_lease,
        "liability_insurance_valid": liability_insurance,
        "electric_certificate_valid": electric_certificate,
    })
