#!/usr/bin/env python

import sys
from datetime import datetime
import pandas as pd
import math
from pipebox import pipequery

def create_dataframe(query_object):
    df = pd.DataFrame(query_object,columns=['nite','date_obs','expnum','band',
                                            'exptime','obstype','program','propid','object'])
    return df

def fillna(dataframe):
    df = dataframe.fillna('NA')
    return df
    
def replace_bias_band(dataframe):
    dataframe.loc[(dataframe.obstype =='zero') & (dataframe.band != 'NA'),'band'] = 'NA'
    return dataframe

def remove_junk(dataframe):
    """ If PTC, junk, test, or focus show up in program, remove """
    df = dataframe[(dataframe.object.str.contains('PTC') == False) &
                   (dataframe.object.str.contains('junk') == False) &
                   (dataframe.object.str.contains('focus') == False) &
                   (dataframe.object.str.contains('test') == False) &
                   (dataframe.object.str.contains('flush') == False)]

    return df

def remove_gap_expnums(dataframe,tdelta=60):
    """ Remove exposures that occur greater than tdelta from previous exposures. Assumes
        testing or otherwise - precautionary"""
    index_list = []
    for i,row in dataframe[1:].iterrows():
        j = i - 1
        # Current exposure's obs time
        obs1 = datetime.strptime(row['date_obs'],'%Y-%m-%dT%H:%M:%S.%f')
        date1 = obs1.date()
        # Prior exposure's obs time
        obs2 = datetime.strptime(dataframe.loc[j,'date_obs'],'%Y-%m-%dT%H:%M:%S.%f')
        date2 = obs2.date()
        # Create datetime objects to compute difference in time
        if date1 == date2:
            timediff = obs1 - obs2
            diffstr = str(timediff).split(':')[2]
            if float(diffstr) > tdelta:
                index_list.append(i)
    if index_list:
        new_df = dataframe.drop(dataframe.index([index_list]))
        return new_df
    else:
        return dataframe

def remove_first_in_sequence(dataframe):
    """ Remove the first exposure in any given sequence """
    grouped = dataframe.groupby(by=['obstype','nite','band','object'])
    first_index_list = []
    for name,group in grouped:
        first_index_list.append(group.index[0])
    new_df = dataframe.drop(dataframe.index[first_index_list])
    return new_df

def remove_sat_rband(dataframe):
    """ Remove r-band exposures with exptime greater than 15 seconds. Avoids
        saturated exposures """
    nor_df = dataframe[(dataframe.band !='r')]
    r_df = dataframe[(dataframe.band == 'r') & (dataframe.exptime <= 15)]
    df = pd.concat([nor_df,r_df]) 
    return df

def create_lists(dataframe):
    """ Returns comma-separated lists of bias exposures and flat exposures 
        for use in WCL """
    bias_list = list(dataframe[(dataframe.obstype=='zero')].expnum.values)
    dflat_list = list(dataframe[(dataframe.obstype=='dome flat')].expnum.values)
    return bias_list,dflat_list 

def final_count_by_band(dataframe):
    """ Returns count per band of exposures to be included in processing """
    grouped = dataframe.groupby(by=['obstype','band']).agg(['count'])['expnum']
    print(grouped)


def is_count_by_band(dataframe,bands_to_process=['g','r','Y','i','z','u','VR'],min_per_sequence=5):
    """ Returns count per band of exposures to be included in processing """
    grouped_df = dataframe.groupby(by=['obstype','band'])
    agged = grouped_df.agg(['count'])['expnum']
    is_false = []
    for name,group in grouped_df:
        count = len(group)
        if group.band.unique()[0] in bands_to_process:
            if count < min_per_sequence:
                print('Not enough exposures:\n%s' % agged)
                is_false.append(False)
            else:
                is_false.append(True)

    if False in is_false:
        print('Not enough exposures!')
        print(agged)
        print('Exiting...')
        sys.exit(1)
    else:
        print('Enough exposures per band are present. Able to process!')

