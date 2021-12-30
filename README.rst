===========
TTUN Server
===========

|Release|

.. |Release| image:: https://github.com/tomvanderlee/ttun-server/actions/workflows/docker-image.yml/badge.svg
   :target: https://github.com/tomvanderlee/ttun-server/actions/workflows/docker-image.yml

The self-hostable proxy tunnel.

Running
-------

Running::

    docker run -e TUNNEL_DOMAIN=<Your tunnel domain> -e SECURE=<True if using SSL> ghcr.io/tomvanderlee/ttun-server:latest


Environment variables:

+----------------+-----------------------------------------------------------------------------------------------------------------+--------------+
| Variable       | Description                                                                                                     | Valid Value  |
+================+=================================================================================================================+==============+
| TUNNEL_DOMAIN  | The domain your tunnel server is hosted on. Any individual tunnels will be hosted as a subdomain of this one.   | FQDN         |
+----------------+-----------------------------------------------------------------------------------------------------------------+--------------+
| SECURE         | Set this value to True if you are hosting the tunnel with SSL. If not leave this variable out                   |              |
+----------------+-----------------------------------------------------------------------------------------------------------------+--------------+

Developing
----------

1. Create and activate a python 3.10 virtual environment

2. Install requirements::

    pip install -r requirements.txt

3. Run::

    uvicorn ttun_server:server --reload
