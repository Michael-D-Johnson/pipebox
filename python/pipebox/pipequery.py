from despydb import DesDbi
import pandas as pd
from datetime import datetime,timedelta
from sys import exit

class PipeQuery(object):
    def __init__(self,section):
        """ Connect to database using user's .desservices file"""
        dbh = DesDbi(None,section)
        cur = dbh.cursor()
        self.section = section
        self.cur = cur 
    
    def find_epoch(self,exposure):
        """ Return correct epoch name for exposure in order to use
            appropriate calibrations file"""
        epoch_query = "select name,minexpnum,maxexpnum from mjohns44.epoch"
        self.cur.execute(epoch_query)
        epochs = self.cur.fetchall()

        found = 0
        exposure = int(exposure)
        diff_list = []
        for name,minexpnum,maxexpnum in epochs:
            # Calculate difference between epoch min,max with given exposure
            # and take minimum
            min_diff = min([abs(exposure - minexpnum),abs(exposure - maxexpnum)])
            diff_list.append((name,min_diff))
            if exposure > int(minexpnum) and exposure < int(maxexpnum):
                # If exposure within epoch limits return epoch name
                found = 1
                return name
        if found == 0:
            # If exposure doesn't live within epoch limits find closest epoch to use
            min_of_min_diff = min([diff for name,diff in diff_list])
            name = [name for name,diff in diff_list if diff == min_of_min_diff][0]
            return name
    
    def get_expnums_from_tag(self,tag):
        """ Query database for each exposure with a given exposure tag.
        Returns a list of expnums."""
        expnum_query = "select distinct expnum from exposuretag where tag='%s'" % tag
        self.cur.execute(expnum_query)
        results = self.cur.fetchall()
        expnum_list = [exp[0] for exp in results]

        return expnum_list

class WidefieldQuery(PipeQuery):

    def get_expnum_info(self,exposure_list):
        """ Query database for band and nite for each given exposure.
            Returns a list of dictionaries."""
        for exp in exposure_list:
            expnum_info = "select distinct expnum, band, nite from exposure where expnum='%s'" % exp
            self.cur.execute(expnum_info)
            results = self.cur.fetchall()[0]
            yield results

    def update_df(self,df):
        """ Takes a pandas dataframe and for each exposure add column:value
            band and nite. Returns dataframe"""
        for index,row in df.iterrows():
            expnum_info = "select distinct expnum, band, nite from exposure where expnum='%s'" % row['expnum']
            self.cur.execute(expnum_info)
            expnum,band,nite = self.cur.fetchall()[0]
            df.loc[index,'nite'] = nite
            df.loc[index,'band'] = band

        return df

    def check_submitted(self,expnum,reqnum):
        """ Queries database to find number of attempts submitted for
            given exposure. Returns count"""
        was_submitted = "select count(*) from pfw_attempt where unitname= 'D00%s' and reqnum = '%s'" % (expnum,reqnum)
        self.cur.execute(was_submitted)
        submitted_or_not = self.cur.fetchone()[0]
        return submitted_or_not       
    
    def get_max(self,ignore_propid=False,ignore_program=False,ignore_all=False,**kwargs):
        """Returns expnum,nite of max(expnum) in the exposure table"""
        base_query = "select max(expnum) from exposure where obstype='object'"
        if ignore_program:
            max_object = base_query + " and propid in (%s)" % ','.join("'{0}'".format(k) for k in kwargs['propid'])
        elif ignore_propid:
            max_object = base_query + " and program in (%s)" % ','.join("'{0}'".format(k) for k in kwargs['program'])
        elif ignore_all:
            max_object = base_query
        else:
            max_object = base_query + " and program in (%s) and propid in (%s)" % (','.join("'{0}'".format(k) for k in kwargs['program']),','.join("'{0}'".format(k) for k in kwargs['propid']))
        self.cur.execute(max_object)
        max_expnum = self.cur.fetchone()[0]
        fetch_nite = "select distinct nite from exposure where expnum=%s" % (max_expnum)
        self.cur.execute(fetch_nite)
        object_nite = self.cur.fetchone()[0]
        return max_expnum,object_nite

    def get_expnums(self,nite=None,ignore_propid=False,ignore_program=False,ignore_all=False,**kwargs):
        """ Get exposure numbers and band for incoming exposures"""
        if not nite:
            raise Exception("Must specify nite!")
        print "selecting exposures to submit..."
        base_query = "select distinct expnum, band from exposure where obstype='object' and object not like '%%pointing%%' and object not like '%%focus%%' and object not like '%%donut%%' and object not like '%%test%%' and object not like '%%junk%%' and nite = '%s' " % nite
        if ignore_propid:
            get_expnum_and_band = base_query + " program in (%s)" % ','.join("'{0}'".format(k) for k in kwargs['program'])
        elif ignore_program:
            get_expnum_and_band = base_query + " and propid in (%s)" % ','.join("'{0}'".format(k) for k in kwargs['propid'])
        elif ignore_all:
            get_expnum_and_band = base_query
        else:
            get_expnum_and_band = base_query + " and program in (%s) and propid in (%s)" % (','.join("'{0}'".format(k) for k in kwargs['program']),','.join("'{0}'".format(k) for k in kwargs['propid']))
        self.cur.execute(get_expnum_and_band)
        results = self.cur.fetchall()

        return results

    def find_precal(self,date,threshold,override=True,tag=None):
        """ Returns precalnite,precalrun given specified nitestring"""
        nitestring = "%s-%s-%s" % (date[:4],date[4:6],date[6:])
        nite = datetime.strptime(nitestring,"%Y-%m-%d")
        days=1
        while days <= threshold:
            find_precal = "select distinct unitname,reqnum,attnum from pfw_attempt where unitname='%s'" % str((nite - timedelta(days=days)).date()).replace('-','')
            self.cur.execute(find_precal)
            results = self.cur.fetchall()
            max = len(results) - 1
            if len(results) != 0:
                precal_unitname,precal_reqnum,precal_attnum = results[max][0],results[max][1],results[max][2]
                status_precal = "select distinct status from task where id in (select distinct task_id from pfw_attempt where unitname='%s' and reqnum=%s and attnum=%s)" % (precal_unitname,precal_reqnum,precal_attnum)
                self.cur.execute(status_precal)
                status = self.cur.fetchone()[0] 
                break
            elif len(results) == 0 or status == 1 or status is None:
                days +=1
            if days > threshold:
                break
        if days > threshold:
            if override is True:
                if tag is None:
                    print "Must specify tag if override is True!"
                    exit(0)
                else:
                    max_tagged = "select distinct unitname,reqnum, attnum from ops_proctag where tag = '%s' and unitname in (select max(unitname) from ops_proctag where tag = '%s')" % (tag,tag)
                    self.cur.execute(max_tagged)
                    last_results = self.cur.fetchall()
                    try:
                        precal_unitname,precal_reqnum,precal_attnum = last_results[0][0],last_results[0][1],last_results[0][2]
                    except:
                        print "No tagged precals found. Please check tag or database section used..."
                        exit(0)
            elif override is False or override is None:
                if results is None:
                    print "No precals found. Please manually select input precal..."
                    exit(0)
        precal_nite = precal_unitname
        precal_run = 'r%sp0%s' % (precal_reqnum,precal_attnum)
        return precal_nite, precal_run

