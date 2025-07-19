
import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import numpy as np
import re
import requests
import os
from bs4 import BeautifulSoup
from urllib.request import urlopen
import mechanicalsoup

# ---- Original logic from notebook ----
from bs4 import BeautifulSoup
from urllib.request import urlopen
import mechanicalsoup
import pandas as pd
from datetime import datetime, timedelta
import os
import numpy as np
import re
import requests

#Define main function
def main_logic(input_path, output_path, cutoff_window, num_teams):
    
    #Build dataframe of teams from input file
    team_list = mk_team_list(input_path)
    #Build dataframe of players from input file
    UKBT_players = mk_player_list(team_list)
    #Build dictionary of all player past results from the player list
    player_results = mk_player_results(UKBT_players)
    #Make dictionary of trimmed player results based on cutoff window and dataframe of player ranking points based on top 4 results
    player_results_cutoff, player_ranking_points_df = mk_cutoff_results(cutoff_window, player_results, UKBT_players)
    #Make seeded dataframe
    seeded_df = mk_seeded_df(team_list, player_ranking_points_df)
    #Export to excel
    export2excel(output_path, seeded_df, player_ranking_points_df, UKBT_players, player_results_cutoff)
    #Make the pool formatting
    #filled_pools = mk_pools(seeded_df, num_teams)
    
    return seeded_df #, filled_pools
    
def mk_team_list(input_path):
    
    #Read in the list of player
    team_list = pd.read_excel(input_path)
    #Add a column for team title
    team_titles = []
    for index, row in team_list[["Player 1 Name", "Player 2 Name"]].iterrows():
        p1_names = re.split("\s+", row.iloc[0].rstrip().lstrip())
        p1_first = p1_names[0]
        p1_second = " ".join(p1_names[1:])
        p2_names = re.split("\s+", row.iloc[1].rstrip().lstrip())
        p2_first = p2_names[0]
        p2_second = " ".join(p2_names[1:])
        team_name = "{}. {} & {}. {}".format(p1_first[0], p1_second, p2_first[0], p2_second)
        team_titles.append(team_name)
    team_list["Team Name"] = team_titles
    
    return team_list

def mk_player_list(team_list):
    
    UKBT_players = {}
    #Fill out the dictionary using the rows of the player list
    for index, row in team_list.iterrows():
        p1_name = row.iloc[0]
        p1_UKBT = row.iloc[1]
        p2_name = row.iloc[2]
        p2_UKBT = row.iloc[3]
        UKBT_players[row.iloc[1]] = row.iloc[0]
        UKBT_players[row.iloc[3]] = row.iloc[2]
        
    return UKBT_players
    
def mk_player_results(UKBT_players):
    pages = {}
    for UKBT_number, player_name in UKBT_players.items():
        url = "https://www.ukbeachtour-playerzone.com/player?p="+str(UKBT_number)
        #page = browser.get(url)
        #pages[UKBT_number] = page.soup
        response = requests.get(url)
        html = response.content
        soup = BeautifulSoup(html, "html.parser")
        pages[UKBT_number] = soup
    #Initialise dictionary to hold player details
    player_results = {}

    for UKBT_number, player_name in UKBT_players.items():
        #Extract the table rows
        rows = pages[UKBT_number].select('tbody tr')
        partners = []
        events = []
        dates = []
        positions = []
        points = []
        for row in rows:
            try:
                partner, event, date, position, point = row.get_text().strip().split("\n")
                month, day, year = date.split("/") 
                date = datetime(int(year), int(month), int(day))
                point = int(point)
                partners.append(partner)
                events.append(event)
                dates.append(date)
                positions.append(position)
                points.append(point)
            except:
                pass
        #Build the pandas dataframe
        player_df = pd.DataFrame({'Partner':partners,
                                  'Event' : events,
                                  'Date': dates,
                                  'Position': positions,
                                  'Points': points,
                                 })
        #display(player_df.sort_values(by=['Date'], ascending=False))
        #Add to the dictionary
        player_results[UKBT_number] = player_df.sort_values(by=['Date'], ascending=False)
    
    return player_results

