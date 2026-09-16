from werkzeug.security import generate_password_hash, check_password_hash
from models import User

def set_password(user, password):
    user.password_hash = generate_password_hash(password)

def verify_password(user, password):
    return user and check_password_hash(user.password_hash, password)