class NitelycalQuery(PipeQuery):

    def check_submitted(self,date):
        """Check to see if a nitelycal has been submitted with given date"""
        was_submitted = "select count(*) from pfw_attempt where unitname= '%s'" % (date)
        self.cur.execute(was_submitted)
        count = self.cur.fetchone()[0]
        return count

    def get_max(self):
        """Get nite of max dflat"""
        max_dflat = "select max(expnum) from exposure where obstype='dome flat'"
        self.cur.execute(max_dflat)
        max_expnum = self.cur.fetchone()[0]
        fetch_nite = "select distinct nite from exposure where expnum=%s" % (max_expnum)
        self.cur.execute(fetch_nite)
        dflat_nite = self.cur.fetchone()[0]
        return max_expnum,dflat_nite   

    def get_cals(self,nites_list):
        """Return calibration information for each nite found in nites_list"""
        cal_query = "select nite,date_obs,expnum,band,exptime,obstype,program,propid,object \
                     from exposure where obstype in ('zero','dome flat') \
                     and nite in (%s) order by expnum" % ','.join(nites_list)
        self.cur.execute(cal_query)
        cal_info = self.cur.fetchall()
        return cal_info

    def count_by_band(self,nites_list):
        """Return count per band of each obstype/band pair for nites in nites_list"""
        cal_query = "select count(expnum),band,obstype \
                     from exposure where obstype in ('zero','dome flat') \
                     and nite in (%s) group by band,obstype order by obstype" % ','.join(nites_list)
        self.cur.execute(cal_query)
        cal_info = self.cur.fetchall()
        print " Obstype         Band      Count"
        for row in cal_info:
            print "%09s  %09s  %09s" % (row[2], row[1], row[0])

    def update_df(self,df):
        """ Takes a pandas dataframe and for each exposure add column:value
            band, nite, obstype. Returns dataframe"""
        for index,row in df.iterrows():
            expnum_info = "select distinct expnum, band, nite, obstype from exposure where expnum='%s'" % row['expnum']
            self.cur.execute(expnum_info)
            expnum,band,nite,obstype = self.cur.fetchall()[0]
            try: 
                is_band = row['band']
                if is_band is None: 
                    df.loc[index,'band'] = band 
            except: 
                df.loc[index,'band'] = band
            try: 
                is_nite = row['nite']
                if is_nite is None: 
                    df.loc[index,'nite'] = nite
            except: 
                df.loc[index,'nite'] = nite
            try:
                is_obstype = row['obstype']
                if is_obstype is None:
                    df.loc[index,'obstype'] = obstype
            except:
                df.loc[index,'obstype'] = obstype

        return df
