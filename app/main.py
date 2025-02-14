from fastapi import FastAPI, Request, Query, HTTPException
from pymongo import MongoClient
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import landscape, A3
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
import os
import csv
import logging

app = FastAPI()

# Database connection
client = MongoClient("mongodb+srv://shivam66jnp:XYPPYf4gyJf5El4O@cluster0.ru4bvi9.mongodb.net/esp8266_data?retryWrites=true&w=majority")
db = client["esp8266_data"]
collection = db["sensor_data"]

templates = Jinja2Templates(directory="app/templates")

# Sensor data model
class SensorData(BaseModel):
    temperature: float
    humidity: float
    mq2_analog: int
    mq2_digital: int
    sound_analog: int
    sound_digital: int
    mq9_analog: int
    mq9_digital: int
    mq8_analog: int
    mq8_digital: int
    dust_density_pm25: float
    dust_density_pm10: float

@app.get("/")
async def home(request: Request, page: int = 1):
    per_page = 25
    total_records = collection.count_documents({})
    total_pages = (total_records + per_page - 1) // per_page

    records = list(collection.find({}, {"_id": 0})
                   .sort("timestamp", -1)
                   .skip((page - 1) * per_page)
                   .limit(per_page))
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "data": records,
        "page": page,
        "total_pages": total_pages
    })

@app.post("/insert")
async def insert_data(data: SensorData):
    record = data.dict()
    record["timestamp"] = datetime.utcnow().isoformat()
    collection.insert_one(record)
    return {"message": "Data inserted successfully"}

def build_query(start: str, end: str, download_all: bool):
    """Builds the query for fetching records from MongoDB"""
    if download_all:
        return {}  # Fetch all records

    if start and end and start > end:
        raise HTTPException(status_code=400, detail="Start date cannot be greater than end date")

    query = {}
    if start or end:
        query["timestamp"] = {}
        if start:
            query["timestamp"]["$gte"] = datetime.strptime(start, "%Y-%m-%d")
        if end:
            query["timestamp"]["$lte"] = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1, seconds=-1)  # Full day inclusion

    return query

@app.get("/download-pdf")
async def download_pdf(start: str = Query(None), end: str = Query(None), download_all: bool = Query(False)):
    """Generates and downloads sensor data as a PDF"""
    try:
        query = build_query(start, end, download_all)
        records = list(collection.find(query, {"_id": 0}).sort("timestamp", -1))

        if not records:
            return JSONResponse(content={"message": "No records found"}, status_code=404)

        pdf_path = "app/static/sensor_data.pdf"
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

        doc = SimpleDocTemplate(pdf_path, pagesize=landscape(A3))
        elements = []

        headers = [
            "Timestamp", "Temperature (°C)", "Humidity (%)",
            "MQ2 Analog", "MQ2 Digital", "Sound Analog", "Sound Digital",
            "MQ9 Analog", "MQ9 Digital", "MQ8 Analog", "MQ8 Digital",
            "Dust PM2.5", "Dust PM10"
        ]

        data = [headers] + [
            [r["timestamp"], r["temperature"], r["humidity"], r["mq2_analog"], r["mq2_digital"],
             r["sound_analog"], r["sound_digital"], r["mq9_analog"], r["mq9_digital"],
             r["mq8_analog"], r["mq8_digital"], r["dust_density_pm25"], r["dust_density_pm10"]]
            for r in records
        ]

        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(table)
        doc.build(elements)

        return FileResponse(pdf_path, filename="Sensor_Data_Report.pdf", media_type="application/pdf")

    except Exception as e:
        logging.error(f"Error generating PDF: {e}")
        return JSONResponse(content={"message": "Internal server error"}, status_code=500)

@app.get("/download-csv")
async def download_csv(start: str = None, end: str = None, download_all: bool = Query(False)):
    """Generates and downloads sensor data as a CSV"""
    try:
        query = build_query(start, end, download_all)
        records = list(collection.find(query, {"_id": 0}).sort("timestamp", -1))

        if not records:
            return JSONResponse(content={"message": "No records found"}, status_code=404)

        csv_path = "app/static/sensor_data.csv"
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)

        headers = [
            "Timestamp", "Temperature (°C)", "Humidity (%)", "MQ2 Analog", "MQ2 Digital",
            "Sound Analog", "Sound Digital", "MQ9 Analog", "MQ9 Digital",
            "MQ8 Analog", "MQ8 Digital", "Dust PM2.5", "Dust PM10"
        ]

        with open(csv_path, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            for r in records:
                writer.writerow([
                    r.get("timestamp", "N/A"), r.get("temperature", "N/A"), r.get("humidity", "N/A"),
                    r.get("mq2_analog", "N/A"), r.get("mq2_digital", "N/A"), r.get("sound_analog", "N/A"),
                    r.get("sound_digital", "N/A"), r.get("mq9_analog", "N/A"), r.get("mq9_digital", "N/A"),
                    r.get("mq8_analog", "N/A"), r.get("mq8_digital", "N/A"), r.get("dust_density_pm25", "N/A"),
                    r.get("dust_density_pm10", "N/A")
                ])

        return FileResponse(csv_path, filename="Sensor_Data.csv", media_type="text/csv")

    except Exception as e:
        logging.error(f"Error generating CSV: {e}")
        return JSONResponse(content={"message": "Internal server error"}, status_code=500)