def mk_cutoff_results(cutoff_window, player_results, UKBT_players):

    #Get the current date and time
    current_day = datetime.today()
    #Get points cutoff date
    cutoff_date = current_day - timedelta(cutoff_window)

    #Initialise new dictionary to hold trimmed points results
    player_results_cutoff = {}

    #Initialise a dictionary to hold a players seeding points for the tournament
    player_ranking_points = {}

    for UKBT_number, results in player_results.items():
        #Select only the dates within the last 365 days
        mask = results["Date"]>cutoff_date
        trimmed_results = results[mask].sort_values(by=["Points"], ascending=False)
        player_results_cutoff[UKBT_number] = trimmed_results
        #display(trimmed_results)

        #Sum the top four results to get ranking points
        #Get the number of valid results
        num_res = len(trimmed_results["Points"])
        if num_res > 4:
            ranking_points = trimmed_results["Points"][:4].sum()
        else:
            ranking_points = trimmed_results["Points"][:num_res].sum()
        #Add to ranking points dictionary
        player_ranking_points[UKBT_number] = ranking_points
        
    player_ranking_points_df = pd.DataFrame.from_dict(player_ranking_points, orient='index', columns = ["Ranking Points"]).sort_values(by=["Ranking Points"], ascending=False)
    #Add the player names to the dataframe
    names = []
    for index in player_ranking_points_df.index:
        name = UKBT_players[index]
        names.append(name)

    player_ranking_points_df["Player Name"] = names
        
    return player_results_cutoff, player_ranking_points_df

def mk_seeded_df(team_list, player_ranking_points_df):

    team_list["Player 1 Ranking Points"] = np.zeros(len(team_list.index))
    team_list["Player 2 Ranking Points"] = np.zeros(len(team_list.index))
    team_list["Team Ranking Points"] = np.zeros(len(team_list.index))

    for index, row in team_list.iterrows():
        p1_name = row.iloc[0]
        p1_UKBT = row.iloc[1]
        p2_name = row.iloc[2]
        p2_UKBT = row.iloc[3]  
        p1_points = player_ranking_points_df["Ranking Points"].loc[p1_UKBT]
        p2_points = player_ranking_points_df["Ranking Points"].loc[p2_UKBT]
        team_list.at[index, "Player 1 Ranking Points"]=p1_points
        team_list.at[index, "Player 2 Ranking Points"]=p2_points
        team_ranking_points = p1_points + p2_points
        team_list.at[index, "Team Ranking Points"]=team_ranking_points

        seeded_df = team_list.sort_values(by=["Team Ranking Points"], ascending=False)
    seeded_df["Seed"] = np.arange(1,len(seeded_df.index)+1)
    
    return seeded_df

def export2excel(output_path, seeded_df, player_ranking_points_df, UKBT_players, player_results_cutoff):
    #Export seeded list to excel
    if os.path.isfile(output_path) == True:
        # Remove old output file if it exists
        if os.path.exists(output_path):
            os.remove(output_path)
        seeded_df.to_excel(output_path, sheet_name = "Team Seeding", index=False)
    else:
        seeded_df.to_excel(output_path, sheet_name = "Team Seeding", index=False)
        
    #Export all the trimmed tournament results for each player to excel
    for UKBT_number in player_ranking_points_df.index:
        #Get player name and number into pandas series
        player_name = UKBT_players[UKBT_number]
        heading = pd.Series({player_name : UKBT_number})
        results = player_results_cutoff[UKBT_number]
        with pd.ExcelWriter(output_path, engine="openpyxl", mode="a", if_sheet_exists="overlay") as writer:
            try:
                heading.to_excel(writer, sheet_name='Past Individual Results', header=False, startrow=writer.sheets['Past Individual Results'].max_row)
                results.to_excel(writer, sheet_name='Past Individual Results', index=False, startrow=writer.sheets['Past Individual Results'].max_row)
            except:
                heading.to_excel(writer, sheet_name='Past Individual Results', header=False)
                results.to_excel(writer, sheet_name='Past Individual Results', index=False, startrow=writer.sheets['Past Individual Results'].max_row)
            
