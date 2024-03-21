import requests
import re
import json
import discord
import time

with open('config.json') as f:
    cf = json.load(f)


courseData: dict = cf['courseData']
COURSEIDS = list(courseData.keys())

QUARTERID = cf['quarterId']
# Q1 107015
# Q2 107016
# Q3 107017
# Q4 107018

DEBUG = True

before = {}

WEBHOOK = cf['webhook']
WEBHOOK = discord.webhook.SyncWebhook.from_url(WEBHOOK, session=requests.Session()) # Converts to a webhook object

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
}

params = {
    'client-request-id': 'd9d56afb-4e10-4446-b11a-0040020000db',
}

class BadResponse(Exception):
    pass

def getSAMLCookies(sess: requests.Session) -> requests.Response:
    """ Gets SAML Cookies that are required to make any type of request to the website.
    
    Parameters:
    (requests.Session)sess: A session that will keep track of cookies

    Returns:
    (requests.Response): Returns a response that will be used later in authorization.
    """
    response = sess.get('https://pasco.focusschoolsoftware.com/focus/Modules.php?modname=misc%2FPortal.php', params=params, headers=headers)
    match = re.findall(r'value=\"(.+?)\"', response.text)
    if (not match): # Sometimes when refreshing token it throws an error getting cookies for some reason
        time.sleep(5)
        print("There was a problem getting SAML Cookies... Retrying\nContent: %s" % response.text)
        return getSAMLCookies(sess)
    data = {
        'SAMLRequest': match[0],
        'RelayState': match[1]
    }
    response = sess.post('https://pascosso.pasco.k12.fl.us/adfs/ls/', headers=headers, data=data)
    return response
    





def auth(sess: requests.Session, req1: requests.Response) -> requests.Response:
    """ Logs in using the SAML Cookies with a username and password. This will return a new authorized cookie
    
    Parameters:
    (requests.Session)sess: Session that will keep track of cookies
    (requests.Response)req1: The SAML Cookies request. This is used to extract cookies from the response because it was not adding to the session properly for some reason

    Returns:
    (request.Response): Returns the authorization response. This is primarily used for testing purposes.

    """
    # I Passed the response because for some reason the SAML cookies dont transfer over on the new domain
    data = {
        'UserName': 'district\\%s'  % (cf['studentId']),
        'Password': cf['password'],
        'AuthMethod': 'FormsAuthentication',
    }
    # input(data)
    response = sess.post('https://pascosso.pasco.k12.fl.us/adfs/ls/', params=params, headers=headers, data=data, cookies=req1.cookies)
    # Previous request returns a redirect, below request just goes to the redirect which redirects to another page
    response = sess.get('https://pascosso.pasco.k12.fl.us/adfs/ls/', params=params, headers=headers, cookies=req1.cookies)
    return response

def sendSAMLReq(sess: requests.Session) -> None:
    """ This function does some additional work that will convert the cookie from the pasco website to a cookie that works with focus school software
    
    Parameters:
    (requests.Session)sess: A session that will keep track of cookies
    
    """
    global params
    response = sess.get('https://pasco.focusschoolsoftware.com/focus/index.php', headers=headers)
    match = re.findall(r'value=\"(.+?)\"', response.text)
    data = {
        'SAMLRequest': match[0],
        'RelayState': match[1]
    }
    response = sess.post('https://pascosso.pasco.k12.fl.us/adfs/ls/', params=params, headers=headers, data=data)
    match = re.findall(r'value=\"(.+?)\"', response.text)

    params = {
        'id': 'saml',
    }

    data = {
        'SAMLResponse': match[0],
        'RelayState': match[1],
        "SameSite": 1
    }


    response = sess.post(
        'https://pasco.focusschoolsoftware.com/focus/sso/saml2/acs.php',
        params=params,
        headers=headers,
        data=data,
    )
    response = sess.get("https://pasco.focusschoolsoftware.com/focus/Modules.php?modname=misc%2FPortal.php", headers=headers)


    return response

