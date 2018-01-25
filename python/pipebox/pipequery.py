from despydb import DesDbi
import pandas as pd
from datetime import datetime,timedelta
from sys import exit
import numpy as np, string

class PipeQuery(object):
    def __init__(self,section):
        """ Connect to database using user's .desservices file"""
        dbh = DesDbi(None,section, retry = True)
        cur = dbh.cursor()
        self.section = section
        self.dbh = dbh
        self.cur = cur 
    
    def find_epoch(self,exposure):
        """ Return correct epoch name for exposure in order to use
            appropriate calibrations file"""
        epoch_query = "select name,minexpnum,maxexpnum from ops_epoch"
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

    def get_cals_from_epoch(self, epoch,band = None,campaign= None):
        """ Query to return the unitname,reqnum,attnum of epoch-based calibrations."""
        count_for_campaign = "select count(*) from ops_epoch_inputs where name='{epoch}' \
                              and campaign='{c}'".format(epoch=epoch,c=campaign)
        self.cur.execute(count_for_campaign)
        count = self.cur.fetchall()[0][0]
        if int(count) == 0:
            campaign_query = "select max(campaign) from ops_epoch_inputs where name='{epoch}'".format(epoch=epoch)
            self.cur.execute(campaign_query)
            campaign = self.cur.fetchall()[0][0]
        query = "select * from ops_epoch_inputs where name='{epoch}'  \
                 and campaign = '{c}'".format(epoch=epoch,c=campaign)
        self.cur.execute(query) 
        data = pd.DataFrame(self.cur.fetchall(),
               columns=['name','filetype','reqnum','unitname','attnum','uband','campaign','filename',
                        'filepat','ccdnum'])
       
        if band in ['u','VR']:
            cals = data[(data.uband == 1)]
            cals = cals.append(data[data.filetype=='cal_lintable']) 
            cals = cals.append(data[(data.filetype=='config')])
            cals = cals.append(data[(data.filetype=='None')])
            cals = cals.append(data[(data.filetype=='cal_bf')])
        else:
            cals = data[(data.uband.isnull())]
        return cals     
    
    def get_expnums_from_tag(self,tag):
        """ Query database for each exposure with a given exposure tag.
        Returns a list of expnums."""
        taglist = tag.split(',')
        tag_list_of_dict = []
        for t in taglist:
            expnum_query = "select distinct expnum from exposuretag where tag='%s'" % t
            self.cur.execute(expnum_query)
            results = self.cur.fetchall()
            expnum_list = [exp[0] for exp in results]
            for e in expnum_list:
                tag_dict = {}
                tag_dict['expnum'] = e
                tag_dict['tag'] = t
                tag_list_of_dict.append(tag_dict)
        return tag_list_of_dict

    def get_propids_programs(self):
        """ get the accepted propids and programs """
        get_all_propid = "select distinct propid from OPS_PROPID" 
        self.cur.execute(get_all_propid)
        propid = self.cur.fetchall()
        propid = [i[0] for i in propid]
        get_all_program = "select distinct program from OPS_PROPID"
        self.cur.execute(get_all_program)
        program = self.cur.fetchall()
        program = [i[0] for i in program]
        return propid,program


    def insert_auto_queue(self,n=3,nites=None,process_all=False,program=None,propid=None):
        """ Get exposures into auto_queue for auto processing"""
        if not nites:
            now = datetime.now()
            nites = [now.strftime('%Y%m%d')]
            for i in range(1,n+1):
                date = now - timedelta(i)
                nites.append(date.strftime('%Y%m%d'))
            print "%s: Inserting into AUTO_QUEUE." % now
        base_query = "select distinct expnum from exposure where obstype in ('object','standard') and \
                      object not like '%%pointing%%' and object not like '%%focus%%' and object \
                      not like '%%donut%%' and object not like '%%test%%' and object \
                      not like '%%junk%%' and nite in (%s)" % ','.join(nites)
        if process_all:
            base_query = base_query
        else:
            if program:
                base_query = base_query + " and program in (%s)" % ','.join("'{0}'".format(k) for k in program)
            if propid:
                base_query = base_query + " and propid in (%s)" % ','.join("'{0}'".format(k) for k in propid)
        self.cur.execute(base_query)
        results = [row[0] for row in self.cur.fetchall()]
        if results:
            inserts = []
            for expnum in results:
                try:
                    insert_query = "insert into ops_auto_queue (expnum,created,processed) values ({expnum},CURRENT_TIMESTAMP, 0)".format(expnum=expnum)
                    self.cur.execute(insert_query)
                    inserts.append(expnum)
                except: pass
            self.dbh.commit()
            print '%s exposures inserted.' % len(inserts)
        else:
            print 'No new exposures to insert.'

    def update_auto_queue(self,n_failed=3):
        print '%s: Updating AUTO_QUEUE.' % datetime.now()
        query = "select distinct expnum from ops_auto_queue where processed=0 order by expnum"
        unitnames = ['D00'+ str(e[0]) for e in self.cur.execute(query)]
      
        submitted = "select distinct unitname,attnum,status from pfw_attempt a, task t,pfw_request r where r.reqnum=a.reqnum and t.id=a.task_id and r.project='OPS' and unitname in ('%s')" % ("','".join(unitnames))
        self.cur.execute(submitted)
        failed_query = self.cur.fetchall()
        try:
            df = pd.DataFrame(failed_query,columns=['unitname','attnum','status'])
        except:
            df = pd.DataFrame(columns=['unitname','attnum','status'])
        # Set Null values to -99
        df = df.fillna(-99)

        success_list = []
        fail_list = []
        for u in df['unitname'].unique():
            statuses = list(df[(df.unitname == u)]['status'].values)
            failed_atts = [i for i in statuses if i >=1]
            if 0 in statuses:
                success_list.append(u)
            if 0 not in statuses and -99 not in statuses and len(failed_atts) >= n_failed:
                fail_list.append(u)
        success_exposures = [u.split('D00')[1] for u in success_list]
        fail_exposures = [u.split('D00')[1] for u in fail_list]
        
        if success_exposures:
            update_query = "update ops_auto_queue set processed=1,updated=CURRENT_TIMESTAMP where expnum in ({expnums})".format(expnums=','.join(success_exposures))
            self.cur.execute(update_query)
            self.dbh.commit()
        if fail_exposures:
            update_query = "update ops_auto_queue set processed=2,updated=CURRENT_TIMESTAMP where expnum in ({expnums})".format(expnums=','.join(fail_exposures))
            self.cur.execute(update_query)
            self.dbh.commit()
        if not success_exposures and not fail_exposures:
            print 'No new exposures to update.'
        else:
            print 'Updated %s exposures as processed.' % (len(success_exposures)+len(fail_exposures))

