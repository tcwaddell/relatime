# Credit to:
#       https://github.com/splunk/eventgen/blob/master/lib/timeparser.py


import datetime
import re
import math
import pytz

def timeParser(ts='now', timezone="UTC", now=None, utcnow=None):
    if ts == 'now':
        return now() if callable(now) else datetime.datetime.now()

    if now == None:
        ret = datetime.datetime.now()
    else:
        ret = now()

    unitsre = "(seconds|second|secs|sec|minutes|minute|min|hours|hour|hrs|hr|days|day|weeks|week|w[0-6]|months|month|mon|quarters|quarter|qtrs|qtr|years|year|yrs|yr|s|h|m|d|w|y|w|q)"
    reltimere = "(?i)(?:(?P<plusminus>[+-]*)(?P<num>\d{1,})(?P<unit>"+unitsre+"{1}))?(([\@](?P<snapunit>"+unitsre+"{1})((?P<snapplusminus>[+-])(?P<snaprelnum>\d+)(?P<snaprelunit>"+unitsre+"{1}))*)*)"

    results = re.match(reltimere, ts)
    resultsdict = results.groupdict()

    if resultsdict['plusminus'] is None and resultsdict['num'] is None and resultsdict['snapunit'] is not None:
        resultsdict['plusminus'] = "-"
        resultsdict['num'] = '0'
        resultsdict['unit'] = resultsdict['snapunit']

    # Handle first part of the time string
    if resultsdict['plusminus'] != None and resultsdict['num'] != None \
            and resultsdict['unit'] != None:
        ret = timeParserTimeMath(resultsdict['plusminus'], resultsdict['num'], resultsdict['unit'], ret)

        # Now handle snap-to
        if resultsdict['snapunit'] != None:
            if resultsdict['snapunit'] in ('s', 'sec', 'secs', 'second', 'seconds'):
                ret = datetime.datetime(ret.year, ret.month, ret.day, ret.hour, \
                                        ret.minute, ret.second, 0)
            elif resultsdict['snapunit'] in ('m', 'min', 'minute', 'minutes'):
                ret = datetime.datetime(ret.year, ret.month, ret.day, ret.hour, \
                                        ret.minute, 0, 0)
            elif resultsdict['snapunit'] in ('h', 'hr', 'hrs', 'hour', 'hours'):
                ret = datetime.datetime(ret.year, ret.month, ret.day, ret.hour, 0, 0, 0)
            elif resultsdict['snapunit'] in ('d', 'day', 'days'):
                ret = datetime.datetime(ret.year, ret.month, ret.day, 0, 0, 0, 0)
            elif re.match('w[0-6]', resultsdict['snapunit']) != None or \
                    resultsdict['snapunit'] in ('w', 'week', 'weeks'):
                if resultsdict['snapunit'] in ('w', 'week', 'weeks'):
                    resultsdict['snapunit'] = 'w0'
                weekdaynum = int(resultsdict['snapunit'][1:2])

                # Convert python's weekdays to Splunk's
                retweekday = datetime.date.weekday(ret)
                if retweekday == 6:
                    retweekday = 0
                else:
                    retweekday += 1

                if weekdaynum <= retweekday:
                    ret = ret + datetime.timedelta(days=(weekdaynum - retweekday))
                    ret = datetime.datetime(ret.year, ret.month, ret.day, 0, 0, 0, 0)
                else:
                    ret = ret - datetime.timedelta(days=7)
                    ret = ret - datetime.timedelta(days=retweekday)
                    ret = ret + datetime.timedelta(days=int(weekdaynum))
                    ret = datetime.datetime(ret.year, ret.month, ret.day, 0, 0, 0, 0)
            # Normalize out all year/quarter/months to months and do the math on that
            elif resultsdict['snapunit'] in ('mon', 'month', 'months'):
                ret = datetime.datetime(ret.year, ret.month, 1, 0, 0, 0, 0)
            elif resultsdict['snapunit'] in ('q', 'qtr', 'qtrs', 'quarter', 'quarters'):
                ret = datetime.datetime(ret.year, (math.floor(ret.month / 3) * 3), 1, 0, 0, 0, 0)
            elif resultsdict['snapunit'] in ('y', 'yr', 'yrs', 'year', 'years'):
                ret = datetime.datetime(ret.year, 1, 1, 0, 0, 0, 0)

            if resultsdict['snapplusminus'] != None and resultsdict['snaprelnum'] != None \
                    and resultsdict['snaprelunit'] != None:
                ret = timeParserTimeMath(resultsdict['snapplusminus'], resultsdict['snaprelnum'],
                                        resultsdict['snaprelunit'], ret)
        ret = pytz.timezone(timezone).localize(ret)
        return ret

    else:
        raise ValueError('Cannot parse relative time string for %s' %(ts))