def sendWebhook(embed: discord.Embed, courseID: int) -> None:
    """ This will take the graded assignment and send it in the discord server 
    
    Parameters:
    (discord.Embed)embed: The embed to send
    (courseID): This will use the course ID to find out what role to ping
    """
    WEBHOOK.send(content=f"<@&{courseData[courseID][0]}>", allowed_mentions=discord.AllowedMentions(roles=True), embed=embed, username="Opportunity", avatar_url="https://cdn.discordapp.com/attachments/891493636611641345/1163987969401688175/NASA_Mars_Rover.jpg?ex=65419345&is=652f1e45&hm=e7a03c4eadedbc69966ab5362ce379b04dfdb6e04f2c4bc3f89dedc2d88e22fb&")

def isBadResponse(payload: str) -> bool:
    """ Checks if a bad response was returned from the server. 
    This usually has to do with a server side error and you can reestablish a new connection to resolve the error
    
    Parameters:
    (str)payload: The payload from the server; Either json or HTML document
    
    Returns:
    (bool): A boolean representing whether or not a bad response was returned from the server
    
    """
    return bool(re.search(r'(An error occurred)|(terminating connection due to administrator command)', payload))

def compareDifferences(payload: str, courseID: int) -> None:
    """ Takes the payload beforehand and the new payload to compare them and determine if an assignment was updated or graded for a certain course.
    
    Parameters
    (str)payload: The new payload
    (int)courseID: The ID of the course currently being examined
    

    Raises:
    (BadResponse): When the server returns a server side error, BadResponse will be raised


    """
    global before
    
    if (isBadResponse(payload)):
        raise BadResponse()
    try:
        data: list = json.loads(payload)[0]['result']['data']
    except:  
        with open("dmp", "w") as f:
            f.write(payload)
            print(f"ERROR OCCURRED: {payload}")
            raise BadResponse()
        
    if (courseID not in before):
        before[courseID] = data
        return
    # input('hi')


    # inp = input(str(courseID))
    # if (inp == "y"):
    #     data.append({
    #         "ASSIGNMENT_TITLE": "Stimulus 8 Annotations",
    #         "PERCENT": "50%",
    #     })
    # elif (inp == "n"):
    #     print("AH")
    #     data.append({
    #         "ASSIGNMENT_TITLE": "Stimulus 8 Annotations",
    #         "PERCENT": "100%",
    #     })
    # Testing ^^^
    if DEBUG:
        with open("dmp", "w") as f: # FOR DEBUGGING
            f.write(payload)

    def getAssignmentData(title: str):
        for item in before[courseID]:
            if (item['ASSIGNMENT_TITLE'] == title):
                return item
        return None
    for assn in data:
        before_assn = getAssignmentData(assn['ASSIGNMENT_TITLE']) # Gets the data with the corrosponding assn title in the before var
        if ((not before_assn and assn['PERCENT']) or (assn['PERCENT'] and not before_assn['PERCENT'])): # Check if assignment exists, if it does then check if it was graded
            # If an assn gets put in WITH a grade (never NG) then check if its not in before and check if it was graded
            print("Assignment graded: %s - %s" % (courseData[courseID][1], assn['ASSIGNMENT_TITLE']))
            embed = discord.Embed(title=f"Assignment in {courseData[courseID][1]} Graded", color=discord.Color.blue(), description=assn['ASSIGNMENT_TITLE'])
            embed.add_field(inline=True, name="Total Points", value=f"{assn['POINTS_POSSIBLE']} Points")
            sendWebhook(embed, courseID)
        elif ((before_assn and before_assn['PERCENT'] and (before_assn['PERCENT'] != 'I' and before_assn['PERCENT'] != "0%")) and assn['PERCENT'] != before_assn['PERCENT']): # Check if the assignment existed beforehand, if it did, check if the grade changed before and after
            print("Assignment updated: %s - %s" % (courseData[courseID][1], assn['ASSIGNMENT_TITLE']))
            embed = discord.Embed(title=f"Assignment in {courseData[courseID][1]} Updated", color=discord.Color.blue(), description=assn['ASSIGNMENT_TITLE'])
            embed.add_field(inline=True, name="Curve", value=f"{float(0 if assn['POINTS_EARNED'] == 'NG' else assn['POINTS_EARNED']) - float(0 if before_assn['POINTS_EARNED'] == 'NG' else before_assn['POINTS_EARNED'])} Points")
            embed.add_field(inline=True, name="Total Points", value=f"{assn['POINTS_POSSIBLE']} Points")
            sendWebhook(embed, courseID)
    
    before[courseID] = data