class SuperNova(PipeQuery):
# Copied from widefield (unedited)
    def get_expnum_info(self,exposure_list):
        """ Query database for band and nite for each given exposure.
            Returns a list of dictionaries."""
        for exp in exposure_list:
            expnum_info = "select distinct expnum, band, nite from exposure where expnum='%s'" % exp
            self.cur.execute(expnum_info)
            results = self.cur.fetchall()[0]
            yield results

# Edited from widefield (takes in nite, field and band and yield expnums)
    def update_df(self,df):
        """ Takes a pandas dataframe and for each exposure add column:value
            band and nite. Returns dataframe"""
        for index,row in df.iterrows():
            expnums=self.get_expnums(row['nite'],row['field'],row['band'])
            df.loc[index,'expnums'] = expnums
            print expnums
            firstexp = expnums.split(',')[0]
            df.loc[index,'firstexp'] = firstexp
            df.loc[index,'ccdnum'] = '1,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,62'
            df.loc[index,'seqnum'] = 1
            if (row['field'][-2:] in ['C3','X3']) or (row['band'] == 'z'):
              df.loc[index,'single']= False
            if (row['band'] in ['z','Y']):
              df.loc[index,'fringe']= True
            df.loc[index,'unitname']='D_SN-'+row['field'][-2:]+'_'+row['band']+'_s1'
        return df

