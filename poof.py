import os
import urllib
import urllib2
import getpass
import sys
import base64
import plistlib
import traceback
import json
import time

def getUDID(dsid, mmeFMFAppToken):
    url = 'https://p04-fmfmobile.icloud.com/fmipservice/friends/%s/1/maxCallback/refreshClient' % dsid
    headers = {
        'Authorization': 'Basic %s' % base64.b64encode("%s:%s" % (dsid, mmeFMFAppToken)), #FMF APP TOKEN
        'Content-Type': 'application/json; charset=utf-8',
    }
    data = {
        "clientContext": {
            "appVersion": "5.0" #Critical for getting appropriate config/time
        }
    }
    jsonData = json.dumps(data)
    request = urllib2.Request(url, jsonData, headers)
    i = 0
    while 1:
        try:
            response = urllib2.urlopen(request)
            break
        except: #This exception needs to be caught a bunch of times before the request is made
            i +=1
            continue
    x = json.loads(response.read())
    try:
        UDID = base64.b64decode(x["devices"][0]["id"].replace("~", "="))
    except Exception, e:
        #If an error is thrown, the user will have to manually confirm their UDID
        UDID = (False, False)
    return (UDID, x["devices"][0]["name"])

def tokenFactory(dsid, mmeAuthToken):
    mmeAuthTokenEncoded = base64.b64encode("%s:%s" % (dsid, mmeAuthToken))
    #Now that we have proper Auth code, we will attempt to get all account tokens
    url = "https://setup.icloud.com/setup/get_account_settings"
    headers = {
        'Authorization': 'Basic %s' % mmeAuthTokenEncoded,
        'Content-Type': 'application/xml',
        'X-MMe-Client-Info': '<iPhone6,1> <iPhone OS;9.3.2;13F69> <com.apple.AppleAccount/1.0 (com.apple.Preferences/1.0)>'
    }

    request = urllib2.Request(url, None, headers)
    response = None
    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        if e.code != 200:
            return "HTTP Error: %s" % e.code
        else:
            print e
            raise HTTPError
    #Staple it together
    content = response.read()
    mmeFMFAppToken = plistlib.readPlistFromString(content)["tokens"]["mmeFMFAppToken"]
    mmeFMIToken = plistlib.readPlistFromString(content)["tokens"]["mmeFMIPToken"]
    return (mmeFMFAppToken, mmeFMIToken)

def dsidFactory(uname, passwd): #This can also be a regular DSID with AuthToken
    creds = base64.b64encode("%s:%s" % (uname, passwd))
    url = "https://setup.icloud.com/setup/authenticate/%s" % uname
    headers = {
        'Authorization': 'Basic %s' % creds,
        'Content-Type': 'application/xml',
    }

    request = urllib2.Request(url, None, headers)
    response = None
    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        if e.code != 200:
            if e.code == 401:
                return "HTTP Error 401: Unauthorized. Are you sure the credentials are correct?"
            elif e.code == 409:
                return "HTTP Error 409: Conflict. Two-Factor Authentication appears to be enabled. You cannot use this script unless you get your MMeAuthToken manually (generated either on your PC/Mac or on your iOS device)."
            elif e.code == 404:
                return "HTTP Error 404: URL not found. Did you enter a username?"
            else:
                return "HTTP Error %s.\n" % e.code
        else:
            print e
            raise HTTPError
    content = response.read()
    DSID = int(plistlib.readPlistFromString(content)["appleAccountInfo"]["dsPrsID"]) #Stitch our own auth DSID
    mmeAuthToken = plistlib.readPlistFromString(content)["tokens"]["mmeAuthToken"] #Stitch with token
    return (DSID, mmeAuthToken)

def convertAddress(street, city, state):
    street = street.replace(" ", "+") #Replace all spaces with a +
    city = city.replace(" ", "+")
    url = "http://maps.google.com/maps/api/geocode/json?address=%s,+%s+%s" % (street, city, state)
    headers = {
        'Content-Type': 'application/json',
    }
    request = urllib2.Request(url, None, headers)
    response = None
    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        if e.code != 200:
            return "HTTP Error: %s" % e.code
        else:
            print e
            raise HTTPError
    coords = json.loads(response.read())["results"][0]["geometry"]["location"]
    return (coords["lat"], coords["lng"])

def fmiSetLoc(DSID, mmeFMIToken, UDID, latitude, longitude):
    mmeFMITokenEncoded = base64.b64encode("%s:%s" % (DSID, mmeFMIToken))
    url = 'https://p04-fmip.icloud.com/fmipservice/findme/%s/%s/currentLocation' % (DSID, UDID)
    headers = {
        'Authorization': 'Basic %s' % mmeFMITokenEncoded,
        'X-Apple-PrsId': '%s' % DSID,
        'Accept-Encoding': 'gzip, deflate',
        'Accept': '*/*',
        'Content-Type': 'application/json',
        'Accept-Language': 'en-us',
        'User-Agent': 'FMDClient/6.0 iPhone6,1/13F69',
        'X-Apple-Find-API-Ver': '6.0',
    }
    data = {
        "locationFinished": False,
        "deviceInfo": {
            "batteryStatus": "NotCharging",
            "udid": UDID,
            "batteryLevel": 0.50, #(Arbitrary number)
            "isChargerConnected": False
        },
        "longitude": longitude,
        "reason": 1,
        "horizontalAccuracy": 65,
        "latitude": latitude,
        "deviceContext": {
        },
    }
    jsonData = json.dumps(data)
    request = urllib2.Request(url, jsonData, headers)
    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        if e.code != 200:
            return "Error changing FindMyiPhone location, status code <%s>." % e.code
        else:
            print e
            raise HTTPError
    return "Successfully changed FindMyiPhone location to <%s;%s>." % (latitude, longitude)
    
