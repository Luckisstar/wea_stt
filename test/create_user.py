import os
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
import sys

# 프로젝트의 app 경로를 sys.path에 추가
sys.path.append('./api_gateway')
from app.models import User, Base

# --- 설정 ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sttuser:sttpassword@localhost:5432/sttdb")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_user():
    """새로운 사용자를 DB에 생성합니다."""
    db = SessionLocal()
    try:
        # 테이블이 없으면 생성
        Base.metadata.create_all(bind=engine)

        print("--- Create New User ---")
        username = input("Enter username: ")
        password = input("Enter password: ")
        email = input("Enter email: ")
        
        # 사용자 존재 여부 확인
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"Error: User '{username}' already exists.")
            return

        hashed_password = pwd_context.hash(password)
        new_user = User(
            id=uuid.uuid4(),
            username=username,
            hashed_password=hashed_password,
            email=email
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print(f"\n✅ User '{username}' created successfully!")
        
    finally:
        db.close()

if __name__ == "__main__":
    create_user()