import logging
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db
from models import Patient, MedicalRecord, User
from auth import create_jwt_token, hash_password, verify_password
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.cors import CORSMiddleware
from schemas import PatientCreate, MedicalRecordCreate
from auth import verify_jwt_token  
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Doctor, AvailabilitySlot, Appointment, Patient
from auth import hash_password, verify_jwt_token
from schemas import DoctorCreate, AvailabilitySlotCreate, AppointmentCreate, AppointmentUpdate
import logging
from tasks import send_email  
from celery_app import Celery 
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

import os

load_dotenv()

import traceback
app = FastAPI()

# Add the allowed origins (where the frontend is hosted)
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")



# Configure Logging
logging.basicConfig(
    level=logging.ERROR,  # Log only errors and exceptions
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("error.log"),  # Log to a file
        logging.StreamHandler()  # Log to console
    ]
)

app = FastAPI()

# Add CORSMiddleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],  # Specifies which origins are allowed to make requests
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Middleware for error logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logging.error(f"URL: {request.url} | Method: {request.method} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/register/")
def register_user(request: UserRegister, db: Session = Depends(get_db)):
    try:
        existing_user = db.query(User).filter(User.username == request.username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")

        existing_email = db.query(User).filter(User.email == request.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already exists")

        new_user = User(
            username=request.username,
            email=request.email,
            hashed_password=hash_password(request.password)
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {"message": "User registered successfully", "user_id": new_user.id}

    
    except Exception as e:
        logging.error(f"Error in /register/: {str(e)}")
        logging.error(traceback.format_exc())  # This prints the full error stack trace
        raise HTTPException(status_code=500, detail=str(e))  

@app.post("/login/")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.username == request.username).first()
        if not user or not verify_password(request.password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Invalid credentials")

        token = create_jwt_token({"sub": user.username})
        return {"access_token": token, "token_type": "bearer"}

    except Exception as e:
        logging.error(f"Error in /login/: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")

# Register Doctor
@app.post("/register-doctor/")
def register_doctor(request: DoctorCreate, db: Session = Depends(get_db)):
    existing_email = db.query(Doctor).filter(Doctor.email == request.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")

    new_doctor = Doctor(
        name=request.name,
        specialization=request.specialization,
        contact=request.contact,
        email=request.email,
        hashed_password=hash_password(request.password)
    )
    db.add(new_doctor)
    db.commit()
    db.refresh(new_doctor)
    return {"message": "Doctor registered successfully", "doctor_id": new_doctor.id}

# Add Availability Slots
@app.post("/add-availability/")
def add_availability(slot: AvailabilitySlotCreate, db: Session = Depends(get_db), token: dict = Depends(verify_jwt_token)):
    try:
            doctor = db.query(Doctor).filter(Doctor.id == slot.doctor_id).first()
            if not doctor:
                raise HTTPException(status_code=404, detail="Doctor not found")

            new_slot = AvailabilitySlot(**slot.dict())
            db.add(new_slot)
            db.commit()
            return {"message": "Slot added successfully"}
    except Exception as e:
            db.rollback()
            print(f"Error: {str(e)}")  # Logs actual error in console
            raise HTTPException(status_code=500, detail="Failed to add availability slot")

# Configure Logging
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("error.log"), logging.StreamHandler()]
)

#  **Book Appointment (Triggers Email Notification)**
@app.post("/book-appointment/")
def book_appointment(appointment: AppointmentCreate, db: Session = Depends(get_db), token: dict = Depends(verify_jwt_token)):
    slot = db.query(AvailabilitySlot).filter(AvailabilitySlot.id == appointment.slot_id, AvailabilitySlot.is_booked == False).first()
    if not slot:
        raise HTTPException(status_code=400, detail="Slot unavailable")

    slot.is_booked = True
    new_appointment = Appointment(**appointment.dict())
    db.add(new_appointment)
    db.commit()

    # **Trigger Email Notification**
    user = db.query(User).filter(User.id == appointment.patient_id).first()
    email_body = f"Dear {user.username}, your appointment has been successfully booked!"
    send_email.apply_async((user.email, "Appointment Confirmation", email_body))

    return {"message": "Appointment booked successfully"}

# **Reschedule or Cancel Appointment (Triggers Email Notification)**
@app.put("/update-appointment/{appointment_id}/")
def update_appointment(appointment_id: int, request: AppointmentUpdate, db: Session = Depends(get_db), token: dict = Depends(verify_jwt_token)):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if request.status == "Cancelled":
        appointment.slot.is_booked = False
    appointment.status = request.status
    db.commit()

    # **Trigger Email Notification**
    user = db.query(User).filter(User.id == appointment.patient_id).first()
    email_body = f"Dear {user.username}, your appointment status has been updated to {request.status}."
    send_email.apply_async((user.email, "Appointment Update", email_body))

    return {"message": f"Appointment {request.status.lower()} successfully"}


@app.post("/register-patient/")
def register_patient(
    patient: PatientCreate, 
    db: Session = Depends(get_db), 
    token: dict = Depends(verify_jwt_token)  # Ensure only authenticated users can register a patient
):
    try:
        new_patient = Patient(**patient.dict())
        db.add(new_patient)
        db.commit()
        db.refresh(new_patient)
        return {"message": "Patient registered successfully", "patient_id": new_patient.id}
    except Exception as e:
        logging.error(f"Error in /register-patient/: {str(e)}")
        raise HTTPException(status_code=500, detail="Patient registration failed")


@app.post("/create-record/")
def create_record(
    record: MedicalRecordCreate, 
    db: Session = Depends(get_db), 
    token: dict = Depends(verify_jwt_token)  # Only authorized users can create records
):
    try:
        new_record = MedicalRecord(**record.dict())
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        return {"message": "Record created successfully", "record_id": new_record.id}
    except Exception as e:
        logging.error(f"Error in /create-record/: {str(e)}")
        raise HTTPException(status_code=500, detail="Record creation failed")


@app.get("/view-records/{patient_id}/")
def view_records(
    patient_id: int, 
    db: Session = Depends(get_db), 
    token: dict = Depends(verify_jwt_token)  # Require authentication to view records
):
    try:
        records = db.query(MedicalRecord).filter(MedicalRecord.patient_id == patient_id).all()
        return records
    except Exception as e:
        logging.error(f"Error in /view-records/{patient_id}/: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch records")


@app.put("/update-record/{record_id}/")
def update_record(
    record_id: int, 
    record: MedicalRecordCreate, 
    db: Session = Depends(get_db), 
    token: dict = Depends(verify_jwt_token)  # Ensure only authenticated users can update records
):
    try:
        db_record = db.query(MedicalRecord).filter(MedicalRecord.id == record_id).first()
        if not db_record:
            raise HTTPException(status_code=404, detail="Record not found")
        db_record.details = record.details
        db.commit()
        return {"message": "Record updated successfully"}
    except Exception as e:
        logging.error(f"Error in /update-record/{record_id}/: {str(e)}")
        raise HTTPException(status_code=500, detail="Record update failed")


@app.delete("/delete-record/{record_id}/")
def delete_record(
    record_id: int, 
    db: Session = Depends(get_db), 
    token: dict = Depends(verify_jwt_token)  # Only authenticated users can delete records
):
    try:
        db_record = db.query(MedicalRecord).filter(MedicalRecord.id == record_id).first()
        if not db_record:
            raise HTTPException(status_code=404, detail="Record not found")
        db.delete(db_record)
        db.commit()
        return {"message": "Record deleted successfully"}
    except Exception as e:
        logging.error(f"Error in /delete-record/{record_id}/: {str(e)}")
        raise HTTPException(status_code=500, detail="Record deletion failed")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # If you're using OAuth2

@app.post("/verify-token")
def verify_token(token: str = Depends(oauth2_scheme)):  # Use OAuth2 scheme if applicable
    try:
        payload = verify_jwt_token(token)  # Your JWT verification function
        user_type = payload.get("user_type")  # Extract user_type from the payload

        if user_type is None:  # Check if user_type exists
            raise HTTPException(status_code=401, detail="User type not found in token")

        return {"message": "Token is valid", "user_type": user_type}
    except HTTPException as e:
        raise e  # Re-raise HTTPExceptions from verify_jwt_token
    except Exception as e:
        logging.error(f"Token verification error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.get("/docs/")
def api_docs():
    return {"message": "Access FastAPI Swagger UI at /docs"}
