from fastapi import Cookie, HTTPException
import boto3
from secret_keys import SecretKeys

secret_keys = SecretKeys()
REGION_NAME = secret_keys.REGION_NAME

cognito_client = boto3.client("cognito-idp", region_name=REGION_NAME)


def _get_user_from_cognito(access_token: str):
    try:
        user_res = cognito_client.get_user(AccessToken=access_token)
        return {attr["Name"]: attr["Value"] for attr in user_res.get("UserAttributes")}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting user from cognito: {str(e)}"
        )


def get_current_user(access_token: str = Cookie(None)):
    if not access_token:
        raise HTTPException(status_code=401, detail="User not logged in")
    try:
        user_res = _get_user_from_cognito(access_token)
        return user_res
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting user from cognito: {str(e)}"
        )
