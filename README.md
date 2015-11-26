nzbsrv - Simple web server to list and download movies from RSS feed of NZB indexes
===================================================================================

It grabs some info about the movie, like poster and imdb link.
It provides Download and Ignore buttons.
  - Download will download the .nzb in a folder, so that sabnzbs or other can start downloading it.
  - Ignore will mark the movie as ignore so it won't show up again.

Displays nicely on mobile phone.

No external module dependency. Works with Python 2.7.
Works with the RSS format of omgwtfnzbs.
You are responsible for what you download.

## Usage

Edit nzbconfig.py to put your own RSS feeds and username / api key, and run:

```
python nzbsrv.py
```

## ISC License

https://github.com/shazbits/nzbsrv/blob/master/LICENSE.txt

Romain Dura

http://www.shazbits.com