def create_clean_df(query_object):
    """ Combines all functions in nitelycal_lib """
    df = create_dataframe(query_object)
    nafilled_df = fillna(df)
    biasband_df = replace_bias_band(nafilled_df)
    junkless_df = remove_junk(biasband_df)
    satr_df = remove_sat_rband(junkless_df)
    reindexed_df = satr_df.reset_index()
    gapless_df = remove_gap_expnums(reindexed_df)
    final_df = remove_first_in_sequence(gapless_df)
        
    return final_df

def trim_excess_exposures(df,bands,k=150,verbose=False,exclude=None):
    # k = maximum number
    def trim_flats(): 
        dff = pd.DataFrame()
        set_warning = False 
        for i in range(0,len(bands)):
            length_flat = len(df[df.band.isin([bands[i]])])
            if length_flat<k:
                set_warning = True
                if verbose:
                    print("Warning: less than {k} found for {obstype} {band} band.".format(k=k,obstype='dome flat',band=bands[i]))

            diff_flat = float(length_flat - k)  
            if diff_flat > 0:
                div_flat = int(math.ceil(length_flat/diff_flat))
                remove_expnums= df[(df.band.isin([bands[i]])) & (~df.obstype.isin(['zero']))].iloc[::div_flat,:]['expnum'].values
                dff = dff.append(df[(df.band.isin([bands[i]])) & (~df.obstype.isin(['zero'])) & (~df.expnum.isin(remove_expnums))])
            else:
                dff = dff.append(df[(df.band.isin([bands[i]])) & (~df.obstype.isin(['zero']))])

        return (dff,set_warning)

    def trim_zeros():
        # Trimming zeros
        set_warning = False
        length_zero = len(df[df.obstype.isin(['zero'])])
        if length_zero<k:
            set_warning = True
            if verbose:
                print("Warning: less than {k} found for {obstype}.".format(k=k,obstype='zero'))

        diff_zero = float(length_zero - k)
        if diff_zero >0:
            div_zero= int(math.ceil(length_zero/diff_zero))
            remove_zero = df[df.obstype.isin(['zero'])].iloc[::div_zero,:]['expnum'].values
            df_zero = df[df.obstype.isin(['zero']) & (~df.expnum.isin(remove_zero))]
        else: 
            df_zero = df[df.obstype.isin(['zero'])]
        
        return (df_zero,set_warning)
    if exclude == 'FB':
        df2 = df
        warning = False
    elif exclude =='B':
        df_z = df[(df.obstype.isin(['zero']))]
        df_f,warning = trim_flats()
        df2 = pd.concat([df_f,df_z],ignore_index=True)
    elif exclude == 'F':
        df_f = df[(~df.obstype.isin(['zero']))]
        df_z,warning = trim_zeros()
        df2 = pd.concat([df_f,df_z],ignore_index=True)
    else:
        df_z,zwarning = trim_zeros()
        df_f,fwarning = trim_flats()
        if zwarning or fwarning:
            warning = True
        else:
            warning = False
        df2 = pd.concat([df_f,df_z],ignore_index=True)
    return (df2,warning)

def find_no_data(df,nitelist):
    df2 = df[df.obstype=='dome flat']
    df3 = df2.groupby('nite').count()
    nites = list(df3.index) # nites with non-zero dome flats
    diff = list(set(nitelist)-set(nites)) # list of nights with zero dome flats
    if diff:
        print("Warning: No flats found for nites {}!".format(','.join(diff)))
    df = df[df.nite.isin(nites)]
    return df,nites

if __name__ == "__main__":
    cur = pipequery.NitelycalQuery('db-desoper')
    niterange = [str(n) for n in range(20151117,20151128)]
    bands = ['u','r','i','g','z','Y','VR']
    query = cur.get_cals(niterange,bands=bands)
    df = create_dataframe(query)
    #print(df)
    print(replace_bias_band(df))
    df = create_clean_df(query)
    #print(df)
    
    #is_count_by_band(df)
    count = cur.count_by_band(bands=bands)
    
    df = create_dataframe(query)
    df = fillna(df)
    df = replace_bias_band(df)
    df = remove_junk(df)
    df = remove_sat_rband(df)
    df = df.reset_index()
    df = remove_gap_expnums(df)
    df = remove_first_in_sequence(df)
    final_count_by_band(df)
