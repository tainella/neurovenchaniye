import sqlite3
import os
from dotenv import load_dotenv

load_dotenv(override=True)

ADMINS = [346235776]

class UserDatabase:
    def __init__(self):
        self.connection = sqlite3.connect('app/sql_database/base.db')
        self.cursor = self.connection.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY, 
                username TEXT NOT NULL,
                telegram_username TEXT)
            """)
        # if not self.exists(user_id=346235776):
        #     self.insert(user_id=346235776, 
        #                 username="Загадка Амелия Вадимовна", 
        #                 telegram_username="tainella",
        #                 approved=1,
        #                 access_rights="user")
        self.connection.commit()
    
    def __del__(self):
        self.connection.close()

    def exists(self, user_id: int) -> bool:
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        return row is not None

    def delete(self, user_id: int) -> bool:
        if self.exists(user_id):
            self.cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            self.connection.commit()
            return True
        else:
            return False

    # def is_approved(self, user_id: int) -> bool:
    #     """
    #     Проверяет одобрен ли пользвоатель (1)
    #     """
    #     row = self.cursor.execute("SELECT approved FROM users WHERE user_id = ?", (user_id,)).fetchone()
    #     if row is None:
    #         return False
    #     return bool(row[0])    

    def insert(self, user_id: int, username: str, telegram_username: str):
        """
        Регистрация
        """
        if self.exists(user_id):
            return False

        # user_count = self.cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        # if user_id in ADMINS:
        #     #  админ первый -> duty_admin
        #     if user_count == 0:
        #         access_rights = "user"
        #     else:
        #         access_rights = "user"
        #     approved = 1
        # else:
        #     access_rights = "user"
        #     approved = 1 if user_count == 0 else 0
        self.cursor.execute(
            """
            INSERT INTO users (user_id, username, telegram_username)
            VALUES (?, ?, ?)
            """,
            (user_id, username, telegram_username)
        )
        self.connection.commit()
        return True

    def get_user_telegram_link(self, user_id: int) -> str:
        user = self.get_user(user_id)
        if not user:
            return f"ID: {user_id}"
        
        username = user.get("telegram_username")
        if username:
            return f"@{username}"
        return f'[{user.get("username", "Пользователь")}](https://t.me/{user_id})'
    
    def get_user_id_by_tgname(self, tg_name: str) -> int:
        result = self.cursor.execute("""SELECT user_id
                                     FROM users
                                     WHERE telegram_username=?
                                     """, (tg_name,)).fetchone()
        if result:
            return int(result[0])
        else:
            return None

    def approve_user(self, user_id: int):
        """
        Одобрение -> 1
        """
        self.cursor.execute("UPDATE users SET approved = 1 WHERE user_id = ?", (user_id))
        self.connection.commit()

    def set_access_rights(self, user_id : int, access_rights: str):
        """
        установка прав
        """
        self.cursor.execute("""
                    UPDATE users SET access_rights=? WHERE user_id=?   
                    """, (access_rights, user_id))
        self.connection.commit()

    def get_user(self, user_id: int) -> dict:
        """
        получение данных пользователя
        """
        row = self.cursor.execute("""
            SELECT user_id, username, telegram_username
            FROM users
            WHERE user_id=?
        """,
        (user_id,)).fetchone()
        if not row:
            return {}
        return {"user_id": row[0],
                "username": row[1],
                "telegram_username": row[2],  
                }

    # def get_duty_admin_id(self) -> int:
    #     """
    #     id дежурного админа. Если такого нет, то 0
    #     """
    #     self.cursor.execute("SELECT user_id FROM users WHERE access_rights = 'user'")
    #     row = self.cursor.fetchone()
    #     return row[0] if row else 0
    
    def get_all_users(self) -> dict:
        """
        информация по всем пользателям
        """
        rows = self.cursor.execute("""
            SELECT user_id, username, telegram_username
                                    
            FROM users
        """).fetchall()

        result = []
        for r in rows:
            user_dict = {
                "user_id": r[0],
                "username": r[1],
                "telegram_username": r[2]
            }
            result.append(user_dict)
        return result
    
    def get_admins_id(self) -> list:
        """
        информация по всем админам
        """
        result = self.cursor.execute("""
            SELECT user_id
            FROM users
            WHERE access_rights IN ('user')
        """).fetchall()
        result = [r[0] for r in result]
        return result
    
if __name__ == '__main__':
    db_user = UserDatabase()
    print(db_user.get_admins_id())
    if 346235776 in db_user.get_admins_id():
        print('OK')
