import asyncio
import random
from datetime import date, timedelta, datetime
import uuid

# Add the current directory to the Python path so we can import modules
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Load environment variables FIRST before importing database
load_dotenv()

from database import sessionlocal, engine
from attendance.models.attendance import Attendance
from employee_onboarding.models.employee import Employee
from sqlalchemy import select

async def seed_data():
    print("Starting Database Seed...")
    async with sessionlocal() as session:
        # 1. Get all employees
        result = await session.execute(select(Employee))
        employees = result.scalars().all()
        
        if not employees:
            print("No employees found in the database. Please add some employees first!")
            return
            
        print(f"Found {len(employees)} employees. Generating fake attendance...")
        
        records_added = 0
        today = date.today()
        
        # 2. For each employee, generate records for the past 7 days
        for employee in employees:
            # Randomly decide how many days they showed up (between 3 and 7 days)
            days_present = random.randint(3, 7)
            
            # Pick unique days from the last 7 days to avoid generating duplicates!
            day_offsets = random.sample(range(7), days_present)
            
            for day_offset in day_offsets:
                # Pick a random day in the last 7 days
                attendance_date = today - timedelta(days=day_offset)
                
                # Check if a record already exists for this person on this day
                existing = await session.execute(
                    select(Attendance).where(
                        Attendance.employee_id == employee.id,
                        Attendance.day == attendance_date
                    )
                )
                if existing.scalar_one_or_none():
                    continue # Skip if already exists
                
                # Generate a random arrival time between 8:00 AM and 10:30 AM
                hour = random.randint(8, 10)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                
                # Combine date and time
                arrival_time = datetime.combine(attendance_date, datetime.min.time())
                arrival_time = arrival_time.replace(hour=hour, minute=minute, second=second)
                
                # Create the record
                new_record = Attendance(
                    id=uuid.uuid4(),
                    employee_id=employee.id,
                    day=attendance_date,
                    date_created=arrival_time
                )
                
                session.add(new_record)
                records_added += 1
                
        # 3. Save all to database
        await session.commit()
        print(f"Success! Added {records_added} new attendance records.")

if __name__ == "__main__":
    asyncio.run(seed_data())
