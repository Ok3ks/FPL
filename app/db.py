#from utils import Gameweek, Player, League
import pandas as pd
import sqlite3
from sqlite3 import Error

import requests
from urls import FPL_URL

#Add functions to classes
def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print("Connection has been created successfully")
        return conn
    except Error as e:
        print(e)
    return conn

def create_table(conn):
    try:
        create_table_sql="""CREATE TABLE IF NOT EXISTS EPL_PLAYERS_2023_1ST_HALF (
                            player_id   INTEGER PRIMARY KEY,
                            position VARCHAR (2000),
                            team     VARCHAR (255),
                            player_name  VARCHAR (200)
                        );
                        """
        c = conn.cursor()
        c.execute(create_table_sql)
        print("Table Created")
    except Error as e:
        print(e)
    return conn

def insert(conn, data):
    try:
        #assert columns in data - conftest 
        data.to_sql("EPL_PLAYERS_2023_1ST_HALF",conn,if_exists='replace',index=False)
        conn.commit()
        print("Data Insert Successful")
    except Error as e:
        print(e)
    else:
        print("Pass a dataframe as data")

def dummy_insert(conn):
    data = [("Salah", "Midfield", "Liverpool", "2")]
    data = pd.DataFrame(data)
    insert(conn)

def insert_from_json(conn, path):
    file = pd.read_json(path)
    insert(conn, data = file)
    #assert entry in database has included
    #by the number of values in the list

def update_db_player_info(conn):
    """This function retrieves current information of players
    from the API"""
    
    home = requests.get(FPL_URL)
    home = home.json()

    team_code_to_name = {item['code']: item['name'] for item in home['teams']}
    pos_code_to_pos = {item['id'] : item['singular_name'] for item in home['element_types']}

    data = [(item['id'], team_code_to_name[item['team_code']], pos_code_to_pos[item['element_type']], item['first_name'] + " " + item['second_name'],) for item in home['elements']]
    data = pd.DataFrame(data)

    insert(conn, data)
    print(f"{len(data)} has been added to the SQLite table")


if __name__ == "__main__":
    #pass -db filepath into argparts
    connection = create_connection("/Users/max/Desktop/sqlite-tools-osx-x64-3440000/FPL") #Constant
    create_table(connection)
    update_db_player_info(connection)
    #dummy_insert(connection)

#def select_fillings_by_form_type(conn, form_type):
    #cur = conn.cursor()
    #rs=cur.execute("SELECT * FROM fillings_2021 where form_type='"+form_type+"'")
    #cols=list(map(lambda x:x[0],rs.description))
    #df = pd.DataFrame(rs.fetchall(),columns=cols)
    #return df