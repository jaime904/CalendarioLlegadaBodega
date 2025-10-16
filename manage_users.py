# manage_users.py
from db import init_db, create_user
import sys

def usage():
    print("Uso: python manage_users.py crear <username> <password> <rol>")
    print("Roles válidos: admin | vendor")
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 5 or sys.argv[1] != "crear":
        usage()

    _, _, username, password, role = sys.argv
    init_db()
    try:
        create_user(username, password, role)
        print(f"✓ Usuario creado: {username} ({role})")
    except Exception as e:
        print("Error:", e)
        sys.exit(2)
