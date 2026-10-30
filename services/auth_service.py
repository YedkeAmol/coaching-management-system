from datetime import datetime, timezone
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_db

class AuthService:
    @staticmethod
    def authenticate(username, password):
        if not username or not password:
            return None
        db = get_db()
        user = db.users.find_one({"username": username.strip()})
        if not user:
            return None
        if check_password_hash(user.get("password_hash", ""), password):
            return {
                "id": str(user.get("_id")),
                "username": user.get("username"),
                "full_name": user.get("full_name", "Admin"),
                "role": user.get("role", "admin")
            }
        return None

    @staticmethod
    def change_password(username, old_pw, new_pw):
        if not username:
            return False, "User not identified."
        if not new_pw or len(new_pw) < 6:
            return False, "New password must be at least 6 characters long."
        if old_pw == new_pw:
            return False, "New password must be different from your current password."
        
        db = get_db()
        user = db.users.find_one({"username": username})
        if not user:
            return False, "User not found."
        
        if not check_password_hash(user.get("password_hash", ""), old_pw):
            return False, "Current password is incorrect."
            
        db.users.update_one(
            {"username": username},
            {"$set": {
                "password_hash": generate_password_hash(new_pw),
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        return True, "Password updated successfully."
