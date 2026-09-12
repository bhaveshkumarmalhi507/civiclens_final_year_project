import firebase_admin
from firebase_admin import credentials
cred = credentials.Certificate("D:\\Civiclens\\Backend\\app\\civiclens-dbc4a-firebase-adminsdk-fbsvc-7a24c164d1.json")
firebase_admin.initialize_app(cred)