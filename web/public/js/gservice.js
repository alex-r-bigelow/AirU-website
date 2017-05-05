// Creates the gservice factory. This will be the primary means by which we interact with Google Maps
angular.module('gservice', [])
    .factory('gservice', function($http) {

      // Initialize Variables
      // -------------------------------------------------------------
      // Service our factory will return
      var googleMapService = {};

      // Array of locations obtained from API calls
      var locations = [];

      // Selected Location (initialize to SLC)
      var selectedLat = parseFloat(40.7608);
      var selectedLong = parseFloat(-111.8910);

      // Functions
      // --------------------------------------------------------------
      // Refresh the Map with new data. Function will take new latitude and longitude coordinates.
      googleMapService.refresh = function(latitude, longitude) {

        // Clears the holding array of locations
        locations = [];

        // Set the selected lat and long equal to the ones provided on the refresh() call
        selectedLat = latitude;
        selectedLong = longitude;

        // Perform an AJAX call to get all of the records in the db.
// TODO     when /devices works uncomment
        $http.get('/devices').then(function(response){

            // Convert the results into Google Map Format
            locations = convertToMapPoints(response.data);

            // Then initialize the map.
            initialize(latitude, longitude);
        }, function(error){});

        initMap();

      //   $http({
      //     method: 'POST',
      //     url: 'http://air.eng.utah.edu:8086/query',
  	  //     data: {
  	  //       db: 'defaultdb',
  	  //       q: 'SELECT * FROM airQuality WHERE time >= \'2017-02-01\' LIMIT 100'
  	  //     }
      //   }).then(function mySuccess(response) {
      //     response = response.results[0].series[0];
      //     //console.log(response);
      //     var sensorInfoArray = [];
      //
      //     for( var k = 0; k < response.values.length; k += 1) {
      //       var infoObject = {};
      //
      //       for (var i = 0; i < response.columns.length; i += 1){
      //         infoObject[response.columns[i]] = response.values[k][i];
      //       }
      //
      //       sensorInfoArray.push(infoObject);
      //     }
      //
      //     //create dictionary with ID as key and tuples of
      //     var objectDictWTime = createObjectDict(sensorInfoArray);
      //     sortByTime(objectDictWTime);
      //
      //     // Produces markers for objects created from data, adds listeners for click function
      //     sensorInfoArray.forEach(function(item, index) {
      //       if (item["Latitude"] !== null && item["Longitude"] !== null) {
      //         console.log(item);
      //         var marker = new google.maps.Marker({
      //           position: {lat: item["Latitude"], lng: item["Longitude"]}, map: map
      //         });
      //
      //         //var contentBox = makeGraph(item, objectDictWTime);
      //         var contentBox = "Sensor: " + item["ID"] +"<br/>Air Quality (pm2.5): " + item["pm2.5 (ug/m^3)"];
      //         var infowindow = new google.maps.InfoWindow({content: contentBox});
      //
      //         marker.addListener('click', function() {
      //           infowindow.open(marker.get('map'), marker);
      //         });
      //       }
      //     });
      //
      //     console.log(objectDictWTime);
      //
      //   }, function myError(response) {
      //     console.warn(arguments);
      //   });
      };




      // Private Inner Functions
      // --------------------------------------------------------------
      // Convert a JSON of users into map points
      var convertToMapPoints = function(response){

        // Clear the locations holder
        var locations = [];

        // Loop through all of the JSON entries provided in the response
        for(var i= 0; i < response.length; i++) {
          var device = response[i];

          // Create popup windows for each record
          var  contentString =
              '<p><b>sensor_model</b>: ' + device.sensor_model +
              '<br><b>sensor_version</b>: ' + device.sensor_version +
              '<br><b>macaddress</b>: ' + device.macaddress +
              '<br><b>longitude</b>: ' + device.longitude +
              '<br><b>latitude</b>: ' + device.latitude +
              '<br><b>created_at</b>: ' + device.created_at +
              '</p>';

          // Converts each of the JSON records into Google Maps Location format (Note [Lat, Lng] format).
          locations.push({
            latlon: new google.maps.LatLng(parseFloat(device.location[1]), parseFloat(device.location[0])),
            message: new google.maps.InfoWindow({
                content: contentString,
                maxWidth: 320
            }),
            sensor_model: device.sensor_model,
            sensor_version: device.sensor_version,
            macaddress: device.macaddress,
            longitude: device.longitude,
            latitude: device.latitude,
            created_at: device.created_at
          });
        }
        // location is now an array populated with records in Google Maps format
        return locations;
      };

      var map;
      // Initializes the map
      var initialize = function(latitude, longitude) {

        // Uses the selected lat, long as starting point
        var myLatLng = {lat: parseFloat(selectedLat), lng: parseFloat(selectedLong)};

        // If map has not been created already...
        if (!map){

          // Create a new map and place in the index.html page
          map = new google.maps.Map(document.getElementById('map'), {
              zoom: 8,
              center: myLatLng
          });

          window.testMap = map;
        }

        // Loop through each location in the array and place a marker
        locations.forEach(function(n, i) {
          var marker = new google.maps.Marker({
              position: n.latlon,
              map: map,
              title: "Big Map",
              icon: "green_MarkerA.png",
          });

          // For each marker created, add a listener that checks for clicks
          google.maps.event.addListener(marker, 'click', function(e) {

              // When clicked, open the selected marker's message
              currentSelectedMarker = n;
              n.message.open(map, marker);
          });
        });

        // // Set initial location as a bouncing red marker
        // var initialLocation = new google.maps.LatLng(latitude, longitude);
        // var marker = new google.maps.Marker({
        //     position: initialLocation,
        //     animation: google.maps.Animation.BOUNCE,
        //     map: map,
        //     icon: 'http://maps.google.com/mapfiles/ms/icons/red-dot.png'
        // });
        // lastMarker = marker;

      };

      // Refresh the page upon window load. Use the initial latitude and longitude
      google.maps.event.addDomListener(window, 'load',
          googleMapService.refresh(selectedLat, selectedLong));

      return googleMapService;
});
