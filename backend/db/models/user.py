from sqlalchemy import Column, TEXT, Integer
from db.base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(TEXT, nullable=False)
    email = Column(TEXT, nullable=False, unique=True, index=True)
    cognito_sub = Column(TEXT, unique=True, index=True, nullable=False)
    