# Edited from widefield (changed expnum to unitname)
    def check_submitted(self,unitname,reqnum):
        """ Queries database to find number of attempts submitted for
            given exposure. Returns count"""
        was_submitted = "select count(*) from pfw_attempt where unitname= '%s' and reqnum = '%s'" % (unitname,reqnum)
        self.cur.execute(was_submitted)
        submitted_or_not = self.cur.fetchone()[0]
        return submitted_or_not       
    
# Edited from widefield
    def get_max_nite(self,ignore_propid=False,ignore_program=False,ignore_all=False,**kwargs):
        """Returns expnum,nite of max(expnum) in the exposure table"""
        query = "select max(nite) from manifest_exposure where exptime > 30"
        self.cur.execute(query)
        return self.cur.fetchone()[0]

# Edited from widefield
    def get_failed_triplets(self,nitelist,resubmit_max):
        """ Queries database to find number of failed attempts without success.
            Returns expnums for failed, non-null, nonzero attempts."""
        submitted = "select distinct s.nite, s.field, s.band, p.unitname, p.attnum, t.status from pfw_attempt p, task t, snsubmit s where t.id=p.task_id and s.nite in (%s) and p.task_id = s.task_id  and p.unitname like 'D_SN-%%'" % (','.join(map(str,nitelist)))
        print submitted
        self.cur.execute(submitted)
        failed_query = self.cur.fetchall()
        df = pd.DataFrame(failed_query,columns=['nite','field','band','unitname','attnum','status'])
        # Set Null values to -99
        df = df.fillna(-99)
        passed_unitnames = []
        for u in df['unitname'].unique():
            nattempts = df[(df.unitname==u)].count()[0]
            count = df[(df.unitname==u) & (df.status==0)].count()[0]
            print str(u)+' has '+str(count)+' good processings. '+str(nattempts)+' total processings. Max is '+str(resubmit_max)
            if (count >= 1) or (nattempts >= int(resubmit_max)):
                passed_unitnames.append(u)
        try:
            failed_list = df[(~df.unitname.isin(passed_unitnames)) & (~df.status.isin([0,-99]))][['nite','field','band']]
        except:
            print 'No new failed exposures found!'
            exit()
        try: 
            print failed_list
            resubmit_list = (failed_list.drop_duplicates(subset=['nite','field','band'])).values
            print resubmit_list
        except:
            print 'No new failed exposures found!'
            exit()
 #       print 'get_failed_triplets disabled'
 #       exit()
        return resubmit_list

# SN only code
    def get_triplets_from_nite(self,nite=None,**kwargs):
        """ Get exposure numbers and band for a SN nite field band triplet"""
        if not nite:
            raise Exception("Must specify nite!")
        print "selecting exposures to submit..."
        query = "select distinct nite, field, band from manifest_exposure where exptime > 30 \
                and nite in (%s) " % (','.join(nite))
        print query
        self.cur.execute(query)
#        triplets = np.ravel(np.array(self.cur.fetchall()))
#        return string.join(map(str,triplets),',').reshape[-1:3]
        return np.array(self.cur.fetchall())

    

# Edited from widefield (requires SN triplet)
    def get_expnums(self,nite=None,field=None,band=None,**kwargs):
        snfields=['C1','C2','C3','E1','E2','S1','S2','X1','X2','X3']
        bands=['u','g','r','i','z','Y']
        """ Get exposure numbers and band for a SN nite field band triplet"""
        if not nite:
            raise Exception("Must specify nite!")
        if not field[-2:] in snfields:
            raise Exception("Must specify field!")
        if not band:
            raise Exception("Must specify nite!")
        print "selecting exposures to submit..."
        query = "select distinct expnum from manifest_exposure where exptime > 30  and nite = '%s' and field = 'SN-%s' and band = '%s' " % (str(nite), field[-2:], band)
        self.cur.execute(query)
        exps = np.ravel(np.array(self.cur.fetchall()))
        return string.join(map(str,exps),',')

# Copied from widefield (unedited)
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

