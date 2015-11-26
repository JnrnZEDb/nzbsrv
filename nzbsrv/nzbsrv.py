""" nzbsrv: Simple web server to list and download movies from RSS feed of NZB indexes
	It grabs some info about the movie, like poster and imdb link.
	It provides Download and Ignore buttons.
		- Download will download the .nzb in a folder, so that sabnzbs or other can start downloading it.
		- Ignore will mark the movie as ignore so it won't show up again.
"""

import json
import time
import threading
import SimpleHTTPServer
import SocketServer
import urllib2
import urllib
import urlparse
import copy
import base64
import os
import sys
import traceback
from datetime import datetime, timedelta

import mtwr
import nzbconfig


#
# Shared between monitor and http server
# The feed monitor runs in another thread, so that displaying the web page is instantaneous
#

shared_monitor_data = ''
shared_monitor_lock = threading.Lock()

def read_monitor_data():
	global shared_monitor_data
	shared_monitor_lock.acquire()
	data = copy.deepcopy(shared_monitor_data)
	shared_monitor_lock.release()
	return data

def write_monitor_data(data):
	global shared_monitor_data
	shared_monitor_lock.acquire()
	shared_monitor_data = data
	shared_monitor_lock.release()


#
# HTTP server request handler
#

class NZBRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
	def do_GET(self): # NOQA
		# Ignore favicon
		if self.path == '/favicon.ico':
			return

		# Images
		if self.path.startswith('/data'):
			self.serve_image()
			return

		# Download the nzb on the local machine
		if self.path.startswith('/getnzb'):
			self.download_nzb()
			return

		# Ignore this movie title (store the name in the ignore list file)
		if self.path.startswith('/ignore'):
			self.ignore_movie()
			return

		# List releases
		self.list_movies()

	def serve_image(self):
		data = None
		with open(self.path[1:], 'rb') as f:
			data = f.read()

		if data:
			self.send_response(200)
			self.send_header("Content-type", "image/jpeg")
			self.send_header("Cache-Control", "public,max-age=%s" % 32000000)
			self.send_header("Expires", (datetime.utcnow() + timedelta(seconds=32000000)).strftime("%d %b %Y %H:%M:%S GMT"))
			self.end_headers()
			self.wfile.write(data)
		else:
			self.send_response(404)

	def download_nzb(self):
		# Download the nzb
		nzb_url = urllib.unquote(self.path.replace('/getnzb/', ''))
		remotefile = urllib2.urlopen(nzb_url)
		filename = remotefile.info()['Content-Disposition'].split('filename=')[1]
		with open(os.path.join(nzbconfig.nzb_download_path, filename.replace('"', '')), 'wb') as f:
			f.write(remotefile.read())

		# Keep track of it to color download buttons
		parsed = urlparse.urlparse(nzb_url)
		params = urlparse.parse_qs(parsed.query)
		nzb_id = params['id'][0]
		with open('data/dlhistory.txt', 'a') as f:
			f.write(nzb_id + '\n')

		self._write_response('Downloaded %s' % filename)

	def ignore_movie(self):
		title = urllib.unquote(self.path.replace('/ignore/', ''))
		with open('data/dlignore.txt', 'a') as f:
			f.write(title + '\n')

	def list_movies(self):
		self._write_response(read_monitor_data())

	def _write_response(self, response):
		self.send_response(200)
		self.send_header("Content-type", "text/html")
		self.end_headers()
		self.wfile.write(response)

#
# Utils
#

def natural_time_since(value):
	if isinstance(value, datetime):
		delta = datetime.now() - value
		if delta.days > 6:
			return value.strftime("%b %d")
		if delta.days > 1:
			return str(delta.days) + ' days ago'
		if delta.seconds > 7200:
			return str(delta.seconds / 3600) + ' hours ago'
		if delta.seconds > 3600:
			return '1 hour ago'
		if delta.seconds > 120:
			return str(delta.seconds / 60) + ' minutes ago'
		return 'just now'


#
# Monitor feeds and generate html
#

def start_feed_monitor():
	while (True):
		data = []
		try:
			feeds = mtwr.request_urls(nzbconfig.feed_urls, timeout=30)
			for response in feeds.values():
				data += json.loads(response)
			print 'Feed just fetched %d elements' % len(data)
		except Exception:
			traceback_message = ''.join(traceback.format_exception(*sys.exc_info()))
			print traceback_message

		html = update_feed(data)
		write_monitor_data(html)

		# Sleep by increments of 1 second to catch the keyboard interrupt
		for i in range(nzbconfig.monitor_interval):
			time.sleep(1)

def update_feed(nzbs):
	nzbs = prepare_nzbs(nzbs)
	urls, url_response_cache = get_imdb_urls(nzbs)
	imdb_results = get_imdb_results(urls, url_response_cache)
	insert_imdb_info(nzbs, imdb_results)
	nzbs = remove_ignored_nzbs(nzbs)
	download_images(nzbs)
	downloaded_nzbs_ids = get_downloaded_nzbs_ids()
	html_response = render_template(nzbs, downloaded_nzbs_ids, )
	print 'Feed update done.'
	return html_response

def prepare_nzbs(nzbs):
	# Since we get data from multiple urls, we need to sort by date
	nzbs.sort(key=lambda nzb: nzb['usenetage'], reverse=True)

	# Keep the 200 most recent
	nzbs = nzbs[:200]

	# Get the imdb info urls
	for nzb in nzbs:
		if nzb['weblink'].find('/title/') != -1:
			imdb_id = nzb['weblink'].split('/title/')[1].replace('/', '')
			nzb['imdb_id'] = imdb_id
			nzb['imdb_info_url'] = 'http://www.omdbapi.com/?i=%s' % imdb_id

	return nzbs