def timeParserTimeMath(plusminus, num, unit, ret):
    try:
        num = int(num)
        td = None
        if unit in ('s', 'sec', 'secs', 'second', 'seconds'):
            td = datetime.timedelta(seconds=int(num))
        elif unit in ('m', 'min', 'minute', 'minutes'):
            td = datetime.timedelta(minutes=int(num))
        elif unit in ('h', 'hr', 'hrs', 'hour', 'hours'):
            td = datetime.timedelta(hours=int(num))
        elif unit in ('d', 'day', 'days'):
            td = datetime.timedelta(days=int(num))
        elif unit in ('w', 'week', 'weeks'):
            td = datetime.timedelta(days=(int(num)*7))
        elif re.match('w[0-6]', unit) != None:
            return False
        # Normalize out all year/quarter/months to months and do the math on that
        elif unit in ('mon', 'month', 'months') or \
                    unit in ('q', 'qtr', 'qtrs', 'quarter', 'quarters') or \
                    unit in ('y', 'yr', 'yrs', 'year', 'years'):
            if unit in ('q', 'qtr', 'qtrs', 'quarter', 'quarters'):
                num *= 3
            elif unit in ('y', 'yr', 'yrs', 'year', 'years'):
                num *= 12

            monthnum = int(num) * -1 if plusminus == '-' else int(num)
            if abs(monthnum) / 12 > 0:
                yearnum = int(math.floor(abs(monthnum)/12) * -1 if plusminus == '-' else int(math.floor(abs(monthnum)/12)))
                monthnum = int((abs(monthnum) % 12) * -1 if plusminus == '-' else int((abs(monthnum)%12)))
                ret = datetime.datetime(ret.year + yearnum, ret.month + monthnum, ret.day, ret.hour,
                                        ret.minute, ret.second, ret.microsecond)
            elif monthnum > 0:
                if ret.month + monthnum > 12:
                    ret = datetime.datetime(ret.year+1, ((ret.month+monthnum)%12),
                                            ret.day, ret.hour, ret.minute, ret.second, ret.microsecond)
                else:
                    ret = datetime.datetime(ret.year, ret.month+monthnum, ret.day,
                                            ret.hour, ret.minute, ret.second, ret.microsecond)
            elif monthnum <= 0:
                if ret.month + monthnum <= 0:
                    ret = datetime.datetime(ret.year-1, (12-abs(ret.month+monthnum)),
                                            ret.day, ret.hour, ret.minute, ret.second, ret.microsecond)
                else:
                    ret = datetime.datetime(ret.year, ret.month+monthnum, ret.day,
                                            ret.hour, ret.minute, ret.second, ret.microsecond)

    except ValueError:
        return False

    if td != None:
        if plusminus == '-':
            td = td * -1
        ret = ret + td

    # Always chop microseconds to maintain compatibility with Splunk's parser
    ret = datetime.datetime(ret.year, ret.month, ret.day, ret.hour, ret.minute, ret.second)

    return ret

## Converts Time Delta object to number of seconds in delta
def timeDelta2secs(timeDiff):
    deltaSecs = (timeDiff.microseconds + (timeDiff.seconds + timeDiff.days * 24 * 3600) * 10**6) / 10**6
    return int(deltaSecs)
