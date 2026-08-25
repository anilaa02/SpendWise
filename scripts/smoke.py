import urllib.request
print('fetching...')
print(urllib.request.urlopen('http://127.0.0.1:5000/').getcode())
print(urllib.request.urlopen('http://127.0.0.1:5000/login').getcode())
