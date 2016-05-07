"""
.. module:: weather
   :platform: Unix
   :synopsis: Contains utilities for obtaining weather data and performing
      temperature normalization. Also includes utilities for converting
      temperatures to heating/cooling degree days.

.. moduleauthor:: Phil Ngo <ngo.phil@gmail.com>
.. moduleauthor:: Miguel Perez <miguel.a.perez4@gmail.com>
.. moduleauthor:: Stephen Suffian <stephen.suffian@gmail.com>
.. moduleauthor:: Sabina Tomkins <sabina.tomkins@gmail.com>

"""
import urllib2
import json
from datetime import datetime, timedelta, date
import collections
import pandas as pd
import numpy as np
import os
import utils
import ftplib
import StringIO
import gzip

def degree_day_regression(df, x_opt='both'):
    '''
    Function that runs the weather normalization regression on energy use data

    df: dataframe that includes
        use per day (upd)
        heating degree days per day (hddpd)
        cooling degree days per day (cddpd)

    x_opt: options for the regression function
        'hdd': run regression with just heating degree days
        'cdd': run regression with just cooling degree days
        'both' (default):
    '''

    if x_opt == 'hdd':
        covar = {'HDD': df.hdd_per_day}
        results = pd.ols(y=df.use_per_day, x = covar)
        return pd.DataFrame([[results.beta[1], results.std_err[1],
                              results.beta[0], results.std_err[0],
                              results.r2, results.r2_adj, results.nobs ]],
                            columns = ['intercept', 'intercept_std_err',
                                       'HDD', 'HDD_std_err',
                                       'R2', 'R2_adj','N_reads'])
    elif x_opt == 'cdd':
        covar = {'CDD': df.cdd_per_day}
        results = pd.ols(y=df.use_per_day, x = covar)
        return pd.DataFrame([[results.beta[1], results.std_err[1],
                              results.beta[0], results.std_err[0],
                              results.r2, results.r2_adj, results.nobs]],
                              columns = ['intercept', 'intercept_std_err',
                                         'CDD', 'CDD_std_err',
                                         'R2', 'R2_adj','N_reads'])
    elif x_opt == 'both':
        covar = {'CDD': df.cdd_per_day, 'HDD': df.hdd_per_day}
        results = pd.ols(y=df.use_per_day, x = covar)
        return pd.DataFrame([[results.beta[2], results.std_err[2],
                              results.beta[0], results.std_err[0],
                              results.beta[1], results.std_err[1],
                              results.r2, results.r2_adj, results.nobs]],
                            columns = ['intercept', 'intercept_std_err',
                                       'CDD', 'CDD_std_err',
                                       'HDD','HDD_std_err',
                                       'R2', 'R2_adj','N_reads'])
def get_hdd(ref_temp,df):
    '''
    Adds a column for heating degree days (converted from temp (F)).
    '''
    df['hdd']=ref_temp-df.temps
    df['hdd'].loc[df.hdd<0]=0
    df['hdd_cum']=df.hdd.cumsum()
    return df

def get_cdd(ref_temp,df):
    '''
    Converts a temperature to HDD.
    '''
    df['cdd']=df.temps-ref_temp
    df['cdd'].loc[df.cdd<0]=0
    df['cdd_cum']=df.cdd.cumsum()
    return df

def get_weather_data_as_df_from_zipcode(api_key,zipcode,start_date,end_date):
    """
    Return a dataframe indexed by time containing hourly weather data.
    Requires Weather underground api key.
    """
    query_results = get_weather_data(api_key,"","",start_date,end_date,zipcode=zipcode)
    temp_temps = pd.read_json(query_results)
    temp_temps =  _combine_date_time_and_index(temp_temps)
    return _remove_low_outliers_df(temp_temps,'temp')


def get_weather_data_as_df(api_key,city,state,start_date,end_date):
    """
    Return a dataframe indexed by time containing hourly weather data.
    Requires Weather underground api key.
    """
    query_results = get_weather_data(api_key,city,state,start_date,end_date)
    temp_temps = pd.read_json(query_results)
    temp_temps = _combine_date_time_and_index(temp_temps)
    return _remove_low_outliers_df(temp_temps,'temp')

