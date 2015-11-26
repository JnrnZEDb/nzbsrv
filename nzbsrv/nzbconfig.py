""" Config for nzbsrv
"""

# Use your own credentials, keep empty if not needed
rss_username = 'YourUsername'
rss_api_key = 'YourApiKeyOrPassword'

nzb_download_path = 'C:/Your/Download/Path'

feed_urls = [
	'https://api.*****.org/json/?search=2013&catid=16&user=%s&api=%s&eng=1' % (rss_username, rss_api_key),
	'https://api.*****.org/json/?search=2014&catid=16&user=%s&api=%s&eng=1' % (rss_username, rss_api_key),
	'https://api.*****.org/json/?search=2015&catid=16&user=%s&api=%s&eng=1' % (rss_username, rss_api_key),
]

monitor_interval = 900 # 15 minutes, don't get banned from your index

server_interface = '0.0.0.0'
server_port = 8080