class MultiEpoch(PipeQuery):
    

    def check_proctag(self,tag):
        """ Check to see if specified processing tag exists in PROCTAG table"""
        query = "select count(*) from proctag where tag = '{tag}'".format(tag=tag)
        self.cur.execute(query)
        count = self.cur.fetchone()[0]
        return count

    def update_df(self,df):
        """ Takes a pandas dataframe and for each exposure add column:value
        band and nite. Returns dataframe"""
        try:
            df.insert(len(df.columns), 'unitname', None)
        except:
            pass
        for index, row in df.iterrows():
            df.loc[index, 'unitname'] =  str(row['tile'])

        return df


    def check_submitted(self, tile, reqnum):
        """ Queries database to find number of attempts submitted for
            given exposure. Returns count"""
        was_submitted = "select count(*) from pfw_attempt where unitname= '%s' and reqnum = %s" % (tile,reqnum)
        self.cur.execute(was_submitted)
        submitted_or_not = self.cur.fetchone()[0]
        return submitted_or_not

    def get_tiles_from_radec(self,RA, Dec,radius=None):
        RA = [float(r) for r in RA[0]]
        Dec = [float(d) for d in Dec[0]]
        if RA[0]==min(RA):
            query = "select tilename from coadd where RA_CENT >{minRA} and RA_CENT <{maxRA} and DEC_CENT >{minDec} and DEC_CENT <{maxDec}".format(minRA=RA[0], maxRA=RA[1], minDec=min(Dec), maxDec=max(Dec))
        else:
            query = "select tilename from coadd where (RA_CENT>{minRA} or RA_CENT<{maxRA}) and DEC_CENT>{minDec} and DEC_CENT<{maxDec}".format(minRA=RA[0], maxRA=RA[1], minDec=min(Dec), maxDec=max(Dec))
        self.cur.execute(query)
        return self.cur.fetchall() 

    def get_failed_tiles(self, reqnum,resubmit_max):
        """ Queries database to find number of failed attempts without success.
            Returns expnums for failed, non-null, nonzero attempts."""
        submitted = "select distinct unitname,attnum,status from pfw_attempt p, task t where t.id=p.task_id and reqnum = '%s'" % (reqnum)
        self.cur.execute(submitted)
        failed_query = self.cur.fetchall()
        df = pd.DataFrame(failed_query,columns=['unitname','attnum','status'])
        # Set Null values to -99
        df = df.fillna(-99)

        resubmit_list = []

        for u in df['unitname'].unique():
            count = df[(df.unitname == u) & (df.status == 0)].count()[0]
            statuses = list(df[(df.unitname == u)]['status'].values)
            if -99 in statuses or 0 in statuses:
                pass
            else:
                if (len(statuses) <= int(resubmit_max)):
                    resubmit_list.append(u)
        tile_list = [u for u in resubmit_list]

        return tile_list

    def get_tiles_from_tag(self,tag):
        pass

    
