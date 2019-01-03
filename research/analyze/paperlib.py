from database import Database
from tqdm import *
from forpaper import *
import collections
from paperlib_helper import *
from paperlib_helper import Paperlib_helper

class Paperlib():

    def __init__(self, db):
        self.db = db
        self.feature_list = get_fingerprint_feature_list()
        self.major_table_list = get_fingerprint_feature_list_include_gpuimgs()
        self.group_features = {
                'headers_features' : [0, 1, 2, 3, 4, 5],
                'browser_features' : [6, 7, 8, 9, 10, 11],
                'os_features' : [12, 13, 14],
                #add gpuimgs or not
                'hardware_feature' : [15, 16, 18, 19, 20, 21, 22, 23],
                'ip_features': [24, 25, 26],
                'consistency' : [27, 28, 29, 30]
                }
        self.paperlib_helper = Paperlib_helper()

    def life_time_median(self, db = None, filter_less_than = 3, output_file = './res/life_time_median.dat'):
        """
        calculate the median life time of each feature
        output to output_file
        """
        if db == None:
            db = self.db
        feature_list = self.feature_list
        df = db.load_data(table_name = 'pandas_features')
        df = filter_less_than_n(df, filter_less_than)

        grouped = df.groupby('browserid')
        min_date = min(df['time'])
        max_date = max(df['time'])
        length = (max_date - min_date).days + 3
        life_time = {}
        for feature in feature_list:
            life_time[feature] = [0 for i in range(length + 10)]

        for browserid, cur_group in tqdm(grouped):
            # cur_group is the df of this group
            pre_feature = {}
            pre_time = {}
            changed = {}
            for idx, row in cur_group.iterrows():
                for feature in feature_list:
                    if feature in pre_feature:
                        if pre_feature[feature] != row[feature]:
                            cur_delt = (row['time'] - pre_time[feature]).days
                            life_time[feature][cur_delt] += 1
                            pre_feature[feature] = row[feature]
                            pre_time[feature] = row['time']
                            changed[feature] = True
                    else:
                        pre_feature[feature] = row[feature]
                        pre_time[feature] = row['time']
                        changed[feature] = False 

            # if not changed, we assume the life time is maxmium till the 
            # end date of our database
            for feature in feature_list:
                if not changed[feature]:
                    life_time[feature][(max_date - pre_time[feature]).days] += 1

        medians = {}
        for feature in tqdm(feature_list):
            cur = 0
            total_change = sum(life_time[feature])
            half = total_change / 2
            for i in range(length + 1):
                cur += life_time[feature][i]
                if cur > half:
                    medians[feature] = i + 1
                    break

        
        f = safeopen(output_file, 'w')
        for feature in medians:
            f.write(feature + ' ' + str(medians[feature]))
            f.write('\n')
        f.close()

    def feature_latex_table(self, feature_list, df, output_file = './res/feature_table_1.dat'):
        """
        new version of generate table 1, with changes 
        """
        print feature_list
        print len(feature_list)
        distinct = {}
        unique = {}
        stability = {}

        # generate normal feature first
        print ('generating normal features')
        for feature in tqdm(feature_list):
            unique[feature] = 0
            distinct[feature] = 0

            grouped = df.groupby(feature)
            for key, cur_group in grouped:
                if key.find(self.db.filler) != -1 or key == '':
                    continue
                distinct[feature] += 1
                # feature based on label
                # changes based on browserid
                if cur_group['browserid'].nunique() == 1:
                    unique[feature] += 1

        print ('generating grouped features')
        for feature_group in tqdm(self.group_features):
            grouped = df.groupby([self.major_table_list[x] for x in self.group_features[feature_group]])
            unique[feature_group] = 0
            distinct[feature_group] = 0

            for key, cur_group in grouped:
                if str(key).find(self.db.filler) != -1:
                    continue
                # output for consistant values
                if feature_group == 'consistency' : 
                    print key
                distinct[feature_group] += 1
                if cur_group['browserid'].nunique() == 1:
                    unique[feature_group] += 1

        
        print ('generating stability')
        for feature in feature_list:
            stability[feature] = 0

        grouped = df.groupby('label')
        update_mark = {}
        revert_group_idx = {}
        for group_name in self.group_features:
            stability[group_name] = 0

        for feature in self.group_features:
            update_mark[feature] = True
            for idx in self.group_features[feature]:
                revert_group_idx[feature_list[idx]] = feature 

        total_user_num = 0
        for key, cur_group in tqdm(grouped):
            total_user_num += 1
            for feature in feature_list:
                if cur_group[feature].nunique() == 1:
                    stability[feature] += 1
                elif feature in revert_group_idx:
                    update_mark[revert_group_idx[feature]] = False

            for group_name in self.group_features:
                if update_mark[group_name]:
                    stability[group_name] += 1
                update_mark[group_name] = True

        for feature in stability:
            stability[feature] = float(stability[feature]) / float(total_user_num)

        print ("start to output")
        final_list = feature_list + [k for k in self.group_features]
        f = safeopen(output_file, 'w')
        for feature in final_list:
            f.write(r'{} & {} & {} & {:.4f} \\'.format(feature, distinct[feature], 
                    # change round to floor
                    unique[feature], float(int(stability[feature] * 10000)) / 10000))
            #f.write(r'{} & {} & {} \\'.format(feature, distinct[feature],unique[feature]) )
            f.write('\n')
        f.close()

    def feature_latex_table_paper(self, output_file = './res/feature_table_1.dat'):
        """
        generate table 1, which is used for all feature description
        """
        df = self.db.load_data(table_name = 'pandas_features')
        # assign to the class at the same time
        #self.pdfeatures = df
        value_set = {}
        browser_instance = {}
        feature_list = self.feature_list
        group_features = self.group_features

        group_map = ['' for i in range(29)]
        for key in group_features:
            for i in group_features[key]:
                group_map[i] = key

        num_back = 0;
        browser_id_group = df.groupby('browserid').size()
        browser_id_group = browser_id_group.reset_index(name='counts')
        back_users = set()
        for idx in browser_id_group.index:
            if browser_id_group.at[idx, 'counts'] > 1:
                num_back += 1
                back_users.add(browser_id_group.at[idx, 'browserid'])
        print 'num_back:', num_back
        print 'num_size:', len(back_users)
        df = df.reset_index(drop = True)

        for idx in tqdm(df.index):
            row = df.iloc[idx]
            if row['browserid'] not in browser_instance:
                browser_instance[row['browserid']] = {} 
            group_vals = {}
            for i in range(len(feature_list)):
                feature = feature_list[i]
                # get ride of gpuimgs
                if feature == 'gpuimgs':
                    continue
                group_key = group_map[i]
                cur_feature = row[feature]
                # some times ture and True is different
                # unknown reason, just put a patch here
                # the reason is known, because of the update of 
                # adding value of lied value, fixed in clean_sql, patch not needed
                """
                if cur_feature == 'true':
                    cur_feature = 'True'
                elif cur_feature == 'false':
                    cur_feature = 'False'
                """

                if group_key not in group_vals:
                    group_vals[group_key] = ""
                group_vals[group_key] += str(cur_feature)
                
                if feature not in value_set:
                    value_set[feature] = {}
                if cur_feature not in value_set[feature]:
                    value_set[feature][cur_feature] = set()
                value_set[feature][cur_feature].add(row['browserid'])

                if feature not in browser_instance[row['browserid']]:
                    browser_instance[row['browserid']][feature] = set()
                browser_instance[row['browserid']][feature].add(cur_feature)

            for group_key in group_vals:
                if group_key not in value_set:
                    value_set[group_key] = {}
                if group_vals[group_key] not in value_set[group_key]:
                    value_set[group_key][group_vals[group_key]] = set()
                value_set[group_key][group_vals[group_key]].add(row['browserid'])
                
                if group_key not in browser_instance[row['browserid']]:
                    browser_instance[row['browserid']][group_key] = set()
                browser_instance[row['browserid']][group_key].add(group_vals[group_key])

        distinct = {}
        unique = {}
        per_browser_instance = {}
        f = open(output_file, 'w')
        for feature in value_set:
            distinct[feature] = len(value_set[feature])
            cnt = 0
            for val in value_set[feature]:
                if len(value_set[feature][val]) == 1:
                    cnt += 1
            unique[feature] = cnt

            for bid in browser_instance:
                if feature not in per_browser_instance:
                    per_browser_instance[feature] = 0
                if len(browser_instance[bid][feature]) == 1 and bid in back_users:
                    per_browser_instance[feature] += 1
            per_browser_instance[feature] = float(per_browser_instance[feature]) / float(num_back)
            f.write(r'{} & {} & {} & {:.4f} \\'.format(feature, distinct[feature], unique[feature], per_browser_instance[feature]))
            f.write('\n')
        f.close()

    def verify_browserid_by_cookie(self):
        """
        this function will return the lower, upper bound of browserid accuracy and the total number
        the upper bound is the percentage of browserids with more than one cookies
        the lower bound is the percentage of browserids with fliped cookies
        """
        browserid = 'browserid'
        db = self.db
        df = db.load_data(feature_list = [browserid, 'label', 'os', 'browser'], table_name = 'pandas_features')

        #we can add filter here
        df = filter_less_than_n(df, 3)

        #here we can filter the unrelated os
        #df = filter_df(df, 'os', filtered_list = ['iOS', 'Mac OS X'])
        df = keep_df(df, 'browser', keep_list = ['Chrome Mobile iOS'])

        """
        filtered_list = [
                'safari'
                ]
        df = df[~df['browser'].isin(filtered_list)]
        """

        grouped = df.groupby(browserid)
        lower_wrong_browserid = []
        upper_wrong_browserid = []
        total_number = df[browserid].nunique()

        for key, cur_group in tqdm(grouped):
            appeared = set()
            pre_cookie = ""
            if cur_group['label'].nunique() > 1:
                upper_wrong_browserid.append(key)
            for idx, row in cur_group.iterrows():
                if pre_cookie != row['label']:
                    pre_cookie = row['label']
                    if row['label'] in appeared:
                        lower_wrong_browserid.append(row[browserid])
                        break
                    appeared.add(row['label'])
        return lower_wrong_browserid, upper_wrong_browserid, total_number

    def new_return_user_by_date(self, percentage = False):
        """
        return the number of returned users and new users in each day
        the result will be written into newVsReturn
        if the percentage key is set to True
        the function will return the percentage instead of the real number
        """
        df = self.db.load_data(feature_list = ['browserid', 'time'], table_name = 'pandas_features')
        df = round_time_to_day(df)
        df = df.drop_duplicates(subset = ['time', 'browserid'])
        grouped = df.groupby('browserid')
        min_date = min(df['time'])
        max_date = max(df['time'])
        lendate = (max_date - min_date).days
        datelist = [min_date + datetime.timedelta(days = i) for i in range(lendate + 3)]
        # round time to day
        return_user = {}
        new_user = {} 
        for date in datelist:
            return_user[date] = 0
            new_user[date] = 0

        #here we already removed the multiple visites for same user in same day
        for key, group in tqdm(grouped):
            first = True
            for idx, row in group.iterrows():
                if first:
                    first = False
                    new_user[row['time']] += 1
                else:
                    return_user[row['time']] += 1

        if percentage:
            for date in datelist:
                cur_total = new_user[date] + return_user[date]
                # avoid divide by zero
                if cur_total == 0:
                    cur_total = 1
                new_user[date] = float(new_user[date]) / float(cur_total)
                return_user[date] = float(return_user[date]) / float(cur_total)

        f = safeopen('./res/newVsReturn.dat', 'w')
        f.write('{} {}\n'.format('new-user', 'return-user'))
        for date in datelist:
            f.write('{}-{}-{} {} {}\n'.format(date.year, date.month, date.day, new_user[date], return_user[date]))
        f.close()

    def feature_distribution_by_date(self, feature_name, percentage = False, show_number = 7):
        """
        draw total number of a feature by date
        this function will return a stacked dat file
        """
        db = self.db
        df = db.load_data(feature_list = ['time', 'browserid', 'browserversion', feature_name], table_name = 'pandas_features', limit = 10000)
        min_date = min(df['time'])
        min_date = min_date.replace(microsecond = 0, second = 0, minute = 0, hour = 0)
        max_date = max(df['time'])
        lendate = (max_date - min_date).days
        datelist = [min_date + datetime.timedelta(days = i) for i in range(lendate + 3)]
        # round time to day
        df = round_time_to_day(df)
        df = df.drop_duplicates(subset = [feature_name, 'time', 'browserid'])
        grouped = df.groupby([feature_name, 'time'])
        res = {}
        total_numbers = {}
        daily_all_numbers = {}
        for date in datelist:
            res[date] = {}
            daily_all_numbers[date] = 0

        for key, group in tqdm(grouped):
            cur_number = group['browserid'].nunique()

            daily_all_numbers[key[1]] += cur_number
            if key[0] not in res[key[1]]:
                res[key[1]][key[0]] = 0
            res[key[1]][key[0]] += cur_number

            if key[0] not in total_numbers:
                total_numbers[key[0]] = 0
            total_numbers[key[0]] += cur_number


        f = safeopen('./res/featureNumberByDate/{}.dat'.format(feature_name), 'w')
        total_numbers = sorted(total_numbers.iteritems(), key=lambda (k,v): (-v,k))
        total_numbers = total_numbers[:show_number]
        # print feature names
        for val in total_numbers:
            f.write('{} '.format(val[0]))
        f.write('others\n')

        if percentage:
            for date in datelist:
                for feature in res[date]:
                    # avoid divide by zero
                    if daily_all_numbers[date] == 0:
                        daily_all_numbers[date] = 1
                    res[date][feature] = float(res[date][feature]) / float(daily_all_numbers[date])


        for date in datelist:
            cur_sum = 0
            f.write('{}-{}-{}'.format(date.year, date.month, date.day))
            for feature in total_numbers:
                if feature[0] not in res[date]:
                    f.write(' 0')
                    continue
                cur_sum += res[date][feature[0]]
                f.write(' {}'.format(res[date][feature[0]]))
            if percentage:
                f.write(' {}\n'.format(1.0 - cur_sum))
            else:
                f.write(' {}\n'.format(daily_all_numbers[date] - cur_sum))
        f.close()

    def feature_change_by_browser_date_paper(self, feature, method = 'window'):
        """
        return the number of changed browserid of the feature in each day, method options: window, accu, day 
        """
        print ("generating each day's number")
        db = Database('forpaper345')
        df = db.load_data(feature_list = ['time', 'browser', 'browserid'], table_name = 'patched_pandas')
        df = round_time_to_day(df)

        # keep the same df as changes database
        df = filter_less_than_n(df, 3)
        grouped = df.groupby(['time', 'browser'])
        total_number = {}
        max_size = 0

        if method == 'window':
            max_size = 5
        elif method == 'accu':
            max_size = 10000000
        elif method == 'day':
            max_size = 1

        cur_total = {}
        for cur_group in tqdm(grouped):
            # here we assume time is sorted
            cur_time = cur_group[0][0]
            cur_browser = cur_group[0][1]
            cur_number = cur_group[1]['browserid'].nunique()

            if cur_time not in total_number:
                total_number[cur_time] = {}
            if cur_browser not in cur_total:
                cur_total[cur_browser] = collections.deque() 

            # assume every day we have data for this browser
            cur_total[cur_browser].append(cur_number)
            while len(cur_total[cur_browser]) > max_size:
                cur_total[cur_browser].popleft()

            total_number[cur_time][cur_browser] = sum(cur_total[cur_browser])


        print ("generating real data")
        if feature == 'browserfingerprint':
            db = Database('forpaper345')
            df = db.load_data(table_name = 'allchanges', 
                    feature_list = ['browser', 'fromtime', 'totime', 'browserid', 'tobrowserversion'])
        else:
            db = Database('filteredchangesbrowserid')
            df = db.load_data(table_name = '{}changes'.format(feature))
        df = round_time_to_day(df, timekey = 'totime')
        min_date = min(df['fromtime'])
        min_date = min_date.replace(microsecond = 0, second = 0, minute = 0, hour = 0)
        max_date = max(df['totime'])

        lendate = (max_date - min_date).days
        datelist = [min_date + datetime.timedelta(days = i) for i in range(lendate + 3)]

        # to time is the day that this feature changes
        grouped = df.groupby(['totime', 'browser', 'tobrowserversion'])

        res = {}
        aim_browsers = ['Chrome', 'Firefox', 'Safari']
        total_bversion_number = {}
        for browser in aim_browsers:
            total_bversion_number[browser] = {}

        for cur_group in tqdm(grouped):
            cur_time = cur_group[0][0]
            cur_browser = cur_group[0][1]
            cur_browser_version = cur_group[0][2]
            cur_number = cur_group[1]['browserid'].nunique()
            if cur_browser not in aim_browsers:
                continue

            if cur_browser not in res:
                res[cur_browser] = {}
            if cur_browser_version not in res[cur_browser]:
                res[cur_browser][cur_browser_version] = {}
                total_bversion_number[cur_browser][cur_browser_version] = 0
            
            try:
                if total_number[cur_time][cur_browser] == 0:
                    res[cur_browser][cur_browser_version][cur_time] = 0
                else:
                    res[cur_browser][cur_browser_version][cur_time] = float(cur_number) / float(total_number[cur_time][cur_browser]) * 100
                total_bversion_number[cur_browser][cur_browser_version] += cur_number
            except:
                print 'Error here'
                break
            
        max_version_number = 6
        for browser in aim_browsers:
            # sort versions first
            total_bversion_number[browser] = sorted(total_bversion_number[browser].iteritems(), 
                    key=lambda (k,v): (-v,k))
            
            f = safeopen('./change_dats/{}/{}.dat'.format(feature, browser), 'w')
            f.write('Version#')

            cur_idx = 0
            versions = [b[0] for b in total_bversion_number[browser]]
            for version in versions:
                cur_idx += 1
                if cur_idx > max_version_number:
                    f.write('{}#'.format('Others'))
                    break
                f.write('{}#'.format(version))
            f.write('\n')

            for date in datelist:
                cur_idx = 0
                cur_cnt = 0
                f.write('{}-{}-{}#'.format(date.year, date.month, date.day))
                for browser_version in versions:
                    cur_idx += 1
                    if date in res[browser][browser_version]:
                        cur_num = res[browser][browser_version][date]
                    else:
                        cur_num = 0
                    if cur_idx > max_version_number:
                        cur_cnt += cur_num
                        continue
                    f.write('{}#'.format(cur_num))
                f.write('{}'.format(cur_cnt))
                f.write('\n')
            f.close()

    def feature_change_by_date_paper(self, feature_name):
        """
        take the name of the feature and the changes df
        """
        db = Database('filteredchangesbrowserid')
        df = db.load_data(table_name = '{}changes'.format(feature_name))
        df = remove_flip_users(df)
        print ("{} users remain".format(df['browserid'].nunique()))
        try:
            min_date = min(df['fromtime'])
        except:
            return 
        min_date = min_date.replace(microsecond = 0, second = 0, minute = 0, hour = 0)
        max_date = max(df['totime'])
        lendate = (max_date - min_date).days
        grouped = df.groupby(['from', 'to'])
        # how many browserids 
        sorted_group = collections.OrderedDict(grouped['browserid'].nunique().sort_values(ascending=False))
        sorted_keys = sorted_group.keys()
        total_len = len(grouped)
        output_length = 5
        cur = 0
        dates_data = {}
        datelist = [min_date + datetime.timedelta(days = i) for i in range(lendate + 3)]

        cnt = 0
        sep = ' '

        f = safeopen('./res/topchanges.dat', 'a')
        for group in sorted_group:
            if feature_name == 'langsdetected' or feature_name == 'jsFonts':
                sep = '_'
            elif feature_name == 'plugins':
                sep = '~'
            counts = get_feature_percentage(grouped.get_group(group), 'browser')
            os_counts = get_feature_percentage(grouped.get_group(group), 'os')
            
            try:
                f.write('{} {} {} {} {} {} {} {}\n'.format('$$'.join(group), 
                    '$$', get_change_strs(group[0], group[1], sep=sep), 
                    sorted_group[group], counts[0][0], counts[0][1], os_counts[0][0], os_counts[0][1]))
            except:
                print '$$'.join(str(e) for e in group)
            cnt += 1
            if cnt > 10:
                break
        f.close()

        print ('all changes finished')

        for date in datelist:
            dates_data[date] = {}
            for t in sorted_keys:
                dates_data[date][t] = 0

        for i in tqdm(range(11)):
            try:
                cur_key = sorted_keys[i]
            except:
                break
            cur_group = grouped.get_group(cur_key)
            for idx, row in cur_group.iterrows():
                # round to day
                cur_time = row['totime'].replace(microsecond = 0, second = 0, minute = 0, hour = 0)
                dates_data[cur_time][cur_key] += 1
        first = True
        f = safeopen('./dat/{}changebydate.dat'.format(feature_name),'w')
        for date in datelist:
            if first:
                first = False
                for idx in range(10):
                    try:
                        key = sorted_keys[idx]
                    except:
                        break
                    f.write('{} '.format(str(get_change_strs(key[0], key[1], sep = ' ')).replace(' ','=')))
                f.write('\n')
            f.write('{}-{}-{} '.format(date.year, date.month, date.day))
            sumup = 0
            total = float(sum(dates_data[date].values()))
            if total == 0:
                total = 1
            for idx in range(10):
                try:
                    key = sorted_keys[idx]
                except:
                    break
                f.write('{} '.format(float(dates_data[date][key]) / total))
                sumup += dates_data[date][key]
            f.write('{} '.format(float(sum(dates_data[date].values()) - sumup) / total))
            f.write('\n')
        f.close()

    def feature_minus(self, feature_name, val1, val2):
        helper = Paperlib_helper()
        if feature_name == 'agent':
            return helper.agent_diff(val1, val2)
        elif feature_name == 'language':
            return helper.feature_diff(val1, val2, sep = ';')
        elif feature_name == 'plugins':
            return helper.feature_diff(val1, val2, sep = '~')
        elif feature_name == 'accept':
            return helper.feature_diff(val1, val2, sep = ',')
        else:
            return helper.feature_diff(val1, val2, sep = '_')

    def generate_overall_change_database(self, feature_list = None, keepip = False, groupby_key = 'browserid', aim_table_name = 'fingerprintchanges'):
        """
        generate the delta database of overall fingerprint.
        this table will be genereated in self database
        if keepip is False, we will not include ip related features
        """
        db = self.db
        if keepip == False:
            browserfingerprint = 'noipfingerprint'
        else:
            browserfingerprint = 'browserfingerprint'

        df = db.load_data(table_name = 'patched_all_pandas')
        df = filter_less_than_n(df, 3)

        grouped = df.groupby(groupby_key)
        res = {'IP':[], 'browserid':[], 'fromtime':[], 'totime':[], 
                'const_browser': [], 'const_os': [], 'const_device': [], 'const_IP':[], 'const_clientid': [], 
                'frombrowserversion': [], 'fromosversion': [], 
                'tobrowserversion': [], 'toosversion': []}

        if feature_list == None:
            if keepip == False:
                feature_list = get_fingerprint_change_feature_list() 
            else:
                feature_list = get_fingerprint_feature_list()

        for feature in feature_list:
            res[feature] = []

        pre_row = []
        for cur_key, cur_group in tqdm(grouped):
            if cur_group[browserfingerprint].nunique() == 1:
                continue
            pre_fingerprint = ""
            for idx, row in cur_group.iterrows():

                if pre_fingerprint == "":
                    pre_fingerprint = row[browserfingerprint]
                    pre_row = row
                    continue
                if row[browserfingerprint] == pre_fingerprint:
                    continue

                changed = False
                for feature in feature_list:
                    if feature not in row:
                        continue
                    if row[feature] != pre_row[feature]:
                        difference = self.feature_minus(feature, 
                            pre_row[feature], 
                            row[feature]) 
                        res[feature].append(difference)
                        changed = True
                    else:
                        res[feature].append('')

                if changed == False:
                    for feature in feature_list:
                        del res[feature][-1]
                    continue

                res['IP'].append('{}=>{}'.format(pre_row['IP'], row['IP']))
                res['browserid'].append(row['browserid'])
                res['fromtime'].append(pre_row['time'])
                res['totime'].append(row['time'])

                browser_info = get_browser_version(row['agent'])
                res['tobrowserversion'].append(browser_info.split('#%')[1])
                browser_info = get_browser_version(pre_row['agent'])
                res['frombrowserversion'].append(browser_info.split('#%')[1])

                os_info = get_os_version(row['agent'])
                res['toosversion'].append(os_info.split('#%')[1])
                os_info = get_os_version(pre_row['agent'])
                res['fromosversion'].append(os_info.split('#%')[1])

                res['const_device'].append(row['device'])
                res['const_browser'].append(row['browser'])
                res['const_os'].append(row['os'])
                res['const_IP'].append(row['IP'])
                res['const_clientid'].append(row['clientid'])
        
                pre_fingerprint = row[browserfingerprint]
                pre_row = row
        
        df = pd.DataFrame.from_dict(res)
        print ('finished generating, exporting to sql')
        db.export_sql(df, aim_table_name)
        return 

    def draw_change_reason_by_date(self, table_name = 'patched_tablefeaturechanges'):
        """
        draw the fingure of changed reason by browser

        """
        df = self.db.load_data(table_name = table_name)

        feature_list = get_fingerprint_change_feature_list() 

        columns = self.db.get_column_names(table_name)
        for feature in feature_list:
            if feature not in columns:
                feature_list.remove(feature)
        added_feature = [
                'const_os',
                'const_browser',
                'frombrowserversion',
                'tobrowserversion',
                'fromosversion',
                'toosversion',
                'totime'
                ]

        user_update_keys = [
                'fp2_pixelratio',
                'timezone',
                'cookie',
                'WebGL',
                'localstorage', 
                'plugins'
                ]

        environment_update_keys = [
                'jsFonts',
                'canvastest',
                'inc',
                'gpu',
                'cpucores',
                'audio', 
                'fp2_colordepth',
                'fp2_cpuclass'
                ]

        desktop_browsers = [
                'Chrome',
                'Firefox',
                'Safari',
                ]

        classes = ['browser_update', 'os_update', 'user_update', 'environment_update', 'others']
        
        for feature in added_feature:
            if feature not in feature_list:
                feature_list.append(feature)

        df = round_time_to_day(df, timekey = 'totime')

        min_date = min(df['totime'])
        max_date = max(df['totime'])
        lendate = (max_date - min_date).days
        datelist = [min_date + datetime.timedelta(days = i) for i in range(lendate + 3)]

        grouped = df.groupby(feature_list)
        res = {}
        browser_idx = feature_list.index('const_browser')

        for key, cur_group in tqdm(grouped):
            browser = key[browser_idx]
            frombrowserversion = key[browser_idx + 1]
            tobrowserversion = key[browser_idx + 2]
            fromosversion = key[browser_idx + 3]
            toosversion = key[browser_idx + 4]
            cur_date = key[browser_idx + 5]

            cur_len = len(cur_group)
            if browser not in res:
                res[browser] = {}
                for date in datelist:
                    res[browser][date] = {}
                    for update in classes:
                        res[browser][date][update] = 0

            for i in range(len(feature_list)):
                if key[i] == '':
                    continue
                if feature_list[i] in user_update_keys:
                    res[browser][cur_date]['user_update'] += cur_len
                elif feature_list[i] in environment_update_keys:
                    res[browser][cur_date]['environment_update'] += cur_len
                elif feature_list[i] != 'agent' and feature_list[i] not in added_feature:
                    # if not in user and envir update and the change is not agent, it's others
                    res[browser][cur_date]['others'] += cur_len

            if frombrowserversion != tobrowserversion:
                res[browser][cur_date]['browser_update'] += cur_len
            if fromosversion != toosversion:
                res[browser][cur_date]['os_update'] += cur_len

        for browser in desktop_browsers:
            f = safeopen('./changereasonbydate/{}.dat'.format(browser), 'w')
            f.write('Type#')

            for reason in classes:
                f.write('{}#'.format(reason))
            f.write('\n')

            for date in datelist:
                f.write('{}-{}-{}#'.format(date.year, date.month, date.day))
                cur_date_total = 0
                for reason in classes:
                    cur_date_total += res[browser][date][reason]

                for reason in classes:
                    try:
                        cur_num = float(res[browser][date][reason]) / float(cur_date_total) * 100
                    except:
                        cur_num = 0
                    f.write('{}#'.format(cur_num))
                f.write('\n')
            f.close()

    def draw_change_reason(self, table_name = 'tablefeaturechanges'):
        """
        draw the fingure of changed reason by browser
        """
        df = self.db.load_data(table_name = table_name)

        feature_list = get_fingerprint_change_feature_list() 

        columns = self.db.get_column_names(table_name)
        for feature in feature_list:
            if feature not in columns:
                feature_list.remove(feature)
        added_feature = [
                'os',
                'browser',
                'frombrowserversion',
                'tobrowserversion',
                'fromosversion',
                'toosversion'
                ]

        user_update_keys = [
                'fp2_pixelratio',
                'timezone',
                'cookie',
                'WebGL',
                'localstorage', 
                'plugins'
                ]

        environment_update_keys = [
                'jsFonts',
                'canvastest',
                'inc',
                'gpu',
                'cpucores',
                'audio', 
                'fp2_colordepth',
                'fp2_cpuclass'
                ]

        desktop_browsers = [
                'Chrome',
                'Firefox',
                'Safari',
                'Edge'
                ]

        mobile_browsers = [
                'Chrome Mobile',
                'Firefox Mobile',
                'Mobile Safari',
                'Samsung Internet'
                ]

        classes = ['browser_update', 'os_update', 'user_update', 'environment_update', 'others']
        
        for feature in added_feature:
            if feature not in feature_list:
                feature_list.append(feature)

        grouped = df.groupby(feature_list)

        res = {}
        browser_idx = feature_list.index('browser')
        detailed_list = {}
        total_number = 0

        for key, cur_group in tqdm(grouped):
            # in this for loop, we need to order the reason
            # the order of the reason should be:
            #   OS update, browser update, 
            #   user operations, environment changes
            browser = key[browser_idx]
            frombrowserversion = key[browser_idx + 1]
            tobrowserversion = key[browser_idx + 2]
            fromosversion = key[browser_idx + 3]
            toosversion = key[browser_idx + 4]

            cur_key_str = ''
            cur_len = len(cur_group)
            total_number += cur_len

            if browser not in res:
                res[browser] = {}
                detailed_list[browser] = {}
                for update in classes:
                    res[browser][update] = 0
                    detailed_list[browser][update] = 0

                for feature in feature_list:
                    detailed_list[browser][feature] = 0

            if fromosversion != toosversion:
                res[browser]['os_update'] += cur_len
                detailed_list[browser]['os_update'] += cur_len

            elif frombrowserversion != tobrowserversion:
                res[browser]['browser_update'] += cur_len
                detailed_list[browser]['browser_update'] += cur_len

            else:
                for i in range(len(feature_list)):
                    if key[i] == '':
                        continue
                    cur_key_str += '{}: {}, '.format(feature_list[i], key[i])

                    detailed_list[browser][feature_list[i]] += cur_len

                    if feature_list[i] in user_update_keys:
                        res[browser]['user_update'] += cur_len
                    elif feature_list[i] in environment_update_keys:
                        res[browser]['environment_update'] += cur_len
                    elif feature_list[i] != 'agent' and feature_list[i] not in added_feature:
                        # if not in user and envir update and the change is not agent, it's others
                        res[browser]['others'] += cur_len

            res[browser][cur_key_str] = cur_len
        

        sorted_res = {}
        for browser in res:
            sorted_res[browser] = sorted(res[browser].iteritems(), 
                    key=lambda (k,v): (-v,k))


        res['overall'] = {}
        res['desktopall'] = {}
        res['mobileall'] = {}
        detailed_list['overall'] = {}
        detailed_list['desktopall'] = {}
        detailed_list['mobileall'] = {}

        for update in classes:
            res['overall'][update] = 0
            res['desktopall'][update] = 0
            res['mobileall'][update] = 0
            detailed_list['overall'][update] = 0
            detailed_list['desktopall'][update] = 0
            detailed_list['mobileall'][update] = 0
            for browser in desktop_browsers:
                res['desktopall'][update] += res[browser][update]
                res['overall'][update] += res[browser][update]
                detailed_list['overall'][update] += detailed_list[browser][update]
                detailed_list['desktopall'][update] += detailed_list[browser][update]
            for browser in mobile_browsers:
                res['mobileall'][update] += res[browser][update]
                res['overall'][update] += res[browser][update]
                detailed_list['overall'][update] += detailed_list[browser][update]
                detailed_list['mobileall'][update] += detailed_list[browser][update]
                

        for feature in feature_list:
            detailed_list['overall'][feature] = 0
            detailed_list['desktopall'][feature] = 0
            detailed_list['mobileall'][feature] = 0
            for browser in desktop_browsers:
                detailed_list['overall'][feature] += detailed_list[browser][feature]
                detailed_list['desktopall'][feature] += detailed_list[browser][feature]
            for browser in mobile_browsers:
                detailed_list['overall'][feature] += detailed_list[browser][feature]
                detailed_list['mobileall'][feature] += detailed_list[browser][feature]


        total_number = {}
        for browser in res:
            total_number[browser] = 0
            for update in classes:
                total_number[browser] += res[browser][update]

        '''
        for browser in sorted_res:
            f = safeopen('./changereason/details/{}'.format(browser), 'w')
            for string in sorted_res[browser]:
                f.write('{} {} {}\n'.format(string[0].replace(' ','_'), 
                    string[1], 
                    float(string[1]) / float(total_number[browser])))
            f.close()
        '''

        print ('total_number', total_number)
        print 'desktopall'
        for key in detailed_list['desktopall']:
            print key, detailed_list['desktopall'][key]
        print 'mobile'
        for key in detailed_list['mobileall']:
            print key, detailed_list['mobileall'][key]

        f_all = safeopen('./changereason/overalldetail.dat', 'w')
        for update in classes:
            f_all.write('{}#'.format(update))
        for feature in feature_list:
            f_all.write('{}#'.format(feature))
        f_all.write('\n')
        # write overall to file
        f_all.write('{}#'.format('Overall'))
        for update in classes:
            f_all.write('{}#'.format(float(detailed_list['desktopall'][update] + detailed_list['mobileall'][update])))
        for feature in feature_list:
            f_all.write('{}#'.format(float(detailed_list['desktopall'][feature] + detailed_list['mobileall'][feature])))
        f_all.write('\n')
        f_all.close()

        f_all = safeopen('./changereason/overall.dat', 'w')
        for update in classes:
            f_all.write('{}#'.format(update))
        f_all.write('\n')
        # write overall to file
        f_all.write('{}#'.format('Overall'))
        for update in classes:
            f_all.write('{}#'.format(float(res['desktopall'][update] + res['mobileall'][update]) / float(total_number['desktopall'] + total_number['mobileall'])))
        f_all.write('\n')
        f_all.close()


        f_all = safeopen('./changereason/desktopchanges.dat', 'w')
        for update in classes:
            f_all.write('{}#'.format(update))
        f_all.write('\n')
        # write overall to file
        f_all.write('{}#'.format('Overall'))
        for update in classes:
            f_all.write('{}#'.format(float(res['desktopall'][update]) / float(total_number['desktopall'])))
        f_all.write('\n')

        for browser in desktop_browsers:
            f_all.write('{}#'.format(browser))
            for update in classes:
                f_all.write('{}#'.format(float(res[browser][update]) / float(total_number[browser])))
            f_all.write('\n')
        f_all.close()

        f_all = safeopen('./changereason/mobilechanges.dat', 'w')
        for update in classes:
            f_all.write('{}#'.format(update))
        f_all.write('\n')
        # write overall to file
        f_all.write('{}#'.format('Overall'))
        for update in classes:
            f_all.write('{}#'.format(float(res['mobileall'][update]) / float(total_number['mobileall'])))
        f_all.write('\n')
        for browser in mobile_browsers:
            f_all.write('{}#'.format(browser))
            for update in classes:
                f_all.write('{}#'.format(float(res[browser][update]) / float(total_number[browser])))
            f_all.write('\n')
        f_all.close()

    def remove_flip_fonts(self, df):
        """
        the df need to have the jsFonts column, if this column has the key words,remove this fonts
        """
        flip_fonts_list = [
            '=>Arial Black++Arial Narrow++',
            'Arial Black++Arial Narrow++=>',
            '=>Arial Black++',
            'Arial Black++=>',
            'MT Extra++=>',
            '=>MT Extra++',
            '=>Garamond++',
            'Garamond++=>'
            ]
        for idx in tqdm(df.index):
            if df.at[idx, 'jsFonts'] in flip_fonts_list:
                df.at[idx, 'jsFonts'] = 'flipFonts'
        return df

    def remove_flip_plugins(self, df):
        """
        the df need to have the jsFonts column, if this column has the key words,remove this fonts
        """
        for idx in tqdm(df.index):
            if 'Shockwave Flash' in df.at[idx, 'plugins']:
                df.at[idx, 'plugins'] = df.at[idx, 'plugins'].replace('Shockwave Flash', 'flipplugin')
        return df

    def relation_detection(self, df = [], threshhold = 0.9, table_name = 'allchanges', feature_list = ['jsFonts', 'canvastest', 'plugins', 'gpu', 'audio']):
        """
        this function will return all the changes related to 
            browser update and os update
        the threshhold means if a value change goes together with browser update or os update
        the percentage is higher than threshhold, count it as related
        return related[browser][feature][value] = [agent_list, length_of_related, length_of_curval]
        """
        if len(df) == 0:
            df = self.db.load_data(table_name = table_name)
        related = {}
        overall_list = {}
        for feature in feature_list:
            cur_grouped = df.groupby(['browser', feature])
            for key, cur_group in tqdm(cur_grouped):
                browser = key[0]
                if browser not in related:
                    related[browser] = {}
                if feature not in related[browser]:
                    related[browser][feature] = {'sumup': 0}
                together_list = cur_group[cur_group['agent'] != '']
                if float(len(together_list)) / float(len(cur_group)) > threshhold:
                    related[browser][feature][key[1]] = [cur_group['agent'].unique(), float(len(together_list)), float(len(cur_group)), feature, browser]
                    related[browser][feature]['sumup'] += float(len(together_list))
                    overall_list[key[1]] = related[browser][feature][key[1]]

        sorted_overall = sorted(overall_list.iteritems(), key = lambda (k, v): (-v[1], k))
        fp = safeopen('./relations/overall', 'w')
        for val in sorted_overall:
            fp.write('{}, {}, {}, {}, {}, {}\n'.format(val[0], val[1][1], val[1][2], val[1][3], val[1][4], '====='.join(val[1][0])))
        fp.close()
        return related

    def relation_detection_os_browser(self, df = [], threshhold = 0.9, feature_list = ['jsFonts', 'canvastest', 'plugins', 'gpu', 'audio']):
        """
        same as relation detection ,this time, return by os or browser 
        """
        browser_related = {}
        os_related = {}
        for feature in feature_list:
            cur_grouped = df.groupby(['browser', feature])
            os_together_list = []
            browser_together_list = []
            for key, cur_group in tqdm(cur_grouped):
                for idx, row in cur_group.iterrows():
                    if len(row['tobrowserversion']) == 0 or len(row['toosversion']) == 0:
                        continue
                    if row['agent'] != '':
                        if row['fromosversion'] != row['toosversion']:
                            os_together_list.append((row['os'], row['toosversion']))
                        else:
                            # only keep the big version of browser
                            try:
                                browser_together_list.append((row['browser'], int(row['tobrowserversion'].split('.')[0])))
                            except:
                                print row['tobrowserversion']

                if float(len(os_together_list)) / float(len(cur_group)) > threshhold:
                    os = collections.Counter([v[0] for v in os_together_list]).most_common(1)
                    version = collections.Counter([v[1] for v in os_together_list]).most_common(1)
                    os_related[key[1]] = [feature, os[0], version[0]]
                if float(len(browser_together_list)) / float(len(cur_group)) > threshhold:
                    browser = collections.Counter([v[0] for v in browser_together_list]).most_common(1)
                    version = collections.Counter([v[1] for v in browser_together_list]).most_common(1)
                    browser_related[key[1]] = [feature, browser[0], version[0]]
        return os_related, browser_related 

    def count_val_feature(self, df, val = [], feature = '', sep = '++'):
        """
        this function will return the number of changes caused by the val of feature
        """
        cnt = -1
        res_set = set()
        for idx in tqdm(df.index):
            #cnt += 1
            cnt = df.at[idx, 'browserid']
            cur_vallist = df.at[idx, feature].replace('=>', '++')
            cur_vallist = cur_vallist.split(sep)
            if set(val).issubset(cur_vallist):
                res_set.add(cnt)
        return len(res_set) 

    def request_desktop_detection(self):
        """
        the rule is only the agent string changes
        return this is a request desktop or not
        """
        df = self.db.load_data(table_name = 'final_pandas')
        grouped = df.groupby('clientid')
        res_map = {}
        lied_list = [
                'fp2_liedbrowser',
                'fp2_liedresolution',
                'fp2_liedlanguages',
                'fp2_liedos'
                ]
        lied_set = set()
        cnt = -1
        for key, cur_group in tqdm(grouped):
            cnt += 1
            #if cur_group['os'].nunique() == 1:
            #    continue
            pre_row = {}
            for idx, row in cur_group.iterrows():
                if len(pre_row) == 0:
                    pre_row = row
                    continue
                for lied in lied_list:
                    if pre_row[lied] != row[lied]:
                        lied_set.add(cnt)

                if row['os'] != pre_row['os'] and row['gpu'] == pre_row['gpu'] and row['agent'] != pre_row['agent']:
                    if pre_row['os'] not in res_map:
                        res_map[pre_row['os']] = {}
                    if row['os'] not in res_map[pre_row['os']]:
                        res_map[pre_row['os']][row['os']] = set()
                    res_map[pre_row['os']][row['os']].add(cnt)
                pre_row = row

        total_number = 0
        for f in res_map:
            for t in res_map[f]:
                total_number += len(res_map[f][t])
        print ("Total Number: {}".format(total_number))
        for f in res_map:
            for t in res_map[f]:
                intersection = lied_set.intersection(res_map[f][t])
                print f, t, len(intersection), float(len(intersection)) / float(len(lied_set))#, res_map[f][t][:9]
        return 

    def relation_list(self):
        """
        list the relation related to browser/os update
        """
        feature_list = ['jsFonts', 'canvastest', 'plugins', 'gpu', 'audio', 'encoding']
        df = self.db.load_data(table_name = 'allchanges')
        #os_related, browser_related = self.relation_detection_os_browser(df = df)
        browser_options = [
                'Chrome',
                'Firefox',
                'Safari',
                'Edge',
                'Chrome Mobile',
                'Firefox Mobile',
                'Mobile Safari',
                'Samsung Internet'
                ]
        os_options = [
                'Android',
                'Windows',
                'iOS',
                'Mac OS X'
                ]
        
        cnt = -1
        res = {}
        for idx, row in tqdm(df.iterrows()):
            if row['browser'] not in browser_options:
                continue
            if row['agent'] == '':
                continue

            cnt += 1
            browser = row['browser']
            os = row['os']
            if row['frombrowserversion'] != row['tobrowserversion']:
                try:
                    browser_version = int(row['tobrowserversion'].split('.')[0])
                except:
                    print 'pass'
                    continue

                if browser not in res:
                    res[browser] = {}
                if browser_version not in res[browser]:
                    res[browser][browser_version] = {}
                    res[browser][browser_version]['total'] = set()
                    for f in feature_list:
                        res[browser][browser_version][f] = set()
                for f in feature_list:
                    if row[f] != '':
                        res[browser][browser_version][f].add(cnt)

                res[browser][browser_version]['total'].add(cnt)

            if row['fromosversion'] != row['toosversion']:
                try:
                    os_version = row['toosversion'].split('.')
                    if len(os_version) == 1:
                        os_version = os_version[0]
                    else:
                        os_version = os_version[0] + '.' + os_version[1]
                except:
                    print 'pass'
                    continue

                if os not in res:
                    res[os] = {}
                if os_version not in res[os]:
                    res[os][os_version] = {}
                    res[os][os_version]['total'] = set()
                    for f in feature_list:
                        res[os][os_version][f] = set()
                for f in feature_list:
                    if row[f] != '':
                        res[os][os_version][f].add(cnt)

                res[os][os_version]['total'].add(cnt)

        fp = safeopen('./relations/second', 'w')
        for b in res:
            for version in res[b]:
                fp.write('{} {} '.format(b, version))
                cur_total = len(res[b][version]['total'])
                for f in feature_list:
                    fp.write('{} {} '.format(f, float(len(res[b][version][f])) / float(cur_total)))
                fp.write('\n')
        fp.close()

    def get_flip_list(self, df):
        """
        input a change df
        return a list of flip fonts
        """
        change_font_list = df['jsFonts'].unique()
        left_fonts = set()
        right_fonts = set()
        for fonts in change_font_list:
            cur_fonts = fonts.split('=>')
            left = cur_fonts[0].split('++')
            right = cur_fonts[1].split('++')
            left_fonts.union(left)
            right_fonts.union(right)

        flip_fonts = left_fonts.intersection(right_fonts)
        if '' in flip_fonts:
            flip_fonts.remove('')
        return list(flip_fonts)
        
            
    def draw_detailed_reason(self, table_name = 'allchanges'):
        """
        this is a newer version of changes reason, including
            remove flip jsfonts, flip plugins
            consider MS fonts
        TODO: get the desktop request
        """
        df = self.db.load_data(table_name = table_name)
        ms_office_number = self.count_val_feature(df, val = ['MS Outlook', 'MS Reference Sans Serif'], feature = 'jsFonts')
        print ('Office Fonts:', ms_office_number)
        adobe_number = self.count_val_feature(df, val = ['ADOBE GARAMOND PRO'], feature = 'jsFonts')
        print ('adobe Fonts:', adobe_number)
        return 
        flash_enabled_number = self.count_val_feature(df, val = ['Shockwave Flash'], feature = 'plugins')
        print ('Flash Enabled:', flash_enabled_number)
        df = self.remove_flip_plugins(df)
        df = self.remove_flip_fonts(df)
        totalNumOfChanges = 0
        match_list = {
                'WebGL': 'WebGL',
                'inc': 'inc',
                'gpu': 'GPU', 
                'fp2_colordepth': 'colorDepth',
                #'accept': 'header',
                'encoding': 'encoding',
                'language': 'language',
                #'httpheaders': 'header',
                'agent': 'agent',
                'resolution': 'resolution',
                'localstorage': 'localStorage',
                'fp2_pixelratio': 'zoom',
                'langsdetected': 'detectedLanguages',
                'timezone': 'timezone',
                'plugins': 'plugin',
                'cookie': 'cookie',
                'fp2_liedbrowser': 'fp2_liedbrowser',
                'fp2_liedresolution': 'fp2_liedresolution',
                'fp2_liedlanguages': 'fp2_liedlanguages',
                'fp2_liedos': 'fp2_liedos',
                'audio': 'audio',
                'jsFonts': 'jsFonts',
                'canvastest': 'canvas',
                'ipcity': 'ipcity',
                'ipregion': 'ipregion',
                'ipcountry': 'ipcountry'
                }

        useraction_list = ['localStorage', 'zoom', 'timezone', 'cookie', 'WebGL', 'fp2_liedbrowser', 'fp2_liedresolution', 'fp2_liedlanguages', 'fp2_liedos', 'private', 'flash', 'resolution']
        environment_list = ['colorDepth', 'detectedLanguages', 'audio', 'plugin', 'jsFonts', 'encoding', 'language', 'canvas', 'GPU', 'inc']
        network_list = ['ipcity', 'ipregion', 'ipcountry']

        added_feature = [
                'os',
                'browser',
                'frombrowserversion',
                'tobrowserversion',
                'fromosversion',
                'toosversion'
                ]

        desktop_browsers = [
                'Chrome',
                'Firefox',
                'Safari',
                'Edge'
                ]

        mobile_browsers = [
                'Chrome Mobile',
                'Firefox Mobile',
                'Mobile Safari',
                'Samsung Internet'
                ]
        os_options = [
                'Android',
                'Windows',
                'iOS',
                'Mac OS X'
                ]

        feature_list = get_fingerprint_change_feature_list() 
        columns = self.db.get_column_names(table_name)
        for feature in feature_list:
            if feature not in columns:
                feature_list.remove(feature)

        for feature in added_feature:
            if feature not in feature_list:
                feature_list.append(feature)

        related = self.relation_detection(df = df, feature_list = match_list.keys())#['audio', 'canvastest', 'jsFonts', 'gpu', 'plugins', 'cookie', 'language', 'encoding', 'langsdetected'])

        #If just want relation, return here
        detailed_list = {}

        browser_idx = feature_list.index('browser')
        total_number = {'overall': 0, 'desktop': 0, 'mobile': 0}

        change_ids = {'private': set(), 'flash': set(), 'browserUpdate': set(), 'osUpdate': set(), 'userAction': set(), 'environmentUpdate': set(), 'networkUpdate': set()}
        for key in match_list:
            change_ids[match_list[key]] = set()

        browsermap = {}
        osmap = {}
        cnt = -1
        classes_numbers = {}

        output_type = 1
        #remove the only IP change numbers
        total_browserids = 0 #df['browserid'].nunique()

        for browser in desktop_browsers:
            classes_numbers[browser] = {}
        for browser in mobile_browsers:
            classes_numbers[browser] = {}
        for os in os_options:
            classes_numbers[os] = {}
        classes_numbers['overall'] = {}

        others_numbers = {}
        reason_map = {}
        for idx, row in tqdm(df.iterrows()):
            if output_type == 1:
                cnt = row['browserid']
            else:
                cnt += 1
            browser = row['browser']
            os = row['os']
            cur_classes = ''

            if browser not in browsermap:
                browsermap[browser] = {'networkUpdate': set(), 'browserUpdate': set(), 'osUpdate': set(), 'userAction': set(), 'environmentUpdate': set(), 'flash': set(), 'private': set()}
                for key in match_list:
                    browsermap[browser][match_list[key]] = set()
            if os not in osmap:
                osmap[os] = {'networkUpdate': set(), 'browserUpdate': set(), 'osUpdate': set(), 'userAction': set(), 'environmentUpdate': set(), 'flash': set(), 'private': set()}
                for key in match_list:
                    osmap[os][match_list[key]] = set()

            if row['frombrowserversion'] != row['tobrowserversion'] or (row['fromosversion'] == 
                    row['toosversion'] and row['agent'] != ''):
                change_ids['browserUpdate'].add(cnt)
                browsermap[browser]['browserUpdate'].add(cnt)
                osmap[os]['browserUpdate'].add(cnt)
                cur_classes += 'browserupdate_'
                
            if row['fromosversion'] != row['toosversion']:
                change_ids['osUpdate'].add(cnt)
                browsermap[browser]['osUpdate'].add(cnt)
                osmap[os]['osUpdate'].add(cnt)
                cur_classes += 'osupdate_'

            for feature in match_list:
                if row[feature] != '':
                    # remove related features
                    if feature in related[browser] and row[feature] in related[browser][feature]:
                        continue

                    if feature != 'jsFonts' and feature != 'plugins':
                        change_ids[match_list[feature]].add(cnt)
                        browsermap[browser][match_list[feature]].add(cnt)
                        osmap[os][match_list[feature]].add(cnt)

                    if feature == 'jsFonts' and row[feature] == 'flipFonts':
                        browsermap[browser]['private'].add(cnt)
                        osmap[os]['private'].add(cnt)
                        change_ids['private'].add(cnt)
                    if feature == 'plugins' and 'flipplugin' in row[feature]:
                        browsermap[browser]['flash'].add(cnt)
                        osmap[os]['flash'].add(cnt)
                        change_ids['flash'].add(cnt)

                    #jsFonts special
                    if (match_list[feature] in useraction_list) or (feature =='jsFonts' and row[feature] == 'flipFonts') or (feature == 'plugins' and 'flipplugin' in row[feature]):
                        change_ids['userAction'].add(cnt)
                        browsermap[browser]['userAction'].add(cnt)
                        osmap[os]['userAction'].add(cnt)
                        if 'useraction' not in cur_classes:
                            cur_classes += 'useraction_'

                    elif match_list[feature] in environment_list:
                        #for get the reason of jsFonts
                        """
                        if feature == 'canvastest':
                            if row[feature] not in reason_map:
                                reason_map[row[feature]] = {'total': 0}
                            if browser not in reason_map[row[feature]]:
                                reason_map[row[feature]][browser] = 0
                            reason_map[row[feature]][browser] += 1
                            reason_map[row[feature]]['total'] += 1
                        """
                        if feature == 'jsFonts':
                            val = row['jsFonts']
                            for font in flip_fonts_list:
                                row['jsFonts'].replace(font, '')
                            row['jsFonts'].replace('flipFonts', '')
                            row['jsFonts'].replace('+', '')
                            row['jsFonts'].replace('=>', '')
                            if len(row['jsFonts']) == 0:
                                continue

                        if feature == 'jsFonts' or feature == 'plugins':
                            change_ids[match_list[feature]].add(cnt)
                            browsermap[browser][match_list[feature]].add(cnt)
                            osmap[os][match_list[feature]].add(cnt)

                        change_ids['environmentUpdate'].add(cnt)
                        browsermap[browser]['environmentUpdate'].add(cnt)
                        osmap[os]['environmentUpdate'].add(cnt)
                        if 'environment' not in cur_classes:
                            cur_classes += 'environment_'

                    elif match_list[feature] in network_list:
                        change_ids['networkUpdate'].add(cnt)
                        browsermap[browser]['networkUpdate'].add(cnt)
                        osmap[os]['networkUpdate'].add(cnt)
                        #if 'network' not in cur_classes:
                        #    cur_classes += 'network_'

            if len(cur_classes) > 0:
                total_browserids += 1
                if cur_classes not in classes_numbers['overall']:
                    classes_numbers['overall'][cur_classes] = set()
                classes_numbers['overall'][cur_classes].add(cnt)

                if browser in classes_numbers:
                    if cur_classes not in classes_numbers[browser]:
                        classes_numbers[browser][cur_classes] = set()
                    classes_numbers[browser][cur_classes].add(cnt)
                if os in classes_numbers:
                    if cur_classes not in classes_numbers[os]:
                        classes_numbers[os][cur_classes] = set()
                    classes_numbers[os][cur_classes].add(cnt)

            for feature in feature_list:
                if feature not in useraction_list and feature not in environment_list and cur_classes == '':
                    if feature not in others_numbers:
                        others_numbers[feature] = 0
                    if row[feature] != '':
                        others_numbers[feature] += 1

        #userd for get the reason of changes
        #===================================
        '''
        reason_map = sorted(reason_map.iteritems(), key = lambda (k, v): (-v['total'], k))
        for reason in reason_map:
            print '===================', reason
        '''
        #return 
        #===================================


        sorted_classes_numbers = {}
        for cur_type in classes_numbers:
            sorted_classes_numbers[cur_type] = sorted(classes_numbers[cur_type].iteritems(), key = lambda (k, v): (-len(v), k))


        total_update = 0
        f = safeopen('./changereason/bigtable/updatepercentage', 'w')
        for browser in browsermap:
            total_update += len(browsermap[browser]['browserUpdate'])
        if total_update == 0:
            total_update = 1
        if output_type == 1:
            total_update = total_browserids
        for browser in browsermap:
            f.write('{}\t{}\n'.format(browser, float(len(browsermap[browser]['browserUpdate'])) / float(total_update)))

        total_update = 0
        for os in osmap:
            total_update += len(osmap[os]['osUpdate'])
        if total_update == 0:
            total_update = 1
        if output_type == 1:
            total_update = total_browserids
        for os in osmap:
            f.write('{}\t{}\n'.format(os, float(len(osmap[os]['osUpdate'])) / float(total_update)))
        f.close()

        f = safeopen('./changereason/bigtable/classes', 'w')
        for cur_type in sorted_classes_numbers:
            cur_total_number = sum([len(v[1]) for v in sorted_classes_numbers[cur_type]])
            f.write('{}====================\n'.format(cur_type))
            if cur_total_number == 0:
                cur_total_number = 1
            if output_type == 1:
                cur_total_number = total_browserids
            for item in sorted_classes_numbers[cur_type]:
                f.write('{}\t{}\t{}\n'.format(item[0], float(len(item[1])) / float(cur_total_number), len(item[1])))
        for item in others_numbers:
            f.write('{}\t{}\n'.format(item, others_numbers[item]))
        f.close()

        cur_total = 0
        f = safeopen('./changereason/bigtable/{}'.format('overallactionenv'), 'w')
        f.write('useraction\n')
        for key in useraction_list:
            cur_total += len(change_ids[key])
            if output_type == 1:
                cur_total = total_browserids
            if cur_total == 0:
                cur_total = 1
        f.write('cur_total: {}\n'.format(cur_total))
        for key in useraction_list:
            f.write('{}\t{}\n'.format(key, float(len(change_ids[key])) / float(cur_total)))

        cur_total = 0
        f.write('environment_list\n')
        for key in environment_list:
            cur_total += len(change_ids[key])
        f.write('cur_total: {}\n'.format(cur_total))
        if output_type == 1:
            cur_total = total_browserids
        if cur_total == 0:
            cur_total = 1
        for key in environment_list:
            f.write('{}\t{}\n'.format(key, float(len(change_ids[key])) / float(cur_total)))

        cur_total = 0
        f.write('network Update\n')
        for key in network_list:
            cur_total += len(change_ids[key])
        if output_type == 1:
            cur_total = total_browserids
        if cur_total == 0:
            cur_total = 1
        for key in network_list:
            f.write('{}\t{}\n'.format(key, float(len(change_ids[key])) / float(cur_total)))
        f.close()

        for browser in browsermap:
            f = safeopen('./changereason/bigtable/browser/{}'.format(browser), 'w')
            f.write('{}\n'.format('useraction'))
            cur_total = 0
            for key in useraction_list:
                cur_total += len(browsermap[browser][key])
            if cur_total == 0:
                cur_total = 1
            for key in useraction_list:
                f.write('{}\t{}\n'.format(key, float(len(browsermap[browser][key])) / float(cur_total)))

            f.write('{}\n'.format('environment'))
            cur_total = 0
            for key in environment_list:
                cur_total += len(browsermap[browser][key])
            if cur_total == 0:
                cur_total = 1
            for key in environment_list:
                f.write('{}\t{}\n'.format(key, float(len(browsermap[browser][key])) / float(cur_total)))
            f.close()

        for os in osmap:
            f = safeopen('./changereason/bigtable/os/{}'.format(os), 'w')
            f.write('{}\n'.format('useraction'))
            cur_total = 0
            for key in useraction_list:
                cur_total += len(osmap[os][key])
            if cur_total == 0:
                cur_total = 1
            for key in useraction_list:
                f.write('{}\t{}\n'.format(key, float(len(osmap[os][key])) / float(cur_total)))

            f.write('{}\n'.format('environment'))
            cur_total = 0
            for key in environment_list:
                cur_total += len(osmap[os][key])
            if cur_total == 0:
                cur_total = 1
            for key in environment_list:
                f.write('{}\t{}\n'.format(key, float(len(osmap[os][key])) / float(cur_total)))
            f.close()

        f = safeopen('./changereason/bigtable/ossplit', 'w')
        for key in match_list:
            key = match_list[key]
            cur_total = 0
            for os in osmap:
                cur_total += len(osmap[os][key])
            if output_type == 1:
                cur_total = total_browserids
            if cur_total == 0:
                cur_total = 1
            f.write('{}==================\n'.format(key))
            for os in osmap:
                f.write('{}\t{}\t{}\n'.format(os, len(osmap[os][key]), float(len(osmap[os][key])) / float(cur_total)))

        f.close()

        f = safeopen('./changereason/bigtable/browsersplit', 'w')
        for key in match_list:
            key = match_list[key]
            cur_total = 0
            for b in browsermap:
                cur_total += len(browsermap[b][key])
            if output_type == 1:
                cur_total = total_browserids
            if cur_total == 0:
                cur_total = 1
            f.write('{}==================\n'.format(key))
            for b in browsermap:
                f.write('{}\t{}\t{}\n'.format(b, len(browsermap[b][key]), float(len(browsermap[b][key])) / float(cur_total)))

        f.close()
        return 

    def check_vpn_usage(self, fromip, toip, fromtime, totime):
        """
        input the from, to ip, from to time
        return use vpn or not
        """
        ip2location = self.ip2loation_table
        ip_from = self.ip2location_from

        int_ip = ip2int(fromip)
        idx = bisect.bisect_left(ip_from, int_ip) - 1
        fromlatitude = ip2location.iloc[idx]['latitude']
        fromlongitude = ip2location.iloc[idx]['longitude']
        int_ip = ip2int(toip)
        idx = bisect.bisect_left(ip_from, int_ip) - 1
        tolatitude = ip2location.iloc[idx]['latitude']
        tolongitude = ip2location.iloc[idx]['longitude']

        seconds_change = float((totime - fromtime).total_seconds())
        distance_change = ip_distance(fromlatitude, fromlongitude,
                tolatitude,
                tolongitude) 

        if seconds_change == 0:
            seconds_change = 0.1

        km_per_hour = distance_change / (seconds_change / 3600)

        if km_per_hour > 1999:
            return True
        return False

    def network_change_statics(self):
        """
        input a change dataframe, return VPN usage, subnet change
        IP city, IP region, IP country change
        """
        df = self.db.load_data(table_name = 'allchanges', feature_list = ['IP', 'ipcity', 'ipregion', 'ipcountry', 'fromtime', 'totime', 'browserid'])
        ip_db = Database('uniquemachine')
        self.ip2loation_table = ip_db.load_data(table_name = 'ip2location_db5')
        self.ip2location_from = self.ip2loation_table['ip_from']
        cnt = -1
        total_ip_change = set()
        numbers = {'vpn': set(), 'subnet': set(), 'ipcity': set(), 'ipregion': set(), 'ipcountry': set()}
        for idx, row in tqdm(df.iterrows()):
            #cnt += 1
            cnt = row['browserid']
            ip_0 = row['IP'].split('=>')[0]
            ip_1 = row['IP'].split('=>')[1]
            if ip_0 == ip_1:
                continue
            total_ip_change.add(cnt)
            ip_0_list = ip_0.split('.')
            ip_1_list = ip_1.split('.')
            if ip_0_list[0] == ip_1_list[0] and ip_0_list[1] == ip_1_list[1] and ip_0_list[2] == ip_1_list[2] and ip_0_list[3] != ip_1_list[3]:
                numbers['subnet'].add(cnt)
            if self.check_vpn_usage(ip_0, ip_1, row['fromtime'], row['totime']):
                numbers['vpn'].add(cnt)
            if row['ipcity'] != '':
                numbers['ipcity'].add(cnt)
            if row['ipregion'] != '':
                numbers['ipregion'].add(cnt)
            if row['ipcountry'] != '':
                numbers['ipcountry'].add(cnt)

        numbers['ipcity'] = numbers['ipcity'] - numbers['ipregion'] - numbers['vpn']
        numbers['ipregion'] = numbers['ipregion'] - numbers['ipcountry'] - numbers['vpn']
        numbers['ipcountry'] = numbers['ipcountry'] - numbers['vpn']
        numbers['subnet'] -= numbers['vpn']

        for key in numbers:
            numbers[key] = len(numbers[key])

        fp = safeopen('./networkstaticsbybrowserid.dat', 'w')
        for key in numbers:
            fp.write('{}\t{}\t{}\n'.format(key, numbers[key],float(numbers[key]) / float(len(total_ip_change))))
        fp.close()
        return numbers

    def rebuild_fingerprintchanges(self, 
            from_table = 'fingerprintchanges', 
            aim_table = 'filteredfingerprintchanges'):
        """
        this function will remove useless changes
        """
        db = Database('forpaper345')
        df = db.load_data(table_name = from_table)

        df = self.paperlib_helper.remove_change_only(df, 
                ['audio', 'jsFonts', 'jsFonts'], 
                ['Chrome', 'Firefox', 'Safari'])
        df = self.paperlib_helper.remove_change_only(df, 
                ['accept', 'audio'], ['Chrome', 'Safari'])
        df = self.paperlib_helper.remove_change_only(df, 
                ['plugins', 'plugins'], ['Chrome', 'Safari'])

        print ('finished rebuild, storing back to sql')
        db.export_sql(df, aim_table)
        return 

    def number_feature_per_feature(self, df, feature_1, feature_2, output_file = None, percentage = False, max_num = 3):
        """
        get how many feature 1 have 1,2,...n feature_2 values
        if percentage is True, the res will be percentage of feature 1
        """
        if output_file == None:
            output_file = './distribution/{}_{}'.format(feature_1, feature_2)

        res = [0 for x in range(max_num)]
        total = 0
        grouped = df.groupby(feature_1)
        for key, cur_group in tqdm(grouped):
            total += 1
            cur_num = cur_group[feature_2].nunique()
            if cur_num > max_num - 1:
                res[max_num - 1] += 1 
            else:
                res[cur_num - 1] += 1

        f = safeopen(output_file, 'w')
        for idx in range(len(res)):
            if percentage:
                f.write('{}#'.format(float(res[idx]) / float(total)))
            else:
                f.write('{}#'.format(res[idx]))
        f.close()
        return 

    def number_feature_per_feature_with_changes(self, df, feature_1, feature_2, output_file = None, percentage = False, max_num = 6):
        """
        based on number feature per features, we also output in one bar, the percentage of number of changes
        """
        if output_file == None:
            output_file = './distribution/{}_{}'.format(feature_1, feature_2)

        #df_c = self.db.load_data(table_name = "tablefeaturechanges")
        df_c = self.db.load_data(table_name = "allchanges")
        max_num_c = max_num

        res = [0 for x in range(max_num)]
        change_times = {}
        for x in range(max_num):
            change_times[x] = [0 for y in range(max_num_c)]

        total = 0
        grouped = df.groupby(feature_1)
        grouped_c = df_c.groupby(feature_1)

        for key, cur_group in tqdm(grouped):
            total += 1
            cur_num = len(cur_group[feature_2])
            try:
                cur_group_c = grouped_c.get_group(key)
                cur_num_c = cur_group_c.shape[0]
            except:
                cur_num_c = 0

            if cur_num_c >= max_num_c:
                cur_num_c = max_num_c - 1
            if cur_num > max_num - 1:
                cur_num = max_num

            change_times[cur_num - 1][cur_num_c] += 1

        f = safeopen(output_file, 'w')
        for idx in range(len(res)):
            f.write('{}#'.format(idx + 1))
            if percentage:
                f.write('{}#'.format(float(res[idx]) / float(total)))
            else:
                for cur_num_c in change_times[idx]:
                    f.write('{}#'.format(cur_num_c))
            f.write('\n')
        f.close()
        return 

    def feature_correlation(self, df):
        """
        df is the changes database. get feature correlation based on browser type
        """
        all_feature_list = get_fingerprint_feature_list_include_gpuimgs()
        grouped = df.groupby('const_browser')
        browser_list = ['Chrome', 'Firefox', 'Safari']

        cnt_res = {}
        cnt_together_res = {}

        for browser in browser_list:
            cnt_res[browser] = {}
            cur_group = grouped.get_group(browser)
            print ('doing {}'.format(browser))
            for idx, row in tqdm(cur_group.iterrows()):
                for feature in all_feature_list:
                    if feature not in cnt_res[browser]:
                        cnt_res[browser][feature] = {}
                    if row[feature] not in cnt_res[browser][feature]:
                        cnt_res[browser][feature][row[feature]] = {'total': 0}
                    cnt_res[browser][feature][row[feature]]['total'] += 1
                    for feature2 in all_feature_list:
                        if row[feature2] == '':
                            continue
                        cur_val = '{}:{}'.format(feature2, row[feature2])
                        if cur_val not in cnt_res[browser][feature][row[feature]]:
                            cnt_res[browser][feature][row[feature]][cur_val] = 0
                        cnt_res[browser][feature][row[feature]][cur_val] += 1
            for feature in cnt_res[browser]:
                for key_val in cnt_res[browser][feature]:
                    cnt_res[browser][feature][key_val] = sorted(cnt_res[browser][feature][key_val].iteritems(), key=lambda (k,v): (-v,k))
                cnt_res[browser][feature] = sorted(cnt_res[browser][feature].iteritems(), key = lambda(k, v): (-v[0][1], k))

            print browser
            for feature in cnt_res[browser]:
                print '\t{}'.format(feature)
                for pair in cnt_res[browser][feature][:10]:
                    for val in pair[:5]:
                        print '\t\t\t{}'.format(val[:10])

    def check_flip_feature(self, group, feature_name):
        """
        check wether a feature fliped in a group
        """
        res = set()
        pre_val = ""
        for idx, row in group.iterrows():
            if pre_val == "":
                pre_val = row[feature_name]
                res.add(row[feature_name])
                continue
            elif pre_val == row[feature_name]:
                continue

            if row[feature_name] in res:
                return True
            res.add(row[feature_name])
        return False

    def cookie_pattern(self):
        """
        return the percentage of cookie change pattern
        """
        df = self.db.load_data(table_name = 'patched_pandas')

        #df = filter_less_than_n(df, 3)

        grouped = df.groupby('browserid')
        patterns = ['One cookie', 'Cookie change', 'Private mode', 'Two cookie flip']

        pattern_cnt = [0, 0, 0, 0]
        for key, cur_group in tqdm(grouped):
            if cur_group['label'].nunique() == 1:
                pattern_cnt[0] += 1
                continue
            fliped = self.check_flip_feature(cur_group, 'label')
            if fliped:
                if cur_group['label'].nunique() > 2:
                    pattern_cnt[2] += 1
                else:
                    pattern_cnt[3] += 1
            else:
                pattern_cnt[1] += 1

        total = sum(pattern_cnt)
        print ('Total: {}'.format(total))
        for idx in range(len(pattern_cnt)):
            print ("{}: {}({})".format(patterns[idx], pattern_cnt[idx], float(pattern_cnt[idx]) / float(total)))

    def get_company_from_gpu(self, gpu):
        """
        return the rough value of gpu by all gpu
        """
        gpu_types = [
                'nvidia',
                'intel',
                'powervr',
                'mali',
                'adreno',
                'amd',
                'ati',
                'mesa'
                ]

        for gpu_type in gpu_types:
            if gpu.lower().find(gpu_type) != -1:
                return gpu_type
        return 'others'

    def gpu_inference(self):
        """
        trying to use gpuimgs result to get the type of gpu
        """
        df = self.db.load_data(table_name = 'patched_all_pandas', 
                feature_list = ['browserid', 'gpu', 'gpuimgs', 'canvastest'])
        grouped = df.groupby('gpu')
        imgs_grouped = df.groupby('gpuimgs')

        map_num = {}
        user_map = {}
        total_map = {}
        print ("preparing imgs number")
        for key, cur_group in imgs_grouped:
            cur_res = set()
            for gpu_type in cur_group['gpu'].unique():
                if gpu_type == 'No Debug Info':
                    continue
                cur_res.add(self.get_company_from_gpu(gpu_type))
            map_num[key] = len(cur_res)
            user_map[key] = set(cur_group['browserid'].unique())
            total_map[key] = list(cur_res)

        success = {}
        overall = {}
        mapback = {}
        possible = [set() for i in range(5)]
        total_masked = 0

        for key, cur_group in tqdm(grouped):
            if key == 'No Debug Info':
                total_masked = cur_group['browserid'].nunique()
                gpuimgs = cur_group['gpuimgs'].unique()
                for gpuimg in gpuimgs:
                    # accurate map back
                    if map_num[gpuimg] == 1:
                        if total_map[gpuimg][0] not in mapback:
                            mapback[total_map[gpuimg][0]] = set()
                        cur_accu_group = imgs_grouped.get_group(gpuimg)
                        small_group = cur_accu_group.groupby('gpu')
                        mapback[total_map[gpuimg][0]] |= set(small_group.get_group('No Debug Info')['browserid'].unique())

                    if map_num[gpuimg] != 0 and map_num[gpuimg] < 5:
                        cur_accu_group = imgs_grouped.get_group(gpuimg)
                        small_group = cur_accu_group.groupby('gpu')
                        possible[map_num[gpuimg]] |= set(small_group.get_group('No Debug Info')['browserid'].unique())
                continue

            key = self.get_company_from_gpu(key)
            if key == 'mesa':
                print key
            if key not in overall:
                overall[key] = set()
                success[key] = set()
            gpuimgs = cur_group['gpuimgs'].unique()
            for gpuimg in gpuimgs:
                # for None value
                if gpuimg.find('^') != -1:
                    continue
                if map_num[gpuimg] == 1:
                    success[key] |= user_map[gpuimg]
                overall[key] |= user_map[gpuimg]

        
        f = safeopen('./res/roughgpuinference.dat', 'w')
        for gpu in overall:
            f.write('{} {} {} {} {} {}\n'.format(gpu, 
                len(success[gpu]), len(overall[gpu]), 
                float(len(success[gpu])) / float(len(overall[gpu])), 
                len(mapback[gpu]), total_masked))
        for i in range(5):
            f.write('{} {}\n'.format(i, len(possible[i])))
        f.close()

    def gpu_type_cnt(self):
        """
        for interesting
        """
        df = self.db.load_data(table_name = 'patched_all_pandas', 
                feature_list = ['browserid', 'gpu'])
        grouped = df.groupby('gpu')
        res = {}
        for key, cur_group in tqdm(grouped):
            res[key] = cur_group['browserid'].nunique()

        overall = sorted(res.iteritems(), key=lambda (k,v): (-v,k))
        for t in overall:
            print t

    def get_statics(self):
        """
        get all the static numbers
        """
        
        num_browserids = 0
        num_dynamics = 0
        num_clientids = 0
        num_fingerprints = 0
        total_fingerprints = 0

        df = self.db.load_data(table_name = 'patched_all_pandas', feature_list = ['browserid', 'clientid', 'browserfingerprint'])
        df_c = self.db.load_data(table_name = 'patched_tablefeaturechanges', feature_list = ['browserfingerprint'])

        print ("Before filter less than 3:")
        num_browserids = df['browserid'].nunique()
        num_clientids = df['clientid'].nunique()
        num_fingerprints = df['browsefingerprint'].nunique()
        print ('Num Browserids: {}\nNum user ids: {}\nNum fingerprints: {}'.format(num_browserids, num_clientids, num_fingerprints))


        print ("After filter less than 3:")
        df = filter_less_than_n(df, 3)
        num_browserids = df['browserid'].nunique()
        num_clientids = df['clientid'].nunique()
        num_dynamics = df_c.shape[0]
        print ('Num Browserids: {}\nNum dynamics: {}\nNum user ids: {}'.format(num_browserids, num_dynamics, num_clientids))

    def change_reason_by_cookie(self, feature_name = 'browserid'):
        """
        try to anlyse the reason of changes
        """

        df = self.db.load_data(table_name = 'patched_all_pandas', 
                feature_list = ['browserid', 'browser', 'agent', 'label', 'time', 'gpu'])

        grouped = df.groupby('label')

        f = safeopen('./specialcases/{}'.format(feature_name), 'w')
        for key, cur_group in tqdm(grouped):
            if cur_group[feature_name].nunique() == 1:
                continue

            f.write('{}\n'.format(key))
            cur_grouped = cur_group.groupby(['agent', 'browserid', 'browser', 'gpu'])
            for key, value in cur_grouped:
                f.write('\t{}\n'.format(key))

        f.close()

    def update_influence(self):
        """
        anlyse how one update incluence another browser
        here we based on client id not browser id
        """
        df = self.db.load_data(table_name = 'patched_tablefeaturechanges')
        grouped = df.groupby('browserid')

        f = safeopen('./res/differenctbidchangetogether.dat', 'w')
        for clientid, cur_group in tqdm(grouped):
            for idx, row in cur_group.iterrows():
                if row['canvastest'] != '' and row['os'] != '':
                    f.write('{}\n'.format(clientid))
                    break
        f.close()

    def fingerprint_distribution(self):
        """
        get the fingerprint distribution of 1, 2-10, 10-50
        """

        df = self.db.load_data(table_name = 'final_pandas', feature_list = ['browserfingerprint', 'ispc', 'browser'])
        grouped = df.groupby('browserfingerprint')

        num_cnt = {}
        for key, cur_group in tqdm(grouped):
            cur_cnt = cur_group.shape[0]
            # the ispc value should be same for
            # all records in this group
            browser = cur_group['browser'].unique()[0]
            if browser not in num_cnt:
                num_cnt[browser] = [0, 0, 0, 0]
            if cur_cnt == 1:
                num_cnt[browser][0] += 1
            elif cur_cnt < 10:
                num_cnt[browser][1] += 1
            elif cur_cnt < 50:
                num_cnt[browser][2] += 1
            else:
                num_cnt[browser][3] += 1

        desktop_browsers = ['Chrome', 'Firefox', 'Safari', 'Edge']
        desktop_overall = [0, 0, 0, 0]
        mobile_browsers = ['Chrome Mobile', 'Firefox Mobile', 'Mobile Safari', 'Samsung Internet']
        mobile_overall = [0, 0, 0, 0]
        total_overall = [0, 0, 0, 0]

        for idx in range(4):
            for browser in desktop_browsers:
                desktop_overall[idx] += num_cnt[browser][idx] 
            for browser in mobile_browsers:
                mobile_overall[idx] += num_cnt[browser][idx]
            total_overall[idx] = desktop_overall[idx] + mobile_overall[idx]

        f = safeopen('./fingerprintdistribution/overall.dat', 'w')
        for idx in range(4):
            f.write('{}#'.format(float(total_overall[idx]) / float(sum(total_overall))))
        f.write('\n')

        f = safeopen('./fingerprintdistribution/desktop.dat', 'w')
        for idx in range(4):
            f.write('{}#'.format(float(desktop_overall[idx]) / float(sum(desktop_overall))))
        f.write('\n')
        for browser in desktop_browsers:
            f.write('{}#'.format(browser))
            cur_total = sum([num_cnt[browser][n] for n in range(4)])
            for idx in range(4):
                f.write('{}#'.format(float(num_cnt[browser][idx]) / float(cur_total)))
            f.write('\n')
        f.close()

        f = safeopen('./fingerprintdistribution/mobile.dat', 'w')
        for idx in range(4):
            f.write('{}#'.format(float(mobile_overall[idx]) / float(sum(mobile_overall))))
        f.write('\n')
        for browser in mobile_browsers:
            f.write('{}#'.format(browser))
            cur_total = sum([num_cnt[browser][n] for n in range(4)])
            for idx in range(4):
                f.write('{}#'.format(float(num_cnt[browser][idx]) / float(cur_total)))
            f.write('\n')
        f.close()

    def ip_location_paper(self):
        """
        output the location info to distince
        """
        df = self.db.load_data(table_name = 'final_pandas', 
                feature_list = ['browserid', 'time', 'IP'])
        ip_db = Database('uniquemachine')
        ip2location = ip_db.load_data(table_name = 'ip2location_db5')
        ip_from = ip2location['ip_from']

        client = df.groupby('browserid')
        pre_row = ""
        vpn_browserids = {'browserid': [], 'fromip': [], 'toip': []}
        for key, items in tqdm(client):
            num_ip = items['IP'].nunique()
            if num_ip > 1:
                pre_row = ""
                for name, row in items.iterrows():
                    if type(pre_row) != type("") and pre_row['IP'] == row['IP']:
                        continue

                    ip = row['IP']
                    int_ip = ip2int(ip)
                    idx = bisect.bisect_left(ip_from, int_ip) - 1
                    latitude = ip2location.iloc[idx]['latitude']
                    longitude = ip2location.iloc[idx]['longitude']
                    if type(pre_row) == type(""):
                        pre_row = row
                        pre_row['latitude'] = latitude
                        pre_row['longitude'] = longitude
                        continue

                    seconds_change = float((row['time'] - pre_row['time']).total_seconds())
                    distance_change = ip_distance(pre_row['latitude'], pre_row['longitude'],
                            latitude,
                            longitude) 

                    if seconds_change == 0:
                        seconds_change = 0.1

                    km_per_hour = distance_change / (seconds_change / 3600)

                    if km_per_hour > 1999:
                        vpn_browserids['browserid'].append(key) 
                        vpn_browserids['fromip'].append(pre_row['IP'])
                        vpn_browserids['toip'].append(row['IP'])
                        break

                    pre_row = row
                    pre_row['latitude'] = latitude
                    pre_row['longitude'] = longitude


        df = pd.DataFrame.from_dict(vpn_browserids)
        self.db.export_sql(df, 'possiblevpnids')

    def get_vpn_user(self):
        """
        based on speed info and vpn database
        """
        db = Database('ip2proxy')
        vpn_df = db.load_data(table_name = 'ip2proxy_px1')
        ip_from = vpn_df['ip_from']

        df = self.db.load_data(table_name = 'possiblevpnids')
        possible_users = df['browserid'].unique()

        df = self.db.load_data(table_name = 'final_pandas', feature_list = ['IP', 'browserid'])
        grouped = df.groupby('browserid')

        success = set()
        vpn_keys = set()
        for key, cur_group in tqdm(grouped):
            if key in possible_users:
                for ip in cur_group['IP'].unique():
                    int_ip = ip2int(ip)
                    idx = bisect.bisect_left(ip_from, int_ip) - 1
                    if int_ip <= vpn_df.at[idx, 'ip_to']:
                        success.add(key)
                        vpn_keys.add(ip)

        f = safeopen('./res/overspeednotinvpn.dat', 'w')
        f_s = safeopen('./res/vpnusers.dat','w')
        f_ip = safeopen('./res/vpnips.dat', 'w')
        for browserid in possible_users:
            if browserid not in success:
                f.write(browserid + '\n')
            else:
                f_s.write(browserid + '\n')
        for ip in vpn_keys:
            f_ip.write(ip + '\n')
        f.close()
        f_s.close()
        f_ip.close()
        
        print ('We have {} users in total. {} of them are VPN users'.format(len(possible_users), len(success)))

    def get_overall_vpn_user(self):
        db = Database('ip2proxy')
        vpn_df = db.load_data(table_name = 'ip2proxy_px1')
        ip_from = vpn_df['ip_from']

        df = self.db.load_data(table_name = 'final_pandas', feature_list = ['IP', 'browserid'])
        grouped = df.groupby('IP')
        ip_list = df['IP'].unique()

        success_browserid = set()
        for ip in ip_list:
            int_ip = ip2int(ip)
            idx = bisect.bisect_left(ip_from, int_ip) - 1
            if int_ip <= vpn_df.at[idx, 'ip_to']:
                success_browserid |= set(grouped.get_group(ip)['browserid'].unique())
        
        print ('{} of them are VPN users'.format(len(success_browserid)))

    def get_browserid_same_value_order_change(self, feature_name, sep = ','):
        df = self.db.load_data(table_name = 'final_pandas', feature_list = [feature_name, 'browserid'])
        grouped = df.groupby('browserid')
        for key, cur_group in tqdm(grouped):
            if cur_group[feature_name].nunique() == 1:
                continue
            value_list = cur_group[feature_name].unique()
            for cur_feature in value_list:
                for f2 in value_list:
                    if cur_feature == f2:
                        continue
                    cur_feature = cur_feature.replace(' ', '')
                    f2 = f2.replace(' ','')
                    if cur_feature != f2 and len(cur_feature) == len(f2):
                        if len(set(cur_feature.split(sep)) ^ set(f2.split(sep))) == 0:
                            print key
                            return 