def checkGrades(sess: requests.Session) -> None:
    """ This is the main function that will get the bigger payload and break it into parts and finally compares the differences to determine if it should send a webhook
    
    Parameters:
    (requests.Session)sess: The session that keeps track of cookies
    
    Returns:
    (bool): A boolean that returns the status of the function being ran. 
        Sometimes this is false when the token is invalid and required it to be refreshed when running for long periods of time

    """
    try:
        response = sess.get(f"https://pasco.focusschoolsoftware.com/focus/Modules.php?modname=Grades/StudentGBGrades.php&force_package=SIS&student_id={cf['studentId']}&course_period_id={COURSEIDS[0]}&side_school=33&side_mp={QUARTERID}", headers=headers)
    except requests.exceptions.ConnectionError:
        print("Connection aborted by host. Retrying...")
        time.sleep(10)
        return checkGrades(sess)
    match = re.findall(r'__Module__\.token = \"(.+?)\"', response.text) # Token works for all courses
    if (match):
        token = match[2]
    else:
        return False
    for courseID in COURSEIDS:
        jwttoken = sess.cookies.get('__session_jwt__')

        params = {
            'modname': 'Grades/StudentGBGrades.php',
            'force_package': 'SIS',
            'student_id': cf['studentId'],
            'course_period_id': courseID,
        }

        headersModWithContentType = {
            'content-type': 'multipart/form-data; boundary=----WebKitFormBoundaryiAidsT13sLafE5Ox',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            # 'authorization': f'Bearer {session_id}',
        }
        data = '------WebKitFormBoundaryiAidsT13sLafE5Ox\r\nContent-Disposition: form-data; name=\"course_period_id\"\r\n\r\n%s\r\n------WebKitFormBoundaryiAidsT13sLafE5Ox\r\nContent-Disposition: form-data; name=\"__call__\"\r\n\r\n{\"requests\":[{\"controller\":\"StudentGBGradesController\",\"method\":\"getGradebookGrid\",\"args\":[%s]}]}\r\n------WebKitFormBoundaryiAidsT13sLafE5Ox\r\nContent-Disposition: form-data; name=\"__token__\"\r\n\r\n%s\r\n------WebKitFormBoundaryiAidsT13sLafE5Ox\r\nContent-Disposition: form-data; name=\"__session_jwt__\"\r\n\r\n%s\r\n------WebKitFormBoundaryiAidsT13sLafE5Ox--\r\n' % (courseID, courseID, token, jwttoken)
        try:
            response = sess.post(
                'https://pasco.focusschoolsoftware.com/focus/classes/FocusModule.class.php',
                params=params,
                headers=headersModWithContentType,
                data=data
            )
        except Exception as e:
            with open("dmp", "w") as f:
                f.write(response.text)
                print(f"ERROR OCCURRED: {response.status_code}, Error: {e}")
        try:
            compareDifferences(response.text, courseID)
        except BadResponse:
            return False
    time.sleep(60)
    return True


def main() -> None:
    sess = requests.Session()
    resp = getSAMLCookies(sess)
    print("Getting SAML Cookies")
    auth(sess, resp)
    print("Logged in...")
    resp = sendSAMLReq(sess)
    print("Sent SAML Cookies, authorization complete")
    print("Monitoring grades")
    while (True):
        flag = checkGrades(sess)
        if (not flag): # Cookie is invalid, refresh the token
            print("Token Invalid. Refreshing token...")
            main()



if __name__ == '__main__':
    main()