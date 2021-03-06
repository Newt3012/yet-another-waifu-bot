import os
import psycopg2
import urllib.parse as urlparse


class GGManager:

    def __init__(self):
        self.ggs_data = {}
        self.conn = None
        # self.cur = self.conn.cursor()
        # self.cur.execute("SELECT * FROM users;")
        # query = self.cur.fetchall()
        # for row in query:
        #     _id, ggs, username = row
        #     self.ggs_data[str(_id)] = {'name': str(username), 'ggs': int(ggs)}

    def connect(self, maint):
        if not maint:
            DB_TOKEN = os.getenv("HEROKU_POSTGRESQL_SILVER_URL")
        else:
            DB_TOKEN = os.getenv("DATABASE_URL")
        urlparse.uses_netloc.append("postgres")
        url = urlparse.urlparse(DB_TOKEN)

        self.conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )

    def save(self):
        self.conn.commit()

    def add_user(self, _id, name):
        _id = str(_id)
        if _id in self.ggs_data:
            return
        self.ggs_data[_id] = {'name': name, 'ggs': 10}
        self.cur.execute("INSERT INTO users (id, ggs, username) VALUES (%s, %s, %s)", (_id, 10, name))
        self.save()

    def get_user(self, _id):
        _id = str(_id)
        return self.ggs_data[_id]

    def get_ggs(self, _id):
        _id = str(_id)
        return self.ggs_data[_id]['ggs']

    def add(self, _id, n):
        _id = str(_id)
        n = abs(n)
        self.ggs_data[_id]['ggs'] += n
        ggs = self.get_ggs(_id)
        self.cur.execute("UPDATE users SET ggs=%s WHERE id=%s", (ggs, _id))
        self.save()

    def sub(self, _id, n):
        _id = str(_id)
        n = abs(n)
        self.ggs_data[_id]['ggs'] -= n
        ggs = self.get_ggs(_id)
        self.cur.execute("UPDATE users SET ggs=%s WHERE id=%s", (ggs, _id))
        self.save()

    def set(self, _id, n):
        _id = str(_id)
        self.ggs_data[_id]['ggs'] = n
        self.cur.execute("UPDATE users SET ggs=%s WHERE id=%s", (n, _id))
        self.save()

    def entry_exists(self, _id):
        _id = str(_id)
        return self.ggs_data.get(_id, False)

    def close(self):
        self.cur.close()
        self.conn.close()


gg_manager = GGManager()
