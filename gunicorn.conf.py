# Gunicorn reads this file automatically. AI replies can take 20-40 s, so give
# workers more time than the 30 s default before they are restarted.
timeout = 120
workers = 2
threads = 4