def get_weather_data(api_key,city,state,start_date,end_date,zipcode=None):
    '''
    Returns a json string given a city, state, and desired start_date <datetime>, or range
    of dates to end_date.
    '''
    if(start_date is not None and end_date is not None):

        #format our date structure to pass to our http request
        date_format = "%Y%m%d"
        print 'in weather function'

        #count from start_date to end_date
        num_days = (end_date - start_date).days
        objects_list = []
        for day in range( num_days ):
            dates = start_date + timedelta(days=day)
            formatted_dates = datetime.strftime(dates, date_format)

            #create query which will access desired day's weather
            if zipcode:
                query = 'http://api.wunderground.com/api/'+ api_key +\
                    '/history_' + formatted_dates + '/q/' + zipcode + '.json'
            else:
                # use state and city
                city=city.replace(" ","%20")
                query = 'http://api.wunderground.com/api/'+ api_key +\
                    '/history_' + formatted_dates + '/q/' + state + '/' + city + '.json'
            print "Weather query: {}".format(query)

            #iterate through the number of days and query the api. dump json results every time
            f = urllib2.urlopen(query)
            #read query as a json string
            json_string = f.read()
            #parse/load json string
            parsed_json = json.loads(json_string)

            #Iterate through each json object and append it to an ordered dictionary
            for i in parsed_json['history']['observations']:
                d = collections.OrderedDict()
                d['date'] = i['date']['mon'] + '/' + i['date']['mday'] + '/' + i['date']['year']
                d['time'] = i['date']['pretty'][0:8]
                d['temp'] = i['tempi']
                d['conds'] = i['conds']
                d['wdire'] = i['wdire']
                d['wdird'] = i['wdird']
                d['hail'] = i['hail']
                d['thunder'] = i['thunder']
                d['pressurei'] = i['pressurei']
                d['snow'] = i['snow']
                d['pressurem'] = i['pressurem']
                d['fog'] = i['fog']
                d['tornado'] = i['tornado']
                d['hum'] = i['hum']
                d['tempi'] = i['tempi']
                d['tempm'] = i['tempm']
                d['dewptm'] = i['dewptm']
                d['dewpti'] = i['dewpti']
                d['rain'] = i['rain']
                d['visim'] = i['visi']
                d['wspdi'] = i['wspdi']
                d['wspdm'] = i['wspdm']
                objects_list.append(d)
        #dump the date range data list into a json object and return its data
        j = json.dumps(objects_list)
        return j

    #If we just need the data for ONE day (pass None for end_date):
    if(end_date is None):
        start_date_str = datetime.strftime(start_date, date_format)
        if zipcode:
            query = 'http://api.wunderground.com/api/'+ api_key +\
                '/history_' + start_date_str + '/q/' + zipcode + '.json'
        else:
            query = 'http://api.wunderground.com/api/'+ api_key +\
                '/history_' + start_date_str + '/q/' + state + '/' + city + '.json'
        f = urllib2.urlopen(query)
        json_string = f.read()
        parsed_json = json.loads(json_string)

        objects_list = []
        for i in parsed_json['history']['observations']:
            d = collections.OrderedDict()
            d['date'] = i['date']['mon'] + '/' + i['date']['mday'] + '/' + i['date']['year']
            d['time'] = i['date']['pretty'][0:8]
            d['temp'] = i['tempi']
            d['conds'] = i['conds']
            d['wdire'] = i['wdire']
            d['wdird'] = i['wdird']
            d['hail'] = i['hail']
            d['thunder'] = i['thunder']
            d['pressurei'] = i['pressurei']
            d['snow'] = i['snow']
            d['pressurem'] = i['pressurem']
            d['fog'] = i['fog']
            d['tornado'] = i['tornado']
            d['hum'] = i['hum']
            d['tempi'] = i['tempi']
            d['tempm'] = i['tempm']
            d['dewptm'] = i['dewptm']
            d['dewpti'] = i['dewpti']
            d['rain'] = i['rain']
            d['visim'] = i['visi']
            d['wspdi'] = i['wspdi']
            d['wspdm'] = i['wspdm']
            objects_list.append(d)

        j = json.dumps(objects_list)
        return j

