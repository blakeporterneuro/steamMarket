# -*- coding: utf-8 -*-
"""
based on steamMarket_dataCollection.py but for collecting index fund data
consisting of daily price and volume for every item in a game

@author: Blake Porter
www.blakeporterneuro.com

This code is made available with the CC BY-NC-SA 4.0 license 
https://creativecommons.org/licenses/by-nc-sa/4.0/

Please note no commercial use is permitted.
"""

import requests # make http requests
import json # make sense of what the requests return
import pickle # save our data to our computer

import pandas as pd # structure out data
import numpy as np # do a bit of math
import scipy.stats as sci # do a bit more math

from datetime import datetime # make working with dates 1000x easier 
import time # become time lords

import threading #responsible for the paraleliation of the code

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# Login to steam on your browser and get your steam login cookie 
# For Chrome, settings > advanced > content settings > cookies > see all cookies and site data > find steamcommunity.com > find "steamLoginSecure" > copy the "Content" string and paste below
cookie = {'steamLoginSecure': '12345'}

# gameList as a string or list of strings 
# rust, 252490, dota2, 570; CSGO, 730; pubg, 578080; TF2, 440; payday 2 218620,unturned 304930
# you can find the app id by going to the community market and finding the appid=##### in the URL

gameList = ['730']

for gameID in gameList:
    # initialize
    allItemNames = []
    
    # find total number items
    allItemsGet = requests.get('https://steamcommunity.com/market/search/render/?search_descriptions=0&sort_column=default&sort_dir=desc&appid='+gameID+'&norender=1&count=100', cookies=cookie) # get page
    allItems = allItemsGet.content # get page content
    
    allItems = json.loads(allItems) # convert to JSON
    totalItems = allItems['total_count'] # get total count
    
    
    # you can only get 100 items at a time (despite putting in count= >100)
    # so we have to loop through in batches of 100 to get every single item name by specifying the start position
    for currPos in range(0,totalItems+20,20): # loop through all items
        time.sleep(2.5) # you cant make requests too quickly or steam gets mad
        
        # get item name of each
        allItemsGet = requests.get('https://steamcommunity.com/market/search/render/?start='+str(currPos)+'&count=100&search_descriptions=0&sort_column=default&sort_dir=desc&appid='+gameID+'&norender=1&count=5000', cookies=cookie)
        print('Items '+str(currPos)+' out of '+str(totalItems)+' code: '+str(allItemsGet.status_code)) # reassure us the code is running and we are getting good returns (code 200)
        
        allItems = allItemsGet.content
        allItems = json.loads(allItems)
        allItems = allItems['results']
        for currItem in allItems: 
            allItemNames.append(currItem['hash_name']) # save the names
            
        
    # remove dupes by converting from list to set and back again
    allItemNames = list(set(allItemNames))
    
    # Save all the name so we don't have to do this step anymore
    # use pickle to save all the names so i dont have to keep running above code
    with open(gameID+'ItemNames_4.txt', "wb") as file: # change the text file name to whatever you want
        pickle.dump(allItemNames, file)
    
    
def creating_dataframes(today = datetime.today().strftime("%m/%d/%y")):

    date_rng = pd.date_range(start='07/01/2012', end=today, freq='D') # because tf2 key
    marketIndexMaster_price = pd.DataFrame(date_rng, columns=['date'])
    marketIndexMaster_price = marketIndexMaster_price.set_index('date')

    marketIndexMaster_delta = pd.DataFrame(date_rng, columns=['date'])
    marketIndexMaster_delta = marketIndexMaster_delta.set_index('date')

    marketIndexMaster_vol = pd.DataFrame(date_rng, columns=['date'])
    marketIndexMaster_vol = marketIndexMaster_vol.set_index('date')

    # intialize our Panda's dataframe with the data we want from each item
    allItemsPD = pd.DataFrame(data=None,index=None,columns = ['itemName','initial','timeOnMarket','priceIncrease','smoothChange','priceAvg','priceSD','maxPrice','maxIdx','minPrice','minIdx','swing','volAvg','volSD','slope','rr'])
    

    return marketIndexMaster_price, marketIndexMaster_delta, marketIndexMaster_vol, allItemsPD

