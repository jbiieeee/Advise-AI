import os
import django
import json
from django.test import Client, RequestFactory
from django.contrib.auth.models import User

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def test_chatbot_api():
    client = Client()
    user = User.objects.get(username='ai_test_student')
    client.force_login(user)
    
    response = client.post('/api/chatbot/', 
                           data=json.dumps({'message': 'What is my program?'}),
                           content_type='application/json')
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == '__main__':
    test_chatbot_api()
