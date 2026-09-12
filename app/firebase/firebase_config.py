import firebase_admin
from firebase_admin import credentials
cred = credentials.Certificate("D:\\Civiclens\\Backend\\app\\civiclens-dbc4a-firebase-adminsdk-fbsvc-aa5a0f592e.json")
firebase_admin.initialize_app(cred)