from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import get_db
from auth.dependencies import require_hr

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

@router.get("/messages")
async def get_contact_messages(db: AsyncSession = Depends(get_db), _=Depends(require_hr)):
    try:
        result = await db.execute(text("""
            SELECT id, name, email, subject, message, created_at
            FROM contact_messages
            ORDER BY created_at DESC
        """))
        messages = result.fetchall()
        return [
            {
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "subject": row[3],
                "message": row[4],
                "created_at": row[5]
            }
            for row in messages
        ]
    except Exception as e:
        print(f"❌ ERROR fetching messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))