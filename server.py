from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Password constant
ADMIN_PASSWORD = "natdelmingo231"

# Models
class Employee(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    full_name: str
    gross_salary: float
    photo: Optional[str] = None  # base64 encoded image
    pix_key: Optional[str] = None
    first_half_hours: float = 0.0
    second_half_hours: float = 0.0
    first_half_advance: float = 0.0
    second_half_absences: int = 0
    food_basket_value: float = 50.0  # Default value
    created_at: datetime = Field(default_factory=datetime.utcnow)

class EmployeeCreate(BaseModel):
    full_name: str
    gross_salary: float
    password: str
    photo: Optional[str] = None
    pix_key: Optional[str] = None

class EmployeeUpdate(BaseModel):
    gross_salary: Optional[float] = None
    password: str
    pix_key: Optional[str] = None

class PasswordValidation(BaseModel):
    password: str

class SectorData(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sector_name: str  # "Setor 1" or "Setor 2"
    daily_quantity: float
    date: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SectorUpdate(BaseModel):
    password: str
    daily_quantity: float
    date: str

class EmployeeCalculation(BaseModel):
    employee_id: str
    first_half_hours: Optional[float] = None
    second_half_hours: Optional[float] = None
    first_half_advance: Optional[float] = None
    second_half_absences: Optional[int] = None
    food_basket_value: Optional[float] = None

# Employee endpoints
@api_router.get("/employees", response_model=List[Employee])
async def get_employees():
    """Get all employees"""
    employees = await db.employees.find().to_list(1000)
    return [Employee(**emp) for emp in employees]

@api_router.post("/employees", response_model=Employee)
async def create_employee(employee_data: EmployeeCreate):
    """Create a new employee with password validation"""
    if employee_data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Senha incorreta")
    
    employee_dict = employee_data.dict()
    del employee_dict['password']  # Remove password from stored data
    employee = Employee(**employee_dict)
    
    await db.employees.insert_one(employee.dict())
    return employee

@api_router.get("/employees/{employee_id}", response_model=Employee)
async def get_employee(employee_id: str):
    """Get employee by ID"""
    employee = await db.employees.find_one({"id": employee_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
    return Employee(**employee)

@api_router.put("/employees/{employee_id}/salary")
async def update_employee_salary(employee_id: str, update_data: EmployeeUpdate):
    """Update employee salary with password validation"""
    if update_data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Senha incorreta")
    
    employee = await db.employees.find_one({"id": employee_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
    
    update_dict = {}
    if update_data.gross_salary is not None:
        update_dict["gross_salary"] = update_data.gross_salary
    
    await db.employees.update_one({"id": employee_id}, {"$set": update_dict})
    return {"message": "Salário atualizado com sucesso"}

@api_router.put("/employees/{employee_id}/pix")
async def update_employee_pix(employee_id: str, update_data: EmployeeUpdate):
    """Update employee PIX key with password validation"""
    if update_data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Senha incorreta")
    
    employee = await db.employees.find_one({"id": employee_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
    
    update_dict = {}
    if update_data.pix_key is not None:
        update_dict["pix_key"] = update_data.pix_key
    
    await db.employees.update_one({"id": employee_id}, {"$set": update_dict})
    return {"message": "Chave PIX atualizada com sucesso"}

@api_router.delete("/employees/{employee_id}")
async def fire_employee(employee_id: str, password_data: PasswordValidation):
    """Fire (delete) employee with password validation"""
    if password_data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Senha incorreta")
    
    employee = await db.employees.find_one({"id": employee_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
    
    await db.employees.delete_one({"id": employee_id})
    return {"message": "Funcionário demitido com sucesso"}

@api_router.put("/employees/{employee_id}/calculations")
async def update_employee_calculations(employee_id: str, calc_data: EmployeeCalculation):
    """Update employee calculation data"""
    employee = await db.employees.find_one({"id": employee_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
    
    update_dict = {}
    if calc_data.first_half_hours is not None:
        update_dict["first_half_hours"] = calc_data.first_half_hours
    if calc_data.second_half_hours is not None:
        update_dict["second_half_hours"] = calc_data.second_half_hours
    if calc_data.first_half_advance is not None:
        update_dict["first_half_advance"] = calc_data.first_half_advance
    if calc_data.second_half_absences is not None:
        update_dict["second_half_absences"] = calc_data.second_half_absences
    if calc_data.food_basket_value is not None:
        update_dict["food_basket_value"] = calc_data.food_basket_value
    
    await db.employees.update_one({"id": employee_id}, {"$set": update_dict})
    return {"message": "Dados de cálculo atualizados com sucesso"}

@api_router.get("/employees/{employee_id}/payroll/{period}")
async def calculate_payroll(employee_id: str, period: str):
    """Calculate payroll for first or second half of month"""
    employee = await db.employees.find_one({"id": employee_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
    
    emp = Employee(**employee)
    
    if period == "first":
        # First half: 40% of gross salary, no deductions
        base_amount = emp.gross_salary * 0.4
        total_to_pay = base_amount
        return {
            "period": "Primeira Quinzena",
            "gross_salary": emp.gross_salary,
            "hours_worked": emp.first_half_hours,
            "advance_value": emp.first_half_advance,
            "absences": 0,
            "discount_value": 0.0,
            "total_to_pay": total_to_pay
        }
    
    elif period == "second":
        # Second half: 60% of gross salary minus deductions
        base_amount = emp.gross_salary * 0.6
        
        # Calculate deductions for absences
        # Each absence = day + weekend (2 days) + food basket
        daily_salary = emp.gross_salary / 30  # Assuming 30 days per month
        absence_deduction = emp.second_half_absences * (daily_salary * 3 + emp.food_basket_value)
        
        total_discount = absence_deduction
        total_to_pay = max(0, base_amount - total_discount)
        
        return {
            "period": "Segunda Quinzena",
            "gross_salary": emp.gross_salary,
            "hours_worked": emp.second_half_hours,
            "advance_value": 0.0,
            "absences": emp.second_half_absences,
            "discount_value": total_discount,
            "total_to_pay": total_to_pay
        }
    
    else:
        raise HTTPException(status_code=400, detail="Período inválido. Use 'first' ou 'second'")

# Salon/Sector endpoints
@api_router.post("/validate-password")
async def validate_password(password_data: PasswordValidation):
    """Validate admin password"""
    if password_data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Senha incorreta")
    return {"message": "Senha válida"}

@api_router.get("/sectors/{sector_name}/data")
async def get_sector_data(sector_name: str):
    """Get sector performance data"""
    sector_data = await db.sector_data.find({"sector_name": sector_name}).sort("date", -1).to_list(100)
    return [SectorData(**data) for data in sector_data]

@api_router.post("/sectors/{sector_name}/update")
async def update_sector_data(sector_name: str, update_data: SectorUpdate):
    """Update sector daily quantity with password validation"""
    if update_data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Senha incorreta")
    
    # Create new sector data entry
    sector_data = SectorData(
        sector_name=sector_name,
        daily_quantity=update_data.daily_quantity,
        date=update_data.date
    )
    
    await db.sector_data.insert_one(sector_data.dict())
    return {"message": "Dados do setor atualizados com sucesso"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()