def mk_pools(seeded_df, num_teams):
    if num_teams == 16:
        poolA = [1,8,9,16]
        poolB = [2,7,10,16]
        poolC = [3,6,11,14]
        poolD = [4,5,12,13]
        pools = {"A" : poolA, "B" : poolB, "C" : poolC, "D" : poolD}
        teams = seeded_df["Team Name"].set_axis(seeded_df["Seed"].values)
        filled_pools = {}
        i=1
        for pool, positions in pools.items():
            position_labels = ["A{}".format(i), "B{}".format(i), "C{}".format(i), "D{}".format(i)]
            team_names = [teams.iloc[int(positions[0])],teams.iloc[int(positions[1])],teams.iloc[int(positions[2])],teams.iloc[int(positions[3])]]
            pool_df = pd.DataFrame.from_dict({"Index" : position_labels, "Team" : team_names})
            filled_pools[pool] = pool_df
            i = i+1
            heading = pd.Series({"Pool {}".format(pool) : ""})
            #Export to excel 
            with pd.ExcelWriter(output_path, engine="openpyxl", mode="a", if_sheet_exists="overlay") as writer:
                try:
                    heading.to_excel(writer, sheet_name='Pools', header=False, startrow=writer.sheets['Pools'].max_row)
                    pool_df.to_excel(writer, sheet_name='Pools', index=False, startrow=writer.sheets['Pools'].max_row)
                except:
                    heading.to_excel(writer, sheet_name='Pools', header=False)
                    pool_df.to_excel(writer, sheet_name='Pools', index=False, startrow=writer.sheets['Pools'].max_row)

    elif num_teams == 24:
        poolA = [1,12,13,24]
        poolB = [2,11,14,23]
        poolC = [3,10,15,22]
        poolD = [4,9,16,21]
        poolE = [5,8,17,20]
        poolF = [6,7,18,19]
        pools = {"A" : poolA, "B" : poolB, "C" : poolC, "D" : poolD, "E" : poolE, "F" : poolF}
        teams = seeded_df["Team Name"].set_axis(seeded_df["Seed"].values)
        filled_pools = {}
        i=1
        for pool, positions in pools.items():
            position_labels = ["A{}".format(i), "B{}".format(i), "C{}".format(i), "D{}".format(i)]
            team_names = [teams.iloc[int(positions[0])],teams.iloc[int(positions[1])],teams.iloc[int(positions[2])],teams.iloc[int(positions[3])]]
            pool_df = pd.DataFrame.from_dict({"Key" : position_labels, "Team" : team_names})
            filled_pools[pool] = pool_df
            i = i+1
            heading = pd.Series({"Pool {}".format(pool) : ""})
            #Export to excel 
            with pd.ExcelWriter(output_path, engine="openpyxl", mode="a", if_sheet_exists="overlay") as writer:
                try:
                    heading.to_excel(writer, sheet_name='Pools', header=False, startrow=writer.sheets['Pools'].max_row)
                    pool_df.to_excel(writer, sheet_name='Pools', index=False, startrow=writer.sheets['Pools'].max_row)
                except:
                    heading.to_excel(writer, sheet_name='Pools', header=False)
                    pool_df.to_excel(writer, sheet_name='Pools', index=False, startrow=writer.sheets['Pools'].max_row)
    else:
        filled_pools = {}
    
    return filled_pools

# ---- Streamlit Interface ----
def main():
    st.title("UKBT Seeding App")
    st.subheader("Upload your input Excel file and set parameters to generate a seeded tournament list.")
    st.markdown("A template for the player list required can be downloaded below.")
    
    # Display download button for template
    with open("player_list_template.xlsx", "rb") as f:
        st.download_button(
            label="📥 Download Player List Template",
            data=f,
            file_name="Player_List_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    uploaded_file = st.file_uploader("Upload input Excel file (.xlsx)", type=["xlsx"], accept_multiple_files=False)
    col1, col2 = st.columns(2)
    with col1:
        cutoff_days = st.number_input("Cutoff Window (days)", min_value=1, value=365, 
                                      help="Number of days before today to consider for seeding")
    with col2:
        num_teams = st.number_input("Number of Tournament Teams", min_value=2, value=16)

    if st.button("Generate Seedings") and uploaded_file is not None:
        with st.spinner("Generating seedings..."):
            input_path = "player_list.xlsx"
            output_path = "seeded_output.xlsx"
    
            # Save uploaded file temporarily
            with open(input_path, "wb") as f:
                f.write(uploaded_file.read())
    
            try:
                main_logic(input_path, output_path, int(cutoff_days), int(num_teams))
                st.success("Seedings generated successfully!")
    
                with open(output_path, "rb") as f:
                    st.download_button("Download Seeded Excel", data=f, file_name="seeded_output.xlsx")
    
                # Display seeded results directly below
                df = pd.read_excel(output_path)
                st.subheader("📊 Seeded Teams Order")
                st.dataframe(df)
    
            except Exception as e:
                st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