# need to encode symbols into ASCII for http (https://www.w3schools.com/tags/ref_urlencode.asp)
def ascii_to_http(currItem):
    currItemHTTP = currItem.replace(' ','%20') # convert spaces to %20
    currItemHTTP = currItemHTTP.replace('&','%26')  # convert & to %26
    currItemHTTP = currItemHTTP.replace("'",'%27')  # convert ' to %27
    currItemHTTP = currItemHTTP.replace("(",'%28')  # convert ' to %27
    currItemHTTP = currItemHTTP.replace(")",'%29')  # convert ' to %27
    currItemHTTP = currItemHTTP.replace("|",'%7C')  # convert ' to %27
    currItemHTTP = currItemHTTP.replace(",",'%2C')  # convert ' to %27
    
    return currItemHTTP

def requests_handler(alocatedItemNames):
    currRun = 1 # to keep track of the program running
    
    for currItem in allItemNames: # go through all item names
        currRun += 1
        time.sleep(2.5)

        currItemHTTP = ascii_to_http(currItem)

        # Just to get a simpler request
        itemUrl = 'https://steamcommunity.com/market/pricehistory/?appid='+gameID+'&market_hash_name='+currItemHTTP

        #without the try/except the program was getting interrupted when trying to get csgo items
        try:
            item = requests.get(itemUrl, cookies=cookie)  # get item data
        except requests.exceptions.ConnectionError as e:
            item = "No response"
        
        
        if item == "No response":
            print(currItemHTTP+'bad no data')
            continue

        print(str(currRun),' out of ',str(len(allItemNames))+' code: '+str(item.status_code))

        if item.status_code == 200:
            item = item.content
            item = json.loads(item)
            if item: # did we even get any data back
                itemPriceData = item['prices'] # is there price data?
                if itemPriceData == False or not itemPriceData: # if there was an issue with the request then data will return false and the for loop will just continue to the next item
                    print(currItemHTTP+'bad no data')
                    continue               # this could be cause the http item name was weird (eg symbol not converted to ASCII) but it will also occur if you make too many requests too fast (this is handled below)
                else:
                    # initialize stuff
                    itemPrices = [] # steam returns MEDIAN price for given time bin
                    itemVol = []
                    itemDate = []
                    for currDay in itemPriceData: # pull out the actual data
                        itemPrices.append(currDay[1]) # idx 1 is price
                        itemVol.append(currDay[2]) # idx 2 is volume of items sold
                        itemDate.append(datetime.strptime(currDay[0][0:11], '%b %d %Y')) # idx 0 is the date
                    
                    # lists are strings, convert to numbers
                    itemPrices = list(map(float, itemPrices))
                    itemVol = list(map(int, itemVol))
                    
                    # combine sales that occurs on the same day
                    # avg prices, sum volume
                    # certainly not the best way to do this but, whatever
                    for currDay in range(len(itemDate)-1,0,-1): # start from end (-1) and go to start
                        if itemDate[currDay] == itemDate[currDay-1]: # if current element's date same as the one before it
                            itemPrices[currDay-1] = np.mean([itemPrices[currDay],itemPrices[currDay-1]]) # average prices from the two days
                            itemVol[currDay-1] = np.sum([itemVol[currDay],itemVol[currDay-1]]) # sum volume
                            # delete the repeats
                            del itemDate[currDay] 
                            del itemVol[currDay] 
                            del itemPrices[currDay]
                    
                    # now that days are combined
                    normTime = list(range(0,len(itemPrices))) # create a new list that "normalizes" days from 0 to n, easier to work with than datetime
                    
                    # some basic data
                    timeOnMarket = (datetime.today()-itemDate[0]).days # have to do this because if sales are spare day[0] could be months/years ago
                    priceIncrease = itemPrices[-1] -itemPrices[0] # what was the price increase from day 0 to the most recent day [-1]
                    maxPrice = max(itemPrices) # max price
                    maxIdx = itemPrices.index(maxPrice) # when was the max price?
                    minPrice = min(itemPrices)
                    minIdx = itemPrices.index(minPrice)
                    swing = maxPrice - minPrice # greatest price swing
                    
                    if timeOnMarket >= 30:
                        smoothStart = np.mean(itemPrices[0:10])
                        smoothEnd = np.mean(itemPrices[-11:-1])
                        smoothChange = smoothEnd - smoothStart
                    else:
                        smoothStart = np.nan
                        smoothEnd = np.nan
                        smoothChange = np.nan
                    
                    
                    # get some descriptive stats
                    itemPriceAvg = np.mean(itemPrices) # average price
                    if len(itemPrices) > 1: # make sure there is at least two days of sales
                        itemPriceInitial = itemPrices[1] - itemPrices[0] # how much did the price jump from day 0 to 1? eg the first trading day
                    else:
                        itemPriceInitial = itemPrices[0]
                    itemVolAvg = np.mean(itemVol)
                    
                    itemPriceSD = np.std(itemPrices)
                    itemVolSD = np.std(itemVol)
                    
                    
                    # linear regression to find slope and fit
                    fitR = sci.linregress(normTime,itemPrices) # slope intercept rvalue pvalue stderr
                    RR = float(fitR[2]**2) # convert to R^2 value
                    
                    
                    # stock market
                    
                    stock = pd.DataFrame(itemDate,columns=['date'])
                    stock = stock.set_index('date')
                    stock['price'] = itemPrices
                    stock['vol'] = itemVol
                    
                    stock['delta'] = stock['price'].diff()
                    
                    with mutex:
                        marketIndex.append((currItem, [stock['price'] , stock['vol'] ,stock['delta'] ]))

                    # save data 
                    currentItemDict = {'itemName':currItem,'initial':itemPriceInitial,'timeOnMarket':timeOnMarket,'priceIncrease':priceIncrease,'smoothChange':smoothChange,'priceAvg':itemPriceAvg,'priceSD':itemPriceSD,'maxPrice':maxPrice,'maxIdx':maxIdx,'minPrice':minPrice,'minIdx':minIdx,'swing':swing,'volAvg':itemVolAvg,'volSD':itemVolSD,'slope':fitR[0],'rr':RR}
                    with mutex:
                        aditions.append(currentItemDict)
                    
            else:
                print(currItemHTTP+'bad no data')
                continue