def get_imdb_urls(nzbs):
	# Make a unique list of imdb api urls
	urls = [nzb['imdb_info_url'] for nzb in nzbs if 'imdb_info_url' in nzb]
	urls = list(set(urls))

	# Checking our local imdb cache
	cached_results = {}
	for url in urls:
		cached_filename = 'data/imdbapi/' + base64.urlsafe_b64encode(url)
		if os.path.exists(cached_filename):
			with open(cached_filename) as f:
				cached_results[url] = f.read()

	# Removed urls for which we have cached data
	urls = [url for url in urls if url not in cached_results]
	return urls, cached_results

def get_imdb_results(urls, url_response_cache):
	# Multi-threaded fetch of imdb info (if not already cached)
	imdb_results = mtwr.request_urls(urls, timeout=30) if urls else {}
	imdb_results.update(url_response_cache)
	return imdb_results

def insert_imdb_info(nzbs, imdb_results):
	for nzb in nzbs:
		if 'imdb_info_url' in nzb:
			url_data = imdb_results[nzb['imdb_info_url']]

			# Cache on the disk
			cached_filename = 'data/imdbapi/' + base64.urlsafe_b64encode(nzb['imdb_info_url'])
			if not os.path.exists(cached_filename):
				with open(cached_filename, 'w') as f:
					f.write(url_data)

			try:
				imdb_info = json.loads(url_data)
				if 'Poster' in imdb_info and imdb_info['Poster'] != 'N/A':
					nzb['poster_url'] = imdb_info.get('Poster', '')
					nzb['poster_path'] = 'data/' + nzb['poster_url'].split('/')[-1]
					nzb['title'] = imdb_info.get('Title', '')
					nzb['year'] = imdb_info.get('Year', '')
					nzb['actors'] = imdb_info.get('Actors')
					nzb['rating'] = imdb_info.get('imdbRating', '')
			except Exception as e:
				print 'Error loading imdb info: ' + str(e)

def remove_ignored_nzbs(nzbs):
	# Get list of ignored movie titles so we don't display them
	ignored_nzbs = []
	if os.path.exists('data/dlignore.txt'):
		with open('data/dlignore.txt') as f:
			ignored_nzbs = f.read().split('\n')

	# Remove ignored movies and the ones without a poster
	nzbs = [nzb for nzb in nzbs if 'poster_url' in nzb and nzb['title'] not in ignored_nzbs]
	return nzbs

def download_images(nzbs):
	# Multi-threaded fetch of poster urls and caching of the images (if not already cached)
	urls = [nzb['poster_url'] for nzb in nzbs if 'poster_url' in nzb and not os.path.exists(nzb['poster_path'])]
	if urls:
		results = mtwr.request_urls(urls, timeout=30)
		for url, url_data in results.iteritems():
			filename = 'data/' + url.split('/')[-1]
			with open(filename, 'wb') as f:
				f.write(url_data)

def get_downloaded_nzbs_ids():
	# Get list of dled nzb ids for buttons style
	downloaded_nzbs_ids = []
	if os.path.exists('data/dlhistory.txt'):
		with open('data/dlhistory.txt') as f:
			downloaded_nzbs_ids = f.read().split('\n')
	return downloaded_nzbs_ids

def render_template(nzbs, downloaded_nzbs_ids):
	# Generate html list
	html_output = ''
	for nzb in nzbs[:50]:
		if '720p' in nzb['release']:
			resolution = '720p'
		elif '1080p' in nzb['release']:
			resolution = '1080p'
		elif '480p' in nzb['release']:
			resolution = '480p'
		else:
			resolution = '???p'
		if '3D' in nzb['release']:
			resolution += ' 3D'

		if nzb['nzbid'] not in downloaded_nzbs_ids:
			class_name = 'dlbutton'
			disabled = ''
		else:
			class_name = 'dlbuttongreyed'
			disabled = 'disabled="disabled"'

		title = nzb['title'].encode('ascii', errors='ignore')
		html_output += ("""
			<tr><td style="border-top:1px solid #dddddd; text-align:center; padding-bottom:15px;">
				<span style="font-weight:bold; font-size:x-large;">{} ({})</span><br>
				<img height="400" src="/{}"><br>
				<a target="_blank" href="{}">IMDB</a> | Rating: {} | {} | {} GB | {}<br>
				Actors: {}<br>
				<span onclick="download(this)" nzburl="{}" class="{}" {}>DOWNLOAD</span>
				<span onclick="ignoretitle(this)" nzbtitle="{}" class="dlbutton">IGNORE</span><br>
			</td></tr>
			""").format(
				title,
				nzb['year'].encode('ascii', errors='ignore'),
				nzb['poster_path'],
				nzb['weblink'],
				nzb['rating'],
				resolution,
				int(nzb['sizebytes']) / 1073741824,
				natural_time_since(datetime.fromtimestamp(float(nzb['usenetage']))),
				nzb['actors'].encode('ascii', errors='ignore')[:42] + '...',
				'/getnzb/' + urllib.quote(nzb['getnzb']),
				class_name,
				disabled,
				urllib.quote(title),
		)

	# Final html
	html_template = ''
	with open('nzblist.tpl') as f:
		html_template = f.read()

	return html_template.replace('{{content}}', html_output)


#
# usage: nzbsrv.py
# Press CTRL+C to stop.
#

if __name__ == "__main__":
	try:
		server = SocketServer.TCPServer((nzbconfig.server_interface, nzbconfig.server_port), NZBRequestHandler)
		threading.Thread(target=server.serve_forever).start()
		start_feed_monitor()
	except KeyboardInterrupt:
		server.shutdown()
	except Exception:
		traceback_message = ''.join(traceback.format_exception(*sys.exc_info()))
		print traceback_message