def fmfSetLoc(DSID, mmeFMFAppToken, UDID, latitude, longitude): #UDID has to be determined manually as it isn't stored by Apple
    mmeFMFAppTokenEncoded = base64.b64encode("%s:%s" % (DSID, mmeFMFAppToken))
    url = 'https://p04-fmfmobile.icloud.com/fmipservice/friends/%s/%s/myLocationChanged' % (DSID, UDID)
    headers = {
        'host': 'p04-fmfmobile.icloud.com',
        'Authorization': 'Basic %s' % mmeFMFAppTokenEncoded,
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': '*/*',
        'User-Agent': 'FindMyFriends/5.0 iPhone6,1/9.3.2(13F69)',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-us',
        'X-Apple-Find-API-Ver': '2.0',
        'X-Apple-AuthScheme': 'Forever',
    }
    data = {
        "serverContext": {
            "authToken": "%s" % mmeFMFAppToken,
            "prsId": DSID,
        },
        "clientContext": {
            "appName": "FindMyFriends", #Needed for proper server response
            "appVersion": "5.0", #Needed for proper server response
            "userInactivityTimeInMS": 5,
            "deviceUDID": "%s" % UDID,
            "location": {
                "altitude": 57, #Arbitrary number
                "longitude": "%s" % longitude,
                "source": "app",
                "horizontalAccuracy": 1.0, #Perfect horizontal accuracy
                "latitude": "%s" % latitude,
                "speed": -1,
                "verticalAccuracy": 1.0 #Perfect vertical accuracy
            }
        }
    }
    jsonData = json.dumps(data)
    request = urllib2.Request(url, jsonData, headers)
    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        if e.code != 200:
            return "Error changing FindMyFriends location, status code <%s>." % e.code
        else:
            print e
            raise HTTPError
    return "Successfully changed FindMyFriends location to <%s;%s>." % (latitude, longitude)

if __name__ == '__main__':
    os.system('cls' if os.name == 'nt' else 'clear') #Clear console window
    user = raw_input("Apple ID: ")
    try: #If DSID fetched, convert to int
        int(user)
        user = int(user)
    except ValueError: #Else (Apple ID) = not convertible
        pass
    passw = getpass.getpass()
    try:
        (DSID, authToken) = dsidFactory(user, passw)
        print "Succesfully authenticated to iCloud: fetched DSID/MMeAuthToken [%s:%s]." % (DSID, authToken)
    except:
        print "Error fetching DSID and MMeAuthToken!\n%s" % dsidFactory(user, passw)
        sys.exit()
    while True:
        try:
            arg = int(raw_input("Would you like to use GPS coordinates [1] or a street address [2]: "))
            if not (1 <= arg <= 2):
                raise ValueError()
            break
        except ValueError:
            print "Please enter 1 or 2 (GPS coordinates, or street address)"
            continue
    latitude, longitude, street, city, state = (None, None, None, None, None)
    if arg == 1:
        latitude = raw_input("Latitude: ")
        longitude = raw_input("Longitude: ")
    if arg == 2:
        street = raw_input("Street address: ")
        city = raw_input("City: ")
        state = raw_input("State: ")
        (latitude, longitude) = convertAddress(street, city, state)
        print "Got GPS coordinates <%s:%s> for %s, %s, %s" % (latitude, longitude, street, city, state)

    while True:
        try:
            serviceSelect = int(raw_input("Spoof FMF, FMI or both: [0, 1, 2] "))
            if not (0 <= serviceSelect <= 2):
                raise ValueError()
            break
        except ValueError:
            print "Please enter 0, 1 or 2 (FMF, FMI or both, respectively)"
            continue

    try:
        mmeFMFAppToken, mmeFMIToken = tokenFactory(DSID, authToken) #Get tokens by using token
    except Exception as e:
        print "Error getting FMF/FMI tokens!\n%s" % e #0 is the FMFAppToken
        traceback.print_exc()
        sys.exit()
    print "Attempting to find UDID's for devices registrated on this iCloud account..."
    UDID = getUDID(DSID, mmeFMFAppToken)
    if UDID[0] != False:
        print "Found UDID [%s] for device [%s]" % (UDID[0], UDID[1])
        confirm = raw_input("Do you want to spoof this device? [y/n] ")
        if confirm == "y" or confirm == "Y" or confirm == "yes" or confirm == "Yes":
            UDID = UDID[0]
        else:
            UDID = raw_input("Manually enter UDID: ")

    else:
        print "Could not fetch any UDID."
        UDID = raw_input("Manually enter UDID: ")

    try:
        while True:
            if serviceSelect == 0 or serviceSelect == 1 or serviceSelect == 2:
                if serviceSelect == 0: #FMF
                    print fmfSetLoc(DSID, mmeFMFAppToken, UDID, latitude, longitude)
                    print "Waiting 5 seconds to send FMF spoof again."
                    time.sleep(5)
                elif serviceSelect == 1: #FMI
                    print fmiSetLoc(DSID, mmeFMIToken, UDID, latitude, longitude)
                    print "Waiting 5 seconds to send FMI spoof again."
                    time.sleep(5)
                else: #FMF/FMI
                    print fmiSetLoc(DSID, mmeFMIToken, UDID, latitude, longitude)
                    print fmfSetLoc(DSID, mmeFMFAppToken, UDID, latitude, longitude)
                    print "Waiting 5 seconds to send FMI/FMF spoof again."
                    time.sleep(5)
            else:
                print "Service select must have a value of 0, 1, or 2."
    except KeyboardInterrupt:
        print "Terminate signal received: spoof stopped."
    except Exception as e:
        print e
        print traceback.print_exc()
        sys.exit()
