import argparse
import os
import errno
import io
import importlib
import sys
import time
import json
import logging
import requests
from lxml import etree
from owslib.wms import WebMapService

from datetime import datetime, timedelta
import dateutil
#import pendulum

try:
    from urllib.parse import urlparse  # Python 3
except ImportError:
    from urlparse import urlparse  # Python 2

GWC_REST_URL = "http://localhost:8080/geowebcache/rest"
NC_LAYERINFO_URL = "https://nowcoast.noaa.gov/layerinfo"
NC_LAYERINFO_DEF_REQUEST = "timestops"
NC_LAYERINFO_DEF_SERVICE = "radar_meteo_imagery_nexrad_time"
NC_LAYERINFO_DEF_FORMAT = "json"
WMS_URL = "http://localhost.kachina:8070/geoserver/wms?"
TIME_OUTPUT_FMT = "rfc3339"
OUTPUT = "gwc.out"
LOG = "gwc.log"

# logging:
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
log = logging.FileHandler(LOG, mode='w')
log.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
logger.addHandler(log)


def main():
    """
    Command line interface
    """
    kwargs = {
        'description': 'Simple command line tool to pass a GWC layer identifier to update.',
        'formatter_class': argparse.RawDescriptionHelpFormatter,
    }
    parser = argparse.ArgumentParser(**kwargs)


    parser.add_argument('-l', '--layer_id', type=str, required=True,
                        help='GWC layer ID (REST API) to update')
    parser.add_argument('--gwc_rest_url', type=str, default=GWC_REST_URL, required=False,
                        help='GWC REST API URL.  Default: {gwc_rest_url}'.format(gwc_rest_url=GWC_REST_URL))


    parser.add_argument('--nc_layerinfo_url', type=str, default=NC_LAYERINFO_URL, required=False,
                        help='nowCOAST LayerInfo service URL.  Default: {nc_layerinfo_url}'.format(nc_layerinfo_url=NC_LAYERINFO_URL))
    parser.add_argument('--nc_layers', type=str, required=False,
                        help='Comma separated list of layer(s) in the nowCOAST service to query')
    parser.add_argument('--nc_req', type=str, default=NC_LAYERINFO_DEF_REQUEST, required=False,
                        help='nowCOAST LayerInfo service request type.  Default: {nc_req}'.format(nc_req=NC_LAYERINFO_DEF_REQUEST))
    parser.add_argument('--nc_service', type=str, default=NC_LAYERINFO_DEF_SERVICE, required=False,
                        help='nowCOAST LayerInfo service REST service name to query.  Default: {nc_service}'.format(nc_service=NC_LAYERINFO_DEF_SERVICE))
    parser.add_argument('--nc_fmt', type=str, default=NC_LAYERINFO_DEF_FORMAT, required=False,
                        help='nowCOAST LayerInfo service output format.  Default: {nc_fmt}'.format(nc_fmt=NC_LAYERINFO_DEF_FORMAT))

    # for wms_url, if one is passed, we use that for time dimension values rather than the nc_layerinfo_url
    parser.add_argument('--wms_url', type=str, required=False, help='WMS URL to parse.  Specify this to use instead of the NC LayerInfo Servlet')

    parser.add_argument('--wms_layer', type=str, required=False,
                        help='The id of the WMS layer we will query to discover available time values')

    parser.add_argument('--time_output_fmt', type=str, choices=set(("rfc3339", "iso8601")), default=TIME_OUTPUT_FMT, required=False,
                        help='Timestamp output format.  One of \'rfc3339\' or \'iso8601\' Default: {time_output_fmt}'.format(
                            time_output_fmt=TIME_OUTPUT_FMT))

    parser.add_argument('-o', '--output', type=str, required=False, default=OUTPUT,
                        help='Output filename (path to a file to output results to).  Default: {out}'.format(out=OUTPUT))

    # parser.add_argument('-o', '--output', type=str, default='', required=False,
    #                    help='')
    # parser.add_argument('-o', '--output', type=str, default='', required=False,
    #

    args = parser.parse_args()

    filename = args.output
    try:
        out = io.open(filename, mode="wt", encoding="utf-8")
    except IOError:
        print("Unable to write output file: {file}".format(file=filename))
        exit(1)

    # set the output format we'll use to write date strings 'iso8601' or 'rfc3339':
    if args.time_output_fmt == "rfc3339":
        time_output_fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
    elif args.time_output_fmt == "iso8601":
        time_output_fmt = "%Y-%m-%dT%H:%M:%S"
    else:
        time_output_fmt = "%Y-%m-%dT%H:%M:%S"


    ##############################################
    # query the GWC REST API:
    ##############################################
    url = ("/").join([args.gwc_rest_url, "layers", args.layer_id]) + ".xml"
    if logger: logger.info("Querying GWC for layer: {layer}.  URL: {url}. Parameters {params}".format(layer=args.layer_id, url=url, params=""))
    r = requests.get(url=url, auth=('geowebcache', 'secured'))
    #get the text output, but save 'gwc_layer_xml_byte' since etree expects bytes to avoid encoding issues
    gwc_layer_xml = r.text
    gwc_layer_xml_byte = r.content
    #debug:
    #print(gwc_layer_xml)
    #out.write(gwc_layer_xml)

    ##############################################
    # query the NC LayerInfo Service or WMS:
    ##############################################
    # timestops will hold the source service's time values:
    timestops = []

    # if a 'wms_url' parameter was passed, we'll use that:
    if args.wms_url is not None:
        url = args.wms_url
        try:
            wms = WebMapService(url, version='1.3.0')
        except Exception as e:
            print("WMS URL: {url} is not 1.3.0 compliant, falling back to 1.1.1.  Err: {err}".format(url=args.wms_url, err=e))
            if logger:
                logger.info("WMS URL: {url} is not 1.3.0 compliant, falling back to 1.1.1.  Err: {err}".format(url=args.wms_url, err=e))
            try:
                wms = WebMapService(url, version='1.1.1')
            except Exception as e:
                print("WMS URL: {url} is not 1.3.0 or 1.1.1 compliant.  Err: {err}".format(url=args.wms_url, err=e))
                if logger:
                    logger.info("WMS URL: {url} is not 1.3.0 or 1.1.1 compliant.  Err: {err}".format(url=args.wms_url, err=e))
                exit(code=2)
        print(wms.identification.type)
        print(list(wms.contents))

        if args.wms_layer is not None:
            if args.wms_layer in wms.contents:
                print("OWSLib timepositions:")
                for timeposition in wms.contents[args.wms_layer].timepositions:
                    print(timeposition)
                    # timestops.append(datetime.strptime(timeposition, "%Y-%m-%dT%H:%M:%S.%f%z"))
                    timestops.append(dateutil.parser.parse(timeposition))
                    #timestops.append(pendulum.parse(timeposition))

    # otherwise, use the LayerInfo Servlet to query for new time stops:
    else:
        url = args.nc_layerinfo_url
        payload = {'request': 'timestops', 'service': args.nc_service, 'layers': args.nc_layers, 'format': args.nc_fmt}
        if logger: logger.info("Querying NC LayerInfo service: {url}. Parameters: {params}".format(layer=args.layer_id, url=url, params=payload))

        r = requests.get(url=url, params=payload)
        layerinfo_result = r.text

        # convert to json to extract timestops
        nc_layerinfo_json = json.loads(layerinfo_result)
        timestops = nc_layerinfo_json['layers'][0]['timeStops']
        # debug:
        #print(json.dumps(nc_layerinfo_json, indent=4))
        #out.write(json.dumps(nc_layerinfo_json, indent=4) + "\n")

        for i, stop in enumerate(timestops):
            timestops[i] = datetime.utcfromtimestamp(stop / 1000)


    ##############################################
    # lxml parsing/replacing:
    ##############################################
    # parse GWC XML to update with new time values:
    # first line doesn't work, need to use byte output format from requests to generate etree for some reason
    #parser = etree.XMLParser(encoding="UTF-8")
    #root = etree.fromstring(gwc_layer_xml, parser)

    # parse the byte output from requests instead:
    root = etree.fromstring(gwc_layer_xml_byte)

    # get the bounding box(es):
    grid_subsets = {}
    layer_grid_subsets = root.xpath("//gridSubsets/gridSubset")
    for grid in layer_grid_subsets:
        #coords = grid.xpath("extent/coords")
        coords = grid.find("extent/coords")
        grid_subsets[grid.find("gridSetName").text] = [bound.text for bound in coords.iter("double")]

    for key, coords in grid_subsets.items():
        print("GridSet: {srs}.  Coords: {coords}".format(srs=key, coords=",".join(coords)))


    #time_parameter_filter = root.xpath("//parameterFilters/stringParameterFilter/key[text().lower()='time']")
    time_parameter_filter = root.xpath("//parameterFilters/stringParameterFilter[key ='TIME']")[0]
    time_values = time_parameter_filter.find("values")
    time_value_default = time_parameter_filter.find("defaultValue")

    gwc_filter_times = []
    for child in time_values.iter("string"):
        #print(child.text)

        # use with date formats like: 2017-09-06T13:00:00.000Z
        #gwc_filter_times.append(datetime.strptime(child.text.replace('Z', '+0000'), "%Y-%m-%dT%H:%M:%S.%f%z"))
        # use with date formats like: 2017-09-12T11:44:00
        #gwc_filter_times.append(datetime.strptime(child.text, "%Y-%m-%dT%H:%M:%S"))

        # Try dateutil parser for more universal support... (2017-09-06T13:00:00.000Z, 2017-09-12T11:44:00)
        gwc_filter_times.append(dateutil.parser.parse(child.text))

    # debug: print gwc_filter_times:
    #print(gwc_filter_times)

    # timestop_add: list of NC timestops that will be added to the GWC layer config and used for cache seeding later
    timestop_add = []
    for timestop in timestops:
        if timestop not in gwc_filter_times:

            print("New timestop from WMS added to GWC parameter filter list: {date}".format(date=timestop.strftime(time_output_fmt)))
            timestop_add.append(timestop)

            #add new 'string' subelements:
            time_values.append(etree.fromstring("<string>{date}</string>".format(date=timestop.strftime(time_output_fmt))))
            print(len(list(time_values)))

    # gwc_time_remove: list of existing time parameter filters that are no longer valid, used for cache truncation later
    # gwc_time_remain: just a copy of the gwc_filter_times list to keep a list of still valid gwc_filter_times (to calc defaultValue)
    gwc_time_remove = []
    gwc_time_remain = list(gwc_filter_times)
    for gwc_filter_time in gwc_filter_times:
        if gwc_filter_time not in timestops:
            print("GWC time parameter filter expired: {date}".format(date=gwc_filter_time.strftime(time_output_fmt)))
            gwc_time_remove.append(gwc_filter_time)

            # remove the expired time from the gwc_time_remain list also (need current list to calculate defaultValue):
            gwc_time_remain.remove(gwc_filter_time)

            # iterate over the <string> XML config elements to identify those to remove:
            for child in time_values.iter("string"):
                if dateutil.parser.parse(child.text) == gwc_filter_time:
                    #print("Match: " + child.text)
                    time_values.remove(child)

            print(len(list(time_values)))

    # set the defaultValue to be latest time:
    final_valid_times = gwc_time_remain + timestop_add
    final_valid_times.sort(reverse=True)
    time_value_default.text = final_valid_times[0].strftime(time_output_fmt)

    print("final_valid_times:")
    for time_value in final_valid_times:
        print(time_value.strftime(time_output_fmt))


    # debug: print the resulting XML to stdout for debug:
    #print(etree.dump(root, pretty_print=True))


    ##############################################
    #submit new layer config to GWC:
    ##############################################
    url = ("/").join([args.gwc_rest_url, "layers", args.layer_id]) + ".xml"
    if logger: logger.info(
        "Updating GWC layer: {layer} via POST.  URL: {url}.".format(layer=args.layer_id, url=url))
    r = requests.post(url=url, auth=('geowebcache', 'secured'), data=etree.tostring(root))



    ##############################################
    # seed and truncate:
    ##############################################

    '''
    # from docs:
    {
        "seedRequest": {
            "name": "topp:states",
            "bounds": {"coords": {"double": ["-180", "-90", "180", "90"]}},
            "srs": {"number": 4326},
            "zoomStart": 1,
            "zoomStop": 12,
            "format": "image\/png",
            "type": "seed",
            "threadCount": 4
        }
    }
    
    { "seedRequest": {
            "name": "topp:states",
            "bounds": {"coords": {"double": ["-180", "-90", "180", "90"]}},
            "srs": {"number":4326},
            "zoomStart": 1,
            "zoomStop": 12,
            "format": "image\/png",
            "type": "truncate",
            "threadCount": 4
        }
    }
    '''

    truncate_template_time = {
        "seedRequest": {
            "name":"topp:states",
            "bounds": {"coords": {"double": ["-180", "-90", "180", "90"]}},
            "srs": {"number": 4326},
            "zoomStart": 0,
            "zoomStop": 20,
            "format": "image/png",
            "type": "truncate",
            "threadCount": 1,
            "parameters": {
                "entry": [
                    {"string": ["TIME", "2017-09-13T12:56:00"]}
                ]
            }

        }
    }

    truncate_template = {
        "seedRequest": {
            "name": "topp:states",
            "bounds": {"coords": {"double": ["-180", "-90", "180", "90"]}},
            "srs": {"number": 4326},
            "zoomStart": 0,
            "zoomStop": 20,
            "format": "image/png",
            "type": "truncate",
            "threadCount": 1
        }
    }

    seed_template_bbox = {
        "seedRequest": {
            "name": "topp:states",
            "bounds": {"coords": {"double": ["-180", "-90", "180", "90"]}},
            "srs": {"number": 4326},
            "zoomStart": 0,
            "zoomStop": 7,
            "format": "image/png",
            "type": "seed",
            "threadCount": 4
        }
    }

    seed_template_bbox_time = {
        "seedRequest": {
            "name": "topp:states",
            "bounds": {"coords": {"double": ["-180", "-90", "180", "90"]}},
            "srs": {"number": 4326},
            "zoomStart": 0,
            "zoomStop": 7,
            "format": "image/png",
            "type": "seed",
            "threadCount": 4,
            "parameters": {
                "entry": [
                    {"string": ["TIME", "2017-09-13T12:56:00"]}
                ]
            }
        }
    }

    seed_template = {
        "seedRequest": {
            "name": "topp:states",
            "srs": {"number": 4326},
            "zoomStart": 1,
            "zoomStop": 7,
            "format": "image/png",
            "type": "seed",
            "threadCount": 4
        }
    }

    url = ("/").join([args.gwc_rest_url, "seed", args.layer_id]) + ".json"

    ##############################################
    # truncating:
    ##############################################
    # ToDo: this will all need to be wrapped in a function or iterated over by:
    #   gridset SRS (only handles 4326 currently)
    # ToDo: need to account for zoomLevel (presently only hard-coded to 1 to 7 in JSON templates (should truncate all levels)

    # TEST: test truncating default cache:
    data = truncate_template
    data['seedRequest']['name'] = args.layer_id
    data['seedRequest']['srs']['number'] = 4326
    data['seedRequest']['bounds']['coords']['double'] = grid_subsets['EPSG:4326']
    print("Truncate request (default cache) json:")
    print(data)
    if logger: logger.info(
        "Truncating GWC default cache for layer: {layer}. URL: {url}.".format(layer=args.layer_id, url=url))
    rest_seed_truncate(url, "post", data)

    # truncate expired time parameter filter caches:
    #print(gwc_time_remove)
    if True:
        for gwc_time in gwc_time_remove[:1]:
        # for gwc_time in gwc_time_remove:
        # for gwc_time in gwc_filter_times[-1:]:
        # for gwc_time in gwc_filter_times[:1]:
        # test clearing the same cache just seeded to troubleshoot:
        #for gwc_time in timestop_add[:1]:

            data = truncate_template_time
            data['seedRequest']['name'] = args.layer_id
            data['seedRequest']['srs']['number'] = 4326
            data['seedRequest']['bounds']['coords']['double'] = grid_subsets['EPSG:4326']
            data['seedRequest']['parameters']['entry'][0]['string'][1] = gwc_time.strftime(time_output_fmt)

            print("Truncate request json for time: {time}".format(time=gwc_time.strftime(time_output_fmt)))
            print(data)
            if logger:
                logger.info("Truncating GWC layer: {layer}, timestop: {stop}.  URL: {url}.".format(layer=args.layer_id,
                                                                                                   stop=gwc_time, url=url))
            rest_seed_truncate(url, "post", data)

    # wait until we know truncate has completed before starting seeding
    # (mostly due to 'default' time cache needing to be re-seeded on each update - cache must be fully truncated first):
    status_url = ("/").join([args.gwc_rest_url, "seed", args.layer_id]) + ".json"
    while True:
        # response should look like:
        #   running task: {"long-array-array":[[-1,-1,-2,314,2]]}
        #   no tasks: {"long-array-array":[]}
        r = rest_seed_truncate(url, "get")
        truncate_status = r.json()
        if not truncate_status['long-array-array']:
            break
        time.sleep(3)

    ##############################################
    # seeding:
    ##############################################
    # ToDo: this will all need to be wrapped in a function or iterated over by:
    #   gridset SRS (only handles 4326 currently)
    #   other?

    # first, we want to seed the default cache (no time filter value):
    # default cache appears to exist even if <defaultValue> is set to most recent time filter value and a time filter
    # cache exists for this time value
    # this will need to be truncated and re-seeded each refresh???
    if True:
        data = seed_template_bbox
        data['seedRequest']['name'] = args.layer_id
        data['seedRequest']['srs']['number'] = 4326
        data['seedRequest']['bounds']['coords']['double'] = grid_subsets['EPSG:4326']
        data['seedRequest']['zoomStart'] = 1
        data['seedRequest']['zoomStop'] = 5
        print("Seed request (default cache) json:")
        print(data)
        if logger: logger.info(
            "Seeding GWC default cache for layer: {layer}. URL: {url}.".format(layer=args.layer_id, url=url))
        rest_seed_truncate(url, "post", data)

    if True:
        timestop_add.sort(reverse=True)
        # next, we want to seed any newly added timestops in their own time filter cache:
        for timestop in timestop_add[:1]:
        #for timestop in timestop_add[]]:

            data = seed_template_bbox_time
            data['seedRequest']['name'] = args.layer_id
            data['seedRequest']['srs']['number'] = 4326
            data['seedRequest']['bounds']['coords']['double'] = grid_subsets['EPSG:4326']
            data['seedRequest']['zoomStart'] = 1
            data['seedRequest']['zoomStop'] = 5
            data['seedRequest']['parameters']['entry'][0]['string'][1] = timestop.strftime(time_output_fmt)

            print("Seed request json for time: {time}".format(time=timestop.strftime(time_output_fmt)))
            print(data)
            if logger: logger.info(
                "Seeding GWC layer: {layer}, timestop: {stop}.  URL: {url}.".format(layer=args.layer_id, stop=timestop,
                                                                                    url=url))
            rest_seed_truncate(url, "post", data)

    # just check the seeding status to know if it's completed
    while True:
        # response should look like:
        #   running task: {"long-array-array":[[-1,-1,-2,314,2]]}
        #   no tasks: {"long-array-array":[]}
        r = rest_seed_truncate(url, "get")
        truncate_status = r.json()
        if not truncate_status['long-array-array']:
            break
        time.sleep(3)


def rest_seed_truncate(url, method, data=None):
    """
    :param url: GWC REST API URL
    :param method: one of 'get', 'put', 'post', 'delete'
    :param data: json to send, if any
    :return: the requests response object if successful, otherwise, log an error (ToDo: should be thrown instead)
    """
    try:
        if method.lower() == "get":
            r = requests.get(url=url, auth=('geowebcache', 'secured'), json=data)
        elif method.lower() == "post":
            r = requests.post(url=url, auth=('geowebcache', 'secured'), json=data)
        elif method.lower() == "put":
            r = requests.put(url=url, auth=('geowebcache', 'secured'), json=data)
        elif method.lower() == "delete":
            r = requests.delete(url=url, auth=('geowebcache', 'secured'), json=data)

        r.raise_for_status()
        print(r.text)
        return r
    except requests.exceptions.HTTPError as err:
        print(err)