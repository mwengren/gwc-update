### gwc_update ###
Python client to use to manage GeoWebCache time filter parameter synchronization with source WMS data services.  'gwc'
is designed to query the source WMS for explicit time dimension values (a list of valid time steps), in both iso8601
compatible formats and RFC3339 (default used by GeoServer).  It also is able to query and parse the custom 'LayerInfoServlet'
developed for the [nowcoast](https://nowcoast.noaa.gov) project that it was written to support.  More info about the
nowCOAST LayerInfo Servlet is available [here](https://nowcoast.noaa.gov/help/#!section=layerinfo).


### Installation ###
```
git clone https://github.com/mwengren/gwc_update.git
cd gwc_update
python setup.py install
```


Parameters:

```
  -l LAYER_ID, --layer_id LAYER_ID:     GWC layer ID (REST API) to update
  --gwc_rest_url GWC_REST_URL:          GWC REST API URL. Default:  http://localhost:8080/geowebcache/rest
  --nc_layerinfo_url NC_LAYERINFO_URL:  nowCOAST LayerInfo service URL. Default:  https://nowcoast.noaa.gov/layerinfo
  --nc_layers NC_LAYERS:                Comma separated list of layer(s) in the nowCOAST service to query
  --nc_req NC_REQ:                      nowCOAST LayerInfo service request type. Default: timestops
  --nc_service NC_SERVICE:              nowCOAST LayerInfo service REST service name to query. Default: radar_meteo_imagery_nexrad_time
  --nc_fmt NC_FMT:                      nowCOAST LayerInfo service output format. Default: json
  --wms_url WMS_URL:                    WMS URL to parse. Specify this to use instead of the NC LayerInfo Servlet
  --wms_layer WMS_LAYER:                The id of the WMS layer we will query to discover available time values
  --time_output_fmt {iso8601,rfc3339}:  Timestamp output format. One of 'rfc3339' or 'iso8601'.  Default: rfc3339
  -o OUTPUT, --output OUTPUT:           Output filename (path to a file to output results to). Default: gwc.out

```




#### Usage: ####
```
# Update the GeoWebCache layer 'nexrad_reflectivity' with the timestop values for layer '1' of the nowCOAST service
# 'radar_meteo_imagery_nexrad_time' using the nowCOAST LayerInfo Servlet
gwc -l nexrad_reflectivity --nc_layers 1 --nc_service radar_meteo_imagery_nexrad_time --gwc_rest_url http://34.201.47.185/geowebcache/rest  --time_output_fmt iso8601

# Update the GeoWebCache layer 'nowCOAST_Geo:ndfd_wind' with the time dimension values for the WMS layer of the same name from WMS
# service 'http://localhost:8070/geoserver/wms?' using time format RFC3339 for the GeoWebCache output time filter values
gwc -l nowCOAST_Geo:ndfd_wind --gwc_rest_url http://localhost:8090/geowebcache/rest --wms_url http://localhost:8070/geoserver/wms? --wms_layer nowCOAST_Geo:ndfd_wind --time_output_fmt rfc3339

```
