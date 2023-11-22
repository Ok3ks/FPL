import requests
import time
import pandas as pd
import json
import numpy as np

from os.path import join, realpath

from sqlalchemy import Integer, String, create_engine, select
from sqlalchemy.orm import Session


from app.src.urls import GW_URL,FIXTURE_URL,TRANSFER_URL, HISTORY_URL
from app.src.urls import H2H_LEAGUE, LEAGUE_URL, FPL_PLAYER
from functools import lru_cache

from paths import APP_DIR
from db import Player
from update_gameweek_score import create_connection

pat = realpath(join(APP_DIR, 'fpl'))
print(pat)
engine = create_engine(f"sqlite:///{pat}/")
print(engine)
session = Session(engine)

conn = create_connection(realpath(join(APP_DIR,"fpl")))

def get_player(id, session = session):
    out = []
    if isinstance(id, list):
        for item in id:
            stmt = select(Player).where(Player.player_id == int(item))
            obj = session.scalars(stmt).one()
            out.append(obj)
    else:
        stmt = select(Player).where(Player.player_id == int(id))
        out = session.scalars(stmt).one()
    return out

def get_player_stats_from_db(id, gw,conn):
    #GameweekSc
    query = f"SELECT * FROM Gameweek_{gw} WHERE player_id = {id}"
    c = conn.cursor()
    c.execute(query)
    print(c.fetchall())

#get_player_stats_from_db(60, 3, conn)

def to_json(x:dict, fp):

    with open(fp, 'w') as outs:
        json.dump(x, outs)

    print(f"{x.keys()} stored in Json successfully")

def get_gw_transfers(alist,gw:int, all = False):
    """Input is a list of entry_id. Gw is the gameweek number
    All toggles between extracting all gameweeks or not"""
    row =  {}
    for entry_id in alist:
        r = requests.get(TRANSFER_URL.format(entry_id))
        if r.status_code == 200:
            obj = r.json()
            for item in obj:
                if all:
                    row[item['event']] = row.get(item['event'], {})
                    row[item['event']]['entry_id'] = item['entry']

                    row[item['event']][item['entry']] = row.get(item['entry'], {})

                    row[item['event']][item['entry']]['element_in'] = row[item['event']][item['entry']].get('element_in', [])
                    row[item['event']][item['entry']]['element_out'] = row[item['event']][item['entry']].get('element_out', [])

                    row[item['event']][item['entry']]['element_in'].append(item['element_in'])
                    row[item['event']][item['entry']]['element_out'].append(item['element_out'])
                else: 
                    if int(item['event']) == gw:
                        row[item['entry']] = row.get(item['entry'], {})

                        row[item['entry']]['element_in'] = row[item['entry']].get('element_in', [])
                        row[item['entry']]['element_out'] = row[item['entry']].get('element_out', [])

                        row[item['entry']]['element_in'].append(item['element_in'])
                        row[item['entry']]['element_out'].append(item['element_out'])     
    return row
        
def get_participant_entry(entry_id, gw):
    r = requests.get(FPL_PLAYER.format(entry_id, gw))
    #Logs
    print("Retrieving results, participant {} for event = {}".format(entry_id, gw))

    obj = r.json()
    team_list = {'auto_subs' : {'in': [], 'out': []}}
    
    if r.status_code == 200:

        team_list['gw'] = gw
        team_list['entry'] = entry_id
        team_list['active_chip'] = obj['active_chip']
        
        team_list['points_on_bench'] = obj['entry_history']['points_on_bench']
        team_list['total_points'] = obj['entry_history']['points']
        team_list['points_on_bench'] = obj['entry_history']['points_on_bench']
        team_list['event_transfers_cost'] = obj['entry_history']['event_transfers_cost']

        if obj['automatic_subs']:
            for item in obj['automatic_subs']:
                team_list['auto_subs']['in'].append(item['element_in'])
                team_list['auto_subs']['out'].append(item['element_out'])

        for item in obj['picks']:
            if item['is_captain']:
                team_list['captain'] = int(item['element'])
            elif item['is_vice_captain']:
                team_list['vice_captain'] = int(item['element'])
            else:
                if item['multiplier'] != 0:
                    if 'players' not in list(team_list.keys()):
                        team_list['players'] = str(item['element'])
                    else: 
                        team_list['players'] = team_list['players'] + ','+ str(item['element'])
                else:
                    if 'bench' not in list(team_list.keys()):
                        team_list['bench'] = str(item['element'])
                    else: 
                        team_list['bench'] = team_list['bench'] + ','+ str(item['element'])
    #time.sleep(3)
    return team_list

#Refresh and add to DB
class Gameweek(): 
    
    def __init__(self, gw:int):
        self.gw = gw


    def weekly_score(self):
        r = requests.get(GW_URL.format(self.gw))
        r = r.json()

        temp = {item['id']:item['stats'] for item in r['elements']}
        self.df = pd.DataFrame(temp)
        self.df = self.df.T
        self.df.columns = ['minutes',
            'goals_scored',
            'assists',
            'clean_sheets',
            'goals_conceded',
            'own_goals',
            'penalties_saved',
            'penalties_missed',
            'yellow_cards',
            'red_cards',
            'saves',
            'bonus',
            'bps',
            'influence',
            'creativity',
            'threat',
            'ict_index',
            'starts',
            'expected_goals',
            'expected_assists',
            'expected_goal_involvements',
            'expected_goals_conceded',
            'total_points',
            'in_dreamteam']

        self.df.reset_index(level= 0, names = 'id', inplace = True)
        self.df['event'] = self.gw
        return self.df
    


    def get_points(self, id): #extract from DB
        """Obtains player points using ID"""
        try:
            assert int(id) in self.df['id'].astype(int), 'All_df is not updated'
            point = self.df[self.df['id'] == int(id)]['total_points'].values.tolist()
        except KeyError:
            print("Invalid ID")
        return int(point[0]) 
        
    def basic_stats(self):
        """Measures of Central Tendency for Total points"""
        average = np.mean(self.df['total_points'])
        Q3 = np.percentile(self.df['total_points'], 75)
        Q1 = np.percentile(self.df['total_points'], 25)
        return Q1,average,Q3

class League():
    def __init__(self, league_id):
        self.league_id = league_id
        self.participants = []

    def obtain_league_participants(self):
        """This function uses the league url as an endpoint to query for participants of a league at a certain date.
        Should be used to update participants table in DB """
        has_next = True
        PAGE_COUNT = 1
        while has_next:
            r = requests.get(LEAGUE_URL.format(self.league_id, PAGE_COUNT))
            obj =r.json()
            assert r.status_code == 200, 'error connecting to the endpoint'
            del r
            self.participants.extend(obj['standings']['results'])
            has_next = obj['standings']['has_next']
            PAGE_COUNT += 1
            time.sleep(2)
        return self.participants
    
    def get_all_participant_entries(self,gw):
        self.obtain_league_participants()
        self.participant_entries = [get_participant_entry(participant['entry'],gw) for participant in self.participants]
        return self.participant_entries
    
    def get_gw_transfers(self,gw):
        if len(self.participants) > 1:
            self.entry_ids =[participant['entry'] for participant in self.participants]
            self.transfers = get_gw_transfers(self.entry_ids,gw)
        else:
            self.obtain_league_participants()
            self.transfers = get_gw_transfers(self.entry_ids,gw)
        return self.transfers
    
#Participant class

#class Participant():
    #def __init__(self,entry_id, player_name, entry_name, gw_total):
        #self.entry_id = entry_id
        #self.player_name = player_name
        #self.entry_name = entry_name
        #self.gw_total = gw_total