class WideField(PipeQuery):
  
    def count_by_obstype(self,niteslist):
        """  return count per obstype, band """
        count_query="select obstype,band,count(expnum) from exposure where nite in ({nites}) and obstype not in ('dome flat', 'zero','dark') group by obstype,band".format(nites=','.join(niteslist))
        self.cur.execute(count_query)
        count_info = self.cur.fetchall()
        print " Obstype         Band      Count"
        for row in count_info:
            print "%09s  %09s  %09s" % (row[0], row[1], row[2])
    def get_expnums_from_radec(self, RA, Dec,radius=None):
        RA = [float(r) for r in RA[0]]
        Dec = [float(d) for d in Dec[0]]
        if RA[0]==min(RA):
            query = "select expnum from exposure where radeg>{minRA} and radeg<{maxRA} and decdeg>{minDec} and decdeg<{maxDec}".format(minRA=RA[0], maxRA=RA[1], minDec=min(Dec), maxDec=max(Dec))
        else:
            query = "select expnum from exposure where (radeg>{minRA} or radeg<{maxRA}) and decdeg>{minDec} and decdeg<{maxDec}".format(minRA=RA[0], maxRA=RA[1], minDec=min(Dec), maxDec=max(Dec))
        self.cur.execute(query)
        return self.cur.fetchall()

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
            expnum_info = "select distinct expnum, band, nite, obstype from exposure where expnum='%s'" % row['expnum']
            self.cur.execute(expnum_info)
            expnum,band,nite,obstype = self.cur.fetchall()[0]
            try:
                df.insert(len(df.columns),'nite', None)
                df.insert(len(df.columns),'band', None)
                df.insert(len(df.columns),'unitname',None)
                df.insert(len(df.columns),'obstype',None)
            except:
                pass
            df.loc[index,'nite'] = nite
            df.loc[index,'band'] = band
            df.loc[index,'unitname'] = 'D00' + str(expnum)
            df.loc[index,'obstype'] = obstype
        return df

    def check_submitted(self,unitname,reqnum):
        """ Queries database to find number of attempts submitted for
            given exposure. Returns count"""
        was_submitted = "select count(*) from pfw_attempt where unitname= '%s' and reqnum = '%s'" % (unitname,reqnum)
        self.cur.execute(was_submitted)
        submitted_or_not = self.cur.fetchone()[0]
        return submitted_or_not       
    
    def get_max_nite(self,propid=None,program=None,process_all=False):
        """Returns expnum,nite of max(expnum) in the exposure table"""
        base_query = "select max(expnum) from exposure where obstype in ('object','standard')"
        if process_all:
            base_query = base_query
        else:
            if propid:
                base_query = base_query + " and propid in (%s)" % ','.join("'{0}'".format(k) for k in propid)
            if program:
                base_query = base_query + " and program in (%s)" % ','.join("'{0}'".format(k) for k in program)
        self.cur.execute(base_query)
        max_expnum = self.cur.fetchone()[0]
        fetch_nite = "select distinct nite from exposure where expnum=%s" % (max_expnum)
        self.cur.execute(fetch_nite)
        object_nite = self.cur.fetchone()[0]
        return max_expnum,object_nite

    def get_failed_expnums(self,reqnum,resubmit_max):
        """ Queries database to find number of failed attempts without success.
            Returns expnums for failed, non-null, nonzero attempts."""
        submitted = "select distinct unitname,attnum,status from pfw_attempt p, task t where t.id=p.task_id and reqnum = '%s'" % (reqnum)
        self.cur.execute(submitted)
        failed_query = self.cur.fetchall()
        df = pd.DataFrame(failed_query,columns=['unitname','attnum','status'])
        # Set Null values to -99
        df = df.fillna(-99)

        resubmit_list = []
        for u in df['unitname'].unique():
            count = df[(df.unitname == u) & (df.status == 0)].count()[0]
            statuses = list(df[(df.unitname == u)]['status'].values)
            if -99 in statuses or 0 in statuses:
                pass
            else:
                if (len(statuses) <= int(resubmit_max)):
                    resubmit_list.append(u)

        expnum_list = [u[3:] for u in resubmit_list]
        
        return expnum_list

    def get_expnums_from_auto_queue(self,n_failed=3):
        query = "select distinct expnum from ops_auto_queue where processed=0"
        self.cur.execute(query)
        exposures = [exp[0] for exp in self.cur.fetchall()]
        unitnames = ['D00'+str(e) for e in exposures]

        submitted = "select distinct unitname,attnum,status from pfw_attempt a, task t,pfw_request r where r.reqnum=a.reqnum and t.id=a.task_id and r.project='OPS' and unitname in ('%s')" % ("','".join(unitnames))
        self.cur.execute(submitted)
        failed_query = self.cur.fetchall()
        try:
            df = pd.DataFrame(failed_query,columns=['unitname','attnum','status'])
        except:
            df = pd.DataFrame(unitnames,columns=['unitname'])
            df['status'] = -1 
        # Set Null values to -99
        df = df.fillna(-99)

        null_list = []
        for u in df['unitname'].unique():
            count = df[(df.unitname == u) & (df.status == 0)].count()[0]
            statuses = list(df[(df.unitname == u)]['status'].values)
            failed_atts = [i for i in statuses if i >=1]
            # remove from list any exposures that are currently running or successful
            if -99 in statuses or 0 in statuses:
                null_list.append(u)
            # remove from list any exposures that have failed at least 3 times
            else:
                if len(failed_atts) >= n_failed:
                    null_list.append(u)
        final_unitnames_set = set(unitnames)-set(null_list)
        final_exposures = [u.split('D00')[1] for u in final_unitnames_set]
        return final_exposures

    def get_expnums_from_nites(self,nites=None,process_all=False,program=None,propid=None):
        """ Get exposure numbers and band for incoming exposures"""
        if not nites:
            raise Exception("Must specify nite!")
        print "selecting exposures to submit..."
        base_query = "select distinct expnum,nite from exposure where obstype in ('object','standard') and \
                      object not like '%%pointing%%' and object not like '%%focus%%' and object not like '%%donut%%' \
                      and object not like '%%test%%' and object not like '%%junk%%' and nite in (%s)" % ','.join(nites)
        if process_all:
            base_query = base_query
        else:
            if program:
                base_query = base_query + " and program in (%s)" % ','.join("'{0}'".format(k) for k in program)
            if propid:
                base_query = base_query + " and propid in (%s)" % ','.join("'{0}'".format(k) for k in propid)
        self.cur.execute(base_query)
        results = self.cur.fetchall()
        try:
            [expnums,nites_from_query] = map(list, zip(*results))
        except:
            print "Warning: No expnums found for nites {}.".format(','.join(nites))
            exit(0)
        diff = list(set(nites)-set(nites_from_query))
        diff.sort(key=str.lower)
        if diff:
            print "Warning: No expnums found for nites {}.".format(','.join(diff))    
        return expnums

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

