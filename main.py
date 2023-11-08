import requests
import re
import json
import discord
import time

with open('config.json') as f:
    cf = json.load(f)


courseData: dict = cf['courseData']
COURSEIDS = list(courseData.keys())

# courseData = { # Testing
#     1024509: ("https://discord.com/api/webhooks/1142633545886597266/kFekjeC9Dk0Cq3Tjrhev4QrpbTPFRLtiEv_VtuGmfOls7wZFs0cHOIwpD1ouhMgVqRBX", "AP Seminar"), # General
#     1024569: ("https://discord.com/api/webhooks/1142633545886597266/kFekjeC9Dk0Cq3Tjrhev4QrpbTPFRLtiEv_VtuGmfOls7wZFs0cHOIwpD1ouhMgVqRBX", "AP Chemistry"), # Chem
#     1028258: ("https://discord.com/api/webhooks/1142633545886597266/kFekjeC9Dk0Cq3Tjrhev4QrpbTPFRLtiEv_VtuGmfOls7wZFs0cHOIwpD1ouhMgVqRBX", "AP Physics C"), # Physics
#     1025433: ("https://discord.com/api/webhooks/1142633545886597266/kFekjeC9Dk0Cq3Tjrhev4QrpbTPFRLtiEv_VtuGmfOls7wZFs0cHOIwpD1ouhMgVqRBX", "APUSH")} # General

QUARTERID = cf['quarterId']
# Q1 107015
# Q2 107016
# Q3 107017
# Q4 107018


before = {}

WEBHOOK = cf['webhook']
WEBHOOK = discord.webhook.SyncWebhook.from_url(WEBHOOK, session=requests.Session()) # Converts to a webhook object

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
}

params = {
    'client-request-id': 'dc05ce4b-7249-4891-6f47-0040010000d9',
}

def getSAMLCookies(sess: requests.Session):
    response = sess.get('https://pasco.focusschoolsoftware.com/focus/Modules.php?modname=misc%2FPortal.php', params=params, headers=headers)
    match = re.findall(r'value=\"(.+?)\"', response.text)
    data = {
        'SAMLRequest': match[0],
        'RelayState': match[1]
    }
    response = sess.post('https://pascosso.pasco.k12.fl.us/adfs/ls/', headers=headers, data=data)
    return response
    





def auth(sess: requests.Session, req1: requests.Response):
    # I Passed the response because for some reason the SAML cookies dont transfer over on the new domain
    data = {
        'UserName': 'district\\%s'  % (cf['studentId']),
        'Password': cf['password'],
        'AuthMethod': 'FormsAuthentication',
    }
    response = sess.post('https://pascosso.pasco.k12.fl.us/adfs/ls/', params=params, headers=headers, data=data, cookies=req1.cookies)
    # Previous request returns a redirect, below request just goes to the redirect which redirects to another page
    response = sess.get('https://pascosso.pasco.k12.fl.us/adfs/ls/', params=params, headers=headers, cookies=req1.cookies)
    return response

def sendSAMLReq(sess: requests.Session):
    response = sess.get('https://pasco.focusschoolsoftware.com/focus/index.php', headers=headers)
    match = re.findall(r'value=\"(.+?)\"', response.text)
    data = {
        'SAMLRequest': match[0],
        'RelayState': match[1]
    }
    response = sess.post('https://pascosso.pasco.k12.fl.us/adfs/ls/?client-request-id=554fd3f0-9920-486a-9355-0040000000b8', headers=headers, data=data)
    match = re.findall(r'value=\"(.+?)\"', response.text)
    sess.get('https://pascosso.pasco.k12.fl.us/adfs/ls/', headers=headers)

    params = {
        'id': 'saml',
    }

    data = {
        'SAMLResponse': match[0],
        'RelayState': match[1]
    }


    response = sess.post(
        'https://pasco.focusschoolsoftware.com/focus/sso/saml2/acs.php',
        params=params,
        headers=headers,
        data=data,
    )
    response = sess.get("https://pasco.focusschoolsoftware.com/focus/Modules.php?modname=misc%2FPortal.php", headers=headers)


    return response

def sendWebhook(embed: discord.Embed, courseID: int):
    WEBHOOK.send(content=f"<@&{courseData[courseID][0]}>", allowed_mentions=discord.AllowedMentions(roles=True), embed=embed, username="Opportunity", avatar_url="https://cdn.discordapp.com/attachments/891493636611641345/1163987969401688175/NASA_Mars_Rover.jpg?ex=65419345&is=652f1e45&hm=e7a03c4eadedbc69966ab5362ce379b04dfdb6e04f2c4bc3f89dedc2d88e22fb&")

def compareDifferences(payload: str, courseID: int):
    global before
    try:
        data: list = json.loads(payload)[0]['result']['data']
    except:  
        with open("dmp", "w") as f:
            f.write(payload)
            print(f"ERROR OCCURRED: {payload}")
        
    if (courseID not in before):
        before[courseID] = data
        return
    import pyperclip
    pyperclip.copy(payload)
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
        elif ((before_assn and before_assn['PERCENT']) and assn['PERCENT'] != before_assn['PERCENT']): # Check if the assignment existed beforehand, if it did, check if the grade changed before and after
            print("Assignment updated: %s - %s" % (courseData[courseID][1], assn['ASSIGNMENT_TITLE']))
            embed = discord.Embed(title=f"Assignment in {courseData[courseID][1]} Updated", color=discord.Color.blue(), description=assn['ASSIGNMENT_TITLE'])
            embed.add_field(inline=True, name="Curve", value=f"{float(0 if assn['POINTS_EARNED'] in ['I', 'NG'] else assn['POINTS_EARNED']) - float(0 if before_assn['POINTS_EARNED'] in ['I', 'NG'] else before_assn['POINTS_EARNED'])} Points")
            embed.add_field(inline=True, name="Total Points", value=f"{assn['POINTS_POSSIBLE']} Points")
            sendWebhook(embed, courseID)
    
    before[courseID] = data




def checkGrades(sess: requests.Session):
    response = sess.get(f"https://pasco.focusschoolsoftware.com/focus/Modules.php?modname=Grades/StudentGBGrades.php&force_package=SIS&student_id={cf['studentId']}&course_period_id={COURSEIDS[0]}&side_school=33&side_mp={QUARTERID}", headers=headers)
    match = re.findall(r'__Module__\.token = \"(.+?)\"', response.text) # Token works for all courses
    if (match):
        token = match[2]
    else:
        return False
    for courseID in COURSEIDS:
        # response = sess.get(f"https://pasco.focusschoolsoftware.com/focus/Modules.php?modname=Grades/StudentGBGrades.php&force_package=SIS&student_id=511444&course_period_id={courseID}&side_school=33&side_mp=107016", headers=headers)
        # match = re.findall(r'__Module__\.token = \"(.+?)\"', response.text)
        # token = match[2]
        jwttoken = sess.cookies.get('__session_jwt__')
        sess.get('https://pasco.focusschoolsoftware.com/focus/assets/translations/gettext.js.php?locale=en_US&m=1697492306?m=', headers=headers)
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
        except:
            with open("dmp", "w") as f:
                f.write(response.text)
                print(f"ERROR OCCURRED: {response.status_code}")
        compareDifferences(response.text, courseID)
    time.sleep(60)
    return True


def main():
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