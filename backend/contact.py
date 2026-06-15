from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import get_db

router = APIRouter(prefix="/contact", tags=["contact"])

class ContactForm(BaseModel):
    name: str
    email: EmailStr
    subject: str | None = None
    message: str
@router.post("/")
async def submit_contact(form: ContactForm, db: AsyncSession = Depends(get_db)):
    try:
        # Check which database we are connected to
        db_name_result = await db.execute(text("SELECT current_database()"))
        current_db = db_name_result.scalar_one()
        print(f"🟢 Connected to database: {current_db}")

        # Create table if not exists
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS contact_messages (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                subject VARCHAR(500),
                message TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await db.commit()

        # Insert message
        result = await db.execute(text("""
            INSERT INTO contact_messages (name, email, subject, message)
            VALUES (:name, :email, :subject, :message)
            RETURNING id
        """), {
            "name": form.name,
            "email": form.email,
            "subject": form.subject,
            "message": form.message
        })
        new_id = result.scalar_one()
        await db.commit()

        # Optional: immediately verify the insert
        verify = await db.execute(text("SELECT name, email FROM contact_messages WHERE id = :id"), {"id": new_id})
        row = verify.fetchone()
        print(f"✅ Verified insert: id={new_id}, name={row[0] if row else '?'}")

        print("\n" + "="*50)
        print(f"📬 CONTACT FORM SUBMISSION (saved to DB: {current_db}, id={new_id})")
        print("="*50)
        print(f"Name:    {form.name}")
        print(f"Email:   {form.email}")
        print(f"Subject: {form.subject or '(no subject)'}")
        print(f"Message:\n{form.message}")
        print("="*50 + "\n")

        return {"success": True, "id": new_id}
    except Exception as e:
        await db.rollback()
        print(f"❌ ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))