class NitelyCal(PipeQuery):

    def get_nites(self,expnum_list):
        explist = ','.join(str(n) for n in expnum_list)
        nite_query = "select distinct nite from exposure where expnum in ({explist}) \
                     order by nite".format(explist=explist)
        self.cur.execute(nite_query)

        return [n[0] for n in self.cur.fetchall()]

    def check_submitted(self,date,reqnum):
        """Check to see if a nitelycal has been submitted with given date"""
        was_submitted = "select count(*) from pfw_attempt where unitname= '%s' and reqnum = '%s'" % (date,reqnum)
        self.cur.execute(was_submitted)
        count = self.cur.fetchone()[0]
        return count

    def get_max_nite(self):
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
            try:
                is_unitname = row['unitname']
                if is_unitname is None:
                    df.loc[index, 'unitname'] = nite
            except:
                df.loc[index,'unitname'] = nite

        return df

class PreBPM(PipeQuery):

    def update_df(self,df):
        """ Takes a pandas dataframe and for each exposure add column:value
            band and nite. Returns dataframe"""
        for index,row in df.iterrows():
            expnum_info = "select distinct expnum, band, nite from exposure where expnum='%s'" % row['expnum']
            self.cur.execute(expnum_info)
            expnum,band,nite = self.cur.fetchall()[0]
            try:
                df.insert(len(df.columns),'nite', None)
                df.insert(len(df.columns),'band', None)
                df.insert(len(df.columns),'unitname', None)
            except:
                pass

            df.loc[index,'nite'] = nite
            df.loc[index,'band'] = band
            df.loc[index,'unitname'] = 'D00{expnum}'.format(expnum=expnum)

        return df

    def get_failed_expnums(self,reqnum,resubmit_max):
        """ Queries database to find number of failed attempts without success.
            Returns expnums for failed, non-null, nonzero attempts."""
        submitted = "select distinct unitname,attnum,status from pfw_attempt p, task t where t.id=p.task_id and reqnum = '%s'" % (reqnum)
        self.cur.execute(submitted)
        failed_query = self.cur.fetchall()
        df = pd.DataFrame(failed_query,columns=['unitname','attnum','status'])
        # Set Null values to -99
        df = df.fillna(-99)

        resubmit_list = []
        for u in df['unitname'].unique():
            count = df[(df.unitname == u) & (df.status == 0)].count()[0]
            statuses = list(df[(df.unitname == u)]['status'].values)
            if -99 in statuses or 0 in statuses:
                pass
            else:
                if (len(statuses) <= int(resubmit_max)):
                    resubmit_list.append(u)
        expnum_list = [u[3:] for u in resubmit_list]
        
        return expnum_list

    def get_expnums_from_tag(self,tag):
        """ Query database for each exposure with a given exposure tag.
        Returns a list of expnums."""
        taglist = tag.split(',')
        tag_list_of_dict = []
        for t in taglist:
            expnum_query = "select distinct expnum from exposuretag where tag='%s'" % t
            self.cur.execute(expnum_query)
            results = self.cur.fetchall()
            expnum_list = [exp[0] for exp in results]
            for e in expnum_list:
                tag_dict = {}
                tag_dict['expnum'] = e
                tag_dict['tag'] = t
                tag_list_of_dict.append(tag_dict)
        return tag_list_of_dict

