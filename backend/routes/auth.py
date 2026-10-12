from botocore import regions
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from db.middleware.auth_middleware import get_current_user
from db.models.user import User
from helper.auth_helper import get_secret_hash
from secret_keys import SecretKeys
import boto3
from db.db import get_db

from pydantic_models.auth_models import (
    ConfirmSignupRequest,
    LoginRequest,
    SignupRequest,
)

router = APIRouter()
secret_keys = SecretKeys()
COGNITO_CLIENT_ID = secret_keys.COGNITO_CLIENT_ID
COGNITO_CLIENT_SECRET = secret_keys.COGNITO_CLIENT_SECRET
REGION_NAME = secret_keys.REGION_NAME

cognito_client = boto3.client("cognito-idp", region_name=REGION_NAME)


@router.post("/signup")
def signup_user(data: SignupRequest, db: Session = Depends(get_db)):
    try:
        secret_hash = get_secret_hash(
            data.email, COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET
        )
        cognito_response = cognito_client.sign_up(
            ClientId=COGNITO_CLIENT_ID,
            Username=data.email,
            Password=data.password,
            SecretHash=secret_hash,
            UserAttributes=[
                {"Name": "email", "Value": data.email},
                {"Name": "name", "Value": data.name},
            ],
        )
        cognito_sub = cognito_response.get("UserSub")
        if not cognito_sub:
            raise HTTPException(
                status_code=400, detail="Failed to create user in Cognito"
            )
        new_user = User(name=data.name, email=data.email, cognito_sub=cognito_sub)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {
            "msg": "Signup successfull . Please verify your email if required ",
            "user_id": new_user.id,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error signing up user: {str(e)}")


@router.post("/login")
def login_user(data: LoginRequest, response: Response):
    secret_hash = get_secret_hash(data.email, COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET)
    try:
        cognito_response = cognito_client.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": data.email,
                "PASSWORD": data.password,
                "SECRET_HASH": secret_hash,
            },
        )
        auth_result = cognito_response.get("AuthenticationResult")
        if not auth_result:
            raise HTTPException(status_code=400, detail="Incorrect cognito response")
        access_token = auth_result.get("AccessToken")
        refresh_token = auth_result.get("RefreshToken")

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
        )
        return {
            "message": "Login successful",
            "access_token": cognito_response.get("AuthenticationResult").get(
                "AccessToken"
            ),
        }
    except cognito_client.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error logging in user: {str(e)}")


@router.post("/confirm-signup")
def confirm_signup_user(data: ConfirmSignupRequest):
    secret_hash = get_secret_hash(data.email, COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET)
    try:
        cognito_response = cognito_client.confirm_sign_up(
            ClientId=COGNITO_CLIENT_ID,
            Username=data.email,
            ConfirmationCode=data.otp,
            SecretHash=secret_hash,
        )
        return {"message": "Signup confirmed successfully"}
    except cognito_client.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error confirming signup: {str(e)}"
        )


@router.post("/refresh-token")
def refresh_token(
    refresh_token: str = Cookie(None),
    user_cognito_sub: str = Cookie(None),
    response: Response = None,
):
    if not user_cognito_sub:
        raise HTTPException(status_code=401, detail="No user cognito sub provided")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")
    try:
        secret_hash = get_secret_hash(
            user_cognito_sub, COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET
        )
        cognito_response = cognito_client.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={
                "REFRESH_TOKEN": refresh_token,
                "SECRET_HASH": secret_hash,
            },
        )
        auth_result = cognito_response.get("AuthenticationResult")
        if not auth_result:
            raise HTTPException(status_code=400, detail="Incorrect cognito response")
        access_token = auth_result.get("AccessToken")
        refresh_token = auth_result.get("RefreshToken")
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
        )

        return {
            "message": "Token refreshed successfully",
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    except cognito_client.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error refreshing token: {str(e)}")


@router.get("/me")
def protected_route(user=Depends(get_current_user)):
    try:
        return {"message": "You are authenticated", "user": user}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting user: {str(e)}")