def threads_exec(gameID):
    global mutex
    mutex = threading.Lock()                
                
    with open(gameID+'ItemNames_4.txt', "rb") as file:   # Unpickling
        allItemNames = pickle.load(file)

    #pandas dataframes are not thread safe, so we need to save data in other structures that are        
    global aditions
    aditions = []
    global marketIndex 
    marketIndex = []

    threadsArray = []
    num_threads = 100 
    works = [list(allItemNames)[i::num_threads] for i in range(num_threads)] # #spread the work among threads
    
    i = 0
    for alocatedItemNames in works: #make each thread deal with it's share of  data
        threadsArray.append(threading.Thread(target=requests_handler, args=(alocatedItemNames,))) # iniciar cada uma
        threadsArray[i].start()
        i+=1
        
    i = 0
    for _ in works: 
        threadsArray[i].join()
        i+=1

    print("done with the scrapping moving to pass data to dataframes")

    return aditions, marketIndex, threadsArray

def complete_game_processing(gameID, end = None):
    if end:
        marketIndexMaster_price, marketIndexMaster_delta, marketIndexMaster_vol, allItemsPD = creating_dataframes(end)
    else:
        #default argument is today's date
        marketIndexMaster_price, marketIndexMaster_delta, marketIndexMaster_vol, allItemsPD = creating_dataframes()
    
    aditions, marketIndex, threadsArray = threads_exec(gameID)

    for d in aditions:
        currItemPD = pd.DataFrame(d,index=[0]) 
        allItemsPD= allItemsPD.append(currItemPD,ignore_index=True) 

    for pair in marketIndex:
        marketIndexMaster_price[pair[0]] = pair[1][0]
        marketIndexMaster_vol[pair[0]] = pair[1][1]
        marketIndexMaster_delta[pair[0]] = pair[1][2]

    print("proceding to write data in files")

    # save the dataframe
    allItemsPD.to_pickle(gameID+'PriceData_4.pkl')
    marketIndexMaster_price.to_pickle(gameID+'marketPrice2.pkl')
    marketIndexMaster_vol.to_pickle(gameID+'marketVol2.pkl')
    marketIndexMaster_delta.to_pickle(gameID+'marketDelta2.pkl')
    print('Saved '+gameID)

for gameID in gameList:
    #if you want to end at a specif date pass a string with the date in %m/%d/%y format
    #as the second parameter
    complete_game_processing(gameID)

print('All item data collected')