class PhotoZ(PipeQuery):

    def get_failed_chunks(self, reqnum,resubmit_max):
        """ Queries database to find number of failed attempts without success.
            Returns expnums for failed, non-null, nonzero attempts."""
        submitted = "select distinct unitname,attnum,status from pfw_attempt p, task t where t.id=p.task_id and reqnum = '%s'" % (reqnum)
        self.cur.execute(submitted)
        failed_query = self.cur.fetchall()
        df = pd.DataFrame(failed_query,columns=['unitname','attnum','status'])
        # Set Null values to -99
        df = df.fillna(-99)

        resubmit_list = []

        for u in df['unitname'].unique():
            count = df[(df.unitname == u) & (df.status == 0)].count()[0]
            statuses = list(df[(df.unitname == u)]['status'].values)
            if -99 in statuses or 0 in statuses:
                pass
            else:
                if (len(statuses) <= int(resubmit_max)):
                    resubmit_list.append(u)
        chunk_list = [u for u in resubmit_list]

        return chunk_list

    def check_proctag(self,tag):
        """ Check to see if specified processing tag exists in PROCTAG table"""
        query = "select count(*) from proctag where tag = '{tag}'".format(tag=tag)
        self.cur.execute(query)
        count = self.cur.fetchone()[0]
        return count

    def update_df(self,df):
        """ Takes a pandas dataframe and for each exposure add column:value
        band and nite. Returns dataframe"""
        try:
            df.insert(len(df.columns), 'unitname', None)
        except:
            pass
        for index, row in df.iterrows():
            df.loc[index, 'unitname'] =  str(row['campaign']) + '_' + str(row['chunk'])
        return df

    def check_submitted(self, unitname, reqnum):
        """ Queries database to find number of attempts submitted for
            given exposure. Returns count"""
        was_submitted = "select count(*) from pfw_attempt where unitname= '%s' and reqnum = %s" % (unitname,reqnum)
        self.cur.execute(was_submitted)
        submitted_or_not = self.cur.fetchone()[0]
        return submitted_or_not

    def get_failed_chunks(self, reqnum,resubmit_max):
        """ Queries database to find number of failed attempts without success.
            Returns expnums for failed, non-null, nonzero attempts."""
        submitted = "select distinct unitname,attnum,status from pfw_attempt p, task t where t.id=p.task_id and reqnum = '%s'" % (reqnum)
        self.cur.execute(submitted)
        failed_query = self.cur.fetchall()
        df = pd.DataFrame(failed_query,columns=['unitname','attnum','status'])
        # Set Null values to -99
        df = df.fillna(-99)

        resubmit_list = []

        for u in df['unitname'].unique():
            count = df[(df.unitname == u) & (df.status == 0)].count()[0]
            statuses = list(df[(df.unitname == u)]['status'].values)
            if -99 in statuses or 0 in statuses:
                pass
            else:
                if (len(statuses) <= int(resubmit_max)):
                    resubmit_list.append(u)
        chunk_list = [u for u in resubmit_list]

        return chunk_list

