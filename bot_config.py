from psycopg2 import sql


class BotConfig:

    def __init__(self):
        self.conn = None
        self.cur = None
        self.config = {}
        self.config_props = ['spawn_channel', 'spawn_rate', 'reset_time', 'row_number']

    def connect(self, conn):
        self.conn = conn
        self.cur = self.conn.cursor()
        self.load_config()
    
    def load_config(self):
        self.cur.execute("SELECT * FROM bot_config;")
        query = self.cur.fetchone()
        if query is None:
            return
        for i, c in enumerate(query):
            self.config[self.config_props[i]] = c
    
    def update_config(self, prop, value):
        if self.config.get(prop, None) is not None:
            self.alter_config(prop, value)
            return
        self.config[prop] = value
        self.cur.execute(sql.SQL("INSERT INTO bot_config ({}) VALUES (%s)").format(sql.Identifier(prop)),
                         (prop, value))
        self.save()
    
    def update_reset_time(self):
        self.cur.execute("UPDATE bot_config SET reset_time=now() WHERE row_number=0;")
        self.save()
        self.cur.execute("SELECT reset_time FROM bot_config;")
        query = self.cur.fetchone()
        self.config['reset_time'] = query[0]

    def alter_config(self, prop, value):
        self.cur.execute(sql.SQL("UPDATE bot_config SET {0} = %s WHERE {0} = %s").format(sql.Identifier(prop)),
                         (value, self.config[prop]))
        self.save()
        self.config[prop] = value

    def save(self):
        self.conn.commit()


bot_config = BotConfig()