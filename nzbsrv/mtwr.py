#!/usr/bin/env python
#
# mtwr - Multi-Threaded Web Requests
# Romain Dura | romain@shazbits.com
# https://github.com/shazbits/mtwr
#
# Copyright (c) 2013, Romain Dura romain@shazbits.com
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#

import threading
import Queue
import urllib2
import socket

class URLRequestThread(threading.Thread):
	def __init__(self, queue, url, timeout=None):
		self.queue = queue
		self.url = url
		self.timeout = timeout
		threading.Thread.__init__(self)

	def run(self):
		response = urllib2.urlopen(self.url, timeout=self.timeout)
		data = response.read()
		self.queue.put((self.url, data))

def request_urls(urls, timeout=None, force_ipv4=False):
	"""Executes http, https, ftp requests in parallel and returns a dictionary
	containing urls as keys and response data as values.

	It can happen that using IPv6, socket.connect can timeout,
	to avoid slow requests we can force IPv4.

	The function blocks until all responses have been received.
	The bottleneck is the slowest request.
	"""

	if force_ipv4:
		orig_getaddrinfo = socket.getaddrinfo

		def getaddrinfo_ipv4(host, port, family=0, socktype=0, proto=0, flags=0):
			return orig_getaddrinfo(host, port, socket.AF_INET, socktype, proto, flags)
		socket.getaddrinfo = getaddrinfo_ipv4

	threads = []
	q = Queue.Queue()
	for url in urls:
		new_thread = URLRequestThread(q, url, timeout)
		threads.append(new_thread)
		new_thread.start()

	for t in threads:
		t.join()

	output = {}
	while not q.empty():
		url, data = q.get()
		output[url] = data

	if force_ipv4:
		socket.getaddrinfo = orig_getaddrinfo

	return output
