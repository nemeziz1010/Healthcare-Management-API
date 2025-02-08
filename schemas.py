from pydantic import BaseModel
from typing import List
from pydantic import BaseModel, EmailStr
from typing import Optional

class DoctorCreate(BaseModel):
    name: str
    specialization: str
    contact: str
    email: EmailStr
    password: str

class AvailabilitySlotCreate(BaseModel):
    doctor_id: int
    date: str  # Format 'YYYY-MM-DD'
    time: str  # Format 'HH:MM'

class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    slot_id: int

class AppointmentUpdate(BaseModel):
    status: str  # "Rescheduled" or "Cancelled"

class PatientCreate(BaseModel):
    name: str
    age: int
    gender: str
    contact: str
    medical_history: str

class MedicalRecordCreate(BaseModel):
    patient_id: int
    details: str