class GSODWeatherSource:
    def __init__(self,station_id,start_year,end_year):
        if len(station_id) == 6:
            # given station id is the six digit code, so need to get full name
            gsod_station_index_filename = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(utils.__file__))),
                    'resources',
                    'GSOD-ISD_station_index.json')
            with open(gsod_station_index_filename,'r') as f:
                station_index = json.load(f)
                # take first station in list
                potential_station_ids = station_index[station_id]
        else:
            # otherwise, just use the given id
            potential_station_ids = [station_id]
        self._data = {}
        ftp = ftplib.FTP("ftp.ncdc.noaa.gov")
        ftp.login()
        data = []
        for year in xrange(start_year,end_year + 1):
            string = StringIO.StringIO()
            # not every station will be available in every year, so use the
            # first one that works
            for station_id in potential_station_ids:
                try:
                    ftp.retrbinary('RETR /pub/data/gsod/{year}/{station_id}-{year}.op.gz'.format(station_id=station_id,year=year),string.write)
                    break
                except (IOError,ftplib.error_perm):
                    pass
            string.seek(0)
            f = gzip.GzipFile(fileobj=string)
            self._add_file(f)
            string.close()
            f.close()
        ftp.quit()

    def _add_file(self,f):
        for line in f.readlines()[1:]:
            columns=line.split()
            self._data[columns[2]] = float(columns[3])

    def get_weather_range(self,start,end):
        temps = []
        for days in range((end - start).days):
            dt = start + timedelta(days=days)
            temps.append(self._data.get(dt.strftime("%Y%m%d"),float("nan")))
        return temps

def weather_normalize(trace,temperature,set_point):
    '''
    Returns a weather-normalized trace
    '''
    pass

def get_station_id_from_zip_code(zip_code,google_api_key,solar_api_key):
    '''
    Returns a station id given a zip code.
    '''
    [lat,lng]=get_lat_lng_from_zip_code(zip_code,google_api_key)
    station_id=get_station_id_from_lat_lng(lat,lng,solar_api_key)
    return station_id

def get_station_id_from_lat_lng(lat,lng,solar_api_key):
    '''
    Returns a station id given a lat long.
    '''
    f = urllib2.urlopen('http://developer.nrel.gov/api/solar/data_query/v1.json?api_key='+solar_api_key+'&lat='+str(lat)+'&lon='+str(lng))
    json_string = f.read()
    parsed_json = json.loads(json_string)
    station_id_unicode=parsed_json['outputs']['tmy3']['id']
    station_id=int(str.split(str(station_id_unicode),'-')[1])
    return station_id

def get_lat_lng_from_zip_code(zip_code,google_api_key):
    '''
    Returns a lat long given a zip code.
    '''
    zip_code=zip_code.replace(' ','+')
    zip_code=zip_code.replace(',','%2C')
    f = urllib2.urlopen('https://maps.googleapis.com/maps/api/geocode/json?address='+zip_code+'&key='+google_api_key)
    json_string = f.read()
    parsed_json_lat_lng = json.loads(json_string)
    lat=parsed_json_lat_lng['results'][0]['geometry']['location']['lat']
    lng=parsed_json_lat_lng['results'][0]['geometry']['location']['lng']
    return [lat,lng]

def _index_df_by_date(df):
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    df.index.snap() # snap to nearest frequency

def _combine_date_time_and_index(temp_df):
    for i,date in enumerate(temp_df['date']):
        hour_min=temp_df['time'][i].split(':')
        hour=hour_min[0]
        min_ampm=hour_min[1].split(' ')
        minute=min_ampm[0]
        if('PM' in min_ampm[1]):
            hour=int(hour)+12
            if(hour is 24):
                hour=0
        temp_df['date'][i]=date.replace(hour=int(hour),minute=int(minute))
    _index_df_by_date(temp_df)
    temp_df=temp_df.resample('H',how='mean')
    return temp_df

def _remove_low_outliers_df(df,column_name):
    '''
    This removes weather outliers below -40 degrees. This is due to
    inaccuracies in the weather API. This function requires the indexes
    to be datetimes across a consistent time interval. It uses this time
    interval to replace the outlier with its nearest neighbor.
    '''
    threshold = -40
    outliers=df[column_name][(df[column_name] < threshold)].index
    time_delta=df[column_name].index[1]-df[column_name].index[0]
    offset=time_delta.seconds+time_delta.days*3600*24
    a=0
    for a,i in enumerate(outliers):
        try: df[column_name][i]= df[column_name][i-pd.DateOffset(seconds=offset)]
        except KeyError: df[column_name][i]= df[column_name][i+pd.DateOffset(seconds=offset)]
    